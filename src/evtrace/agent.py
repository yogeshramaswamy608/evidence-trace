"""Agents for AIOpsLab runs (manuscript Sections 5.2 and 5.4).

ModelAgent follows AIOpsLab's ReAct client (clients/react.py at commit 576c3f0): the same API
documentation template and the same "Thought / Action" reply format, with one model behind it
called through the Anthropic Messages API. ProbeAgent needs no model: it issues a fixed sequence
of read actions and submits, so the instrumentation can be tested end to end on a cluster for free.

After the session, summarize() asks the agent for the root-cause summary of its condition:
A, free text; B, a provenance record whose links name telemetry by locator (see locate.py)."""
from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request

RESP_INSTR = """DO NOT REPEAT ACTIONS! Respond with:
Thought: <your thought on the previous output>
Action: <your action towards solving the task>
"""

SUMMARY_A = """Your submission is recorded. Now write a short root-cause analysis summary that explains
your submission: what you observed, what you inferred, and what you concluded. Plain text, at most
200 words. Do not call any action."""

SUMMARY_B = """Your submission is recorded. Now write a short root-cause analysis summary that explains
your submission, as one JSON object and nothing else, in this form:
{"claims": [{"claim_id": "c1", "text": "...", "type": "observation|inference|root_cause|recommendation",
  "no_evidence_found": false, "services": ["..."],
  "links": [{"link_type": "supports|partly_supports|contradicts|context|derived_from", "target": "..."}]}]}
Rules. Each claim is one atomic statement. Every observation and root_cause claim needs at least one
supports or partly_supports link, or "no_evidence_found": true. A link target is either another claim_id
(only with derived_from) or a locator of telemetry you were shown in this session:
  span:<trace_id>/<span_id>        a span from a traces table
  log:<exact log line>             one log line, copied exactly
  metric:<series>@<timestamp>      one metric sample
  cmd:<exact output line>          one line of command output, copied exactly
Link only to telemetry that appears in the observations above."""



EMPTY_REPLY = "(empty reply)"

class ModelAgent:
    """ReAct agent backed by one model; reads the key from LLM_API_KEY."""

    def __init__(self, model: str, temperature: float | None = None, max_tokens: int = 1024,
                 endpoint: str = "https://api.anthropic.com/v1/messages", seed: int = 0) -> None:
        self.model, self.temperature, self.max_tokens, self.endpoint = model, temperature, max_tokens, endpoint
        self.seed = seed  # recorded per run; the Messages API has no seed parameter
        self.system = ""
        self.messages: list[dict] = []
        self.notes: list[str] = []
        self.usage = {"calls": 0, "input_tokens": 0, "output_tokens": 0,
                      "cache_read_input_tokens": 0, "cache_creation_input_tokens": 0}

    def init_context(self, problem_desc: str, instructions: str, apis: dict) -> None:
        from clients.utils.templates import DOCS  # AIOpsLab's own template, same as its ReAct client

        def fmt(d):
            return "\n\n".join(f"{k}\n{v}" for k, v in d.items())
        self.system = DOCS.format(
            prob_desc=problem_desc,
            telemetry_apis=fmt({k: v for k, v in apis.items() if "exec_shell" not in k and "submit" not in k}),
            shell_api=fmt({k: v for k, v in apis.items() if "exec_shell" in k}),
            submit_api=fmt({k: v for k, v in apis.items() if "submit" in k}))
        self.messages = [{"role": "user", "content": instructions}]

    async def get_action(self, input: str) -> str:
        self._user(f"{input}\n\n{RESP_INSTR}")
        reply = self._call()
        self.messages.append({"role": "assistant", "content": reply})
        return reply

    def summarize(self, condition: str) -> str:
        self._user(SUMMARY_B if condition == "B" else SUMMARY_A)
        reply = self._call(max_tokens=2048)
        self.messages.append({"role": "assistant", "content": reply})
        return reply

    def _user(self, text: str) -> None:
        if self.messages and self.messages[-1]["role"] == "user":
            self.messages[-1]["content"] += "\n\n" + text
        else:
            self.messages.append({"role": "user", "content": text})

    def _call(self, max_tokens: int | None = None) -> str:
        key = os.environ.get("LLM_API_KEY")
        if not key:
            raise RuntimeError("LLM_API_KEY is not set")
        msgs = [dict(m) for m in self.messages]
        # An empty model reply cannot be sent back as text (pilot run 42138467998, Nov 5, 2026: HTTP 400,
        # "cache_control cannot be set for empty text blocks"); the API copy carries a marker, the transcript keeps "".
        for m in msgs:
            if isinstance(m["content"], str) and not m["content"].strip():
                m["content"] = EMPTY_REPLY
        # Cache the growing conversation prefix: the system prompt and every turn before the last.
        if len(msgs) >= 2:
            prev = msgs[-2]
            prev["content"] = [{"type": "text", "text": prev["content"], "cache_control": {"type": "ephemeral"}}]
        body = {"model": self.model, "max_tokens": max_tokens or self.max_tokens,
                "system": [{"type": "text", "text": self.system, "cache_control": {"type": "ephemeral"}}],
                "messages": msgs}
        if self.temperature is not None:  # newer models refuse temperature (pilot of Nov 5, 2026), so send it only when set
            body["temperature"] = self.temperature
        for attempt in range(6):
            req = urllib.request.Request(self.endpoint, data=json.dumps(body).encode(), method="POST", headers={
                "content-type": "application/json", "x-api-key": key, "anthropic-version": "2023-06-01"})
            try:
                with urllib.request.urlopen(req, timeout=300) as resp:
                    out = json.load(resp)
                break
            except urllib.error.HTTPError as e:
                if e.code in (429, 500, 502, 503, 529) and attempt < 5:
                    time.sleep(2 ** attempt * 5)
                    continue
                detail = e.read().decode("utf-8", "replace")[:2000]
                # Some models refuse a sampling parameter; drop it once and retry, keeping the reason on record.
                if e.code == 400 and "temperature" in detail and "temperature" in body and attempt < 5:
                    self.notes.append("temperature refused by the API; sent without it: " + detail[:300])
                    body.pop("temperature")
                    continue
                raise RuntimeError(f"HTTP {e.code} from the API: {detail}") from e
        self.usage["calls"] += 1
        for k in self.usage:
            if k != "calls":
                self.usage[k] += out.get("usage", {}).get(k, 0) or 0
        return "".join(b.get("text", "") for b in out.get("content", []) if b.get("type") == "text")


class ProbeAgent:
    """Scripted agent with no model: reads traces, metrics, logs and pods, then submits nothing useful."""

    def __init__(self, namespace: str = "test-hotel-reservation", service: str = "geo") -> None:
        self.steps = [
            f'get_traces("{namespace}", 5)',
            f'get_metrics("{namespace}", 5)',
            f'get_logs("{namespace}", "{service}")',
            f'exec_shell("kubectl get pods -n {namespace}")',
            "submit([])",
        ]
        self.i = 0
        self.usage = {"calls": 0}
        self.last_paths: list[str] = []

    def init_context(self, problem_desc: str, instructions: str, apis: dict) -> None:
        pass

    async def get_action(self, input: str) -> str:
        # get_traces and get_metrics return a file path; read it on the next step, as an agent would.
        if self.last_paths:
            path = self.last_paths.pop(0)
            kind = "read_traces" if "trace" in path.lower() else "read_metrics"
            return f'Thought: read the exported file\nAction: ```\n{kind}("{path}")\n```'
        if "/" in (input or "") and self.i in (1, 2):
            first = input.strip().splitlines()[0].strip()
            if first.endswith((".csv", "/")) or os.path.exists(first):
                self.last_paths.append(first)
                return await self.get_action("")
        step = self.steps[min(self.i, len(self.steps) - 1)]
        self.i += 1
        return f"Thought: probe step {self.i}\nAction: ```\n{step}\n```"

    def summarize(self, condition: str) -> str:
        return "" if condition == "A" else json.dumps({"claims": []})
