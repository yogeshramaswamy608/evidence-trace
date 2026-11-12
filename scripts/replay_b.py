"""Condition B format failures: length count, rebuild check and one replay (P4, deviation 4, Nov 12, 2026).

Run from an AIOpsLab checkout at commit 576c3f0 (see .github/workflows/replay.yml), with LLM_API_KEY set.
  python scripts/replay_b.py count  RUNS_DIR OUT_DIR
  python scripts/replay_b.py replay RUNS_DIR OUT_DIR --budget-usd 5
RUNS_DIR holds the run folders of the failed Condition B runs (data/runs/run_outcomes.jsonl: condition B,
reached, b_parsed false), each with session.json, summary.txt, usage.json and meta.json.

count (free: the token counting endpoint). For each failed run:
  (a) the length of its stored summary in output tokens: count_tokens of the conversation with the summary
      as the last assistant turn, minus count_tokens of the same conversation without it;
  (b) the rebuild check. The requests were not stored; only AIOpsLab's session file was. Each call's request
      is rebuilt as ModelAgent sent it (src/evtrace/agent.py): the system prompt from AIOpsLab's own template
      and problem at the pinned commit, the task instructions, each turn with the ReAct instruction appended,
      the empty-reply marker, the cache marks, and the summary instruction of Condition B. The input tokens of
      every rebuilt request are counted and summed; the run rebuilds exactly when that sum equals the input
      tokens the API billed for the run (usage.json: input + cache read + cache creation) and the number of
      calls equals usage.json's count.
replay (paid, capped). Only when every failed run rebuilds exactly: the summary call of each run is sent again
from its rebuilt request with the same model and an output limit of 8,192 tokens (fixed in the ruling of
Nov 11, 2026, before any replay). No call is repeated on a cut-off reply. The full response, its stop
reason and usage are stored; each reply is parsed with the registered evtrace.locate.parse_summary.
Spending stops before a call once the estimate reaches the budget (prices of Nov 6, 2026, pricing page).
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.request

sys.path.insert(0, os.getcwd())  # the AIOpsLab checkout

from evtrace import locate  # noqa: E402
from evtrace.agent import EMPTY_REPLY, RESP_INSTR, SUMMARY_B  # noqa: E402

API = "https://api.anthropic.com/v1"
PRICES = {"claude-haiku-5-5": (0.10, 0.50), "claude-sonnet-5-5": (2.0, 10.0)}  # USD per million, Nov 6, 2026
REPLAY_MAX_TOKENS = 8192


def post(path: str, body: dict) -> dict:
    key = os.environ["LLM_API_KEY"]
    for attempt in range(8):
        req = urllib.request.Request(f"{API}/{path}", data=json.dumps(body).encode(), method="POST", headers={
            "content-type": "application/json", "x-api-key": key, "anthropic-version": "2023-06-01"})
        try:
            with urllib.request.urlopen(req, timeout=600) as r:
                return json.load(r)
        except urllib.error.HTTPError as e:
            if e.code in (429, 500, 502, 503, 529) and attempt < 7:
                time.sleep(min(60, 2 ** attempt * 3))
                continue
            raise RuntimeError(f"HTTP {e.code}: {e.read().decode('utf-8', 'replace')[:500]}") from e
    raise RuntimeError("unreachable")


def system_prompt(problem_id: str) -> tuple[str, str]:
    """System prompt and task instructions as ModelAgent.init_context built them."""
    from aiopslab.orchestrator.problems.registry import ProblemRegistry
    from clients.utils.templates import DOCS

    prob = ProblemRegistry().get_problem_instance(problem_id)
    desc, instr, apis = prob.get_task_description(), prob.get_instructions(), prob.get_available_actions()

    def fmt(d):
        return "\n\n".join(f"{k}\n{v}" for k, v in d.items())
    system = DOCS.format(prob_desc=desc,
                         telemetry_apis=fmt({k: v for k, v in apis.items() if "exec_shell" not in k and "submit" not in k}),
                         shell_api=fmt({k: v for k, v in apis.items() if "exec_shell" in k}),
                         submit_api=fmt({k: v for k, v in apis.items() if "submit" in k}))
    return system, instr


def conversation(session: dict, instructions: str) -> tuple[list[list[dict]], list[dict]]:
    """Message lists of every call (the agent's steps, then the summary) and the final transcript."""
    msgs: list[dict] = [{"role": "user", "content": instructions}]

    def user(text: str) -> None:
        if msgs and msgs[-1]["role"] == "user":
            msgs[-1]["content"] += "\n\n" + text
        else:
            msgs.append({"role": "user", "content": text})

    calls, action_instr = [], "Please take the next action"
    for item in session.get("trace", []):
        if item.get("role") == "assistant":
            user(f"{action_instr}\n\n{RESP_INSTR}")
            calls.append([dict(m) for m in msgs])
            msgs.append({"role": "assistant", "content": str(item.get("content", ""))})
        elif item.get("role") == "env":
            action_instr = str(item.get("content", "")) + "\n" + "Please take the next action"
    user(SUMMARY_B)
    calls.append([dict(m) for m in msgs])
    return calls, msgs


def body(model: str, system: str, msgs: list[dict], max_tokens: int) -> dict:
    """The request body exactly as ModelAgent._call builds it."""
    msgs = [dict(m) for m in msgs]
    for m in msgs:
        if isinstance(m["content"], str) and not m["content"].strip():
            m["content"] = EMPTY_REPLY
    if len(msgs) >= 2:
        prev = msgs[-2]
        prev["content"] = [{"type": "text", "text": prev["content"], "cache_control": {"type": "ephemeral"}}]
    return {"model": model, "max_tokens": max_tokens,
            "system": [{"type": "text", "text": system, "cache_control": {"type": "ephemeral"}}], "messages": msgs}


def count(b: dict) -> int:
    return post("messages/count_tokens", {k: v for k, v in b.items() if k != "max_tokens"})["input_tokens"]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("mode", choices=["count", "replay"])
    ap.add_argument("runs")
    ap.add_argument("out")
    ap.add_argument("--budget-usd", type=float, default=5.0)
    ap.add_argument("--count-file", help="replay only: the count.jsonl of the count mode; every run must be exact")
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)
    if a.mode == "replay":
        checked = [json.loads(l) for l in open(a.count_file, encoding="utf-8")] if a.count_file else []
        if not checked or not all(r.get("exact") for r in checked):
            print("no replay: not every failed run rebuilds exactly (P4 e)")
            return 0
    runs = sorted(d for d in os.listdir(a.runs) if os.path.exists(os.path.join(a.runs, d, "session.json")))
    rows, spent = [], 0.0
    prompts: dict[str, tuple[str, str]] = {}
    for rid in runs:
        d = os.path.join(a.runs, rid)
        meta = json.load(open(os.path.join(d, "meta.json")))
        usage = json.load(open(os.path.join(d, "usage.json")))
        summary = open(os.path.join(d, "summary.txt"), encoding="utf-8").read()
        session = json.load(open(os.path.join(d, "session.json"), encoding="utf-8"))
        row = {"run_id": rid, "model": meta["model"], "problem_id": meta["problem_id"], "summary_chars": len(summary),
               "billed_input": usage.get("input_tokens", 0) + usage.get("cache_read_input_tokens", 0)
               + usage.get("cache_creation_input_tokens", 0), "billed_output": usage.get("output_tokens", 0),
               "billed_calls": usage.get("calls")}
        try:
            if meta["problem_id"] not in prompts:
                prompts[meta["problem_id"]] = system_prompt(meta["problem_id"])
            system, instr = prompts[meta["problem_id"]]
            calls, _ = conversation(session, instr)
            if a.mode == "count":
                inputs = [count(body(meta["model"], system, c, 1024)) for c in calls]
                row.update({"rebuilt_calls": len(calls), "rebuilt_input": sum(inputs)})
                row["exact"] = row["rebuilt_input"] == row["billed_input"] and row["rebuilt_calls"] == row["billed_calls"]
                if summary.strip():
                    last = calls[-1]
                    with_summary = last + [{"role": "assistant", "content": summary.rstrip()}]
                    row["summary_tokens"] = count(body(meta["model"], system, with_summary, 1)) - inputs[-1]
                else:
                    row["summary_tokens"] = 0
            else:
                p_in, p_out = PRICES[meta["model"]]
                b = body(meta["model"], system, calls[-1], REPLAY_MAX_TOKENS)
                est = (count(b) * p_in * 1.25 + REPLAY_MAX_TOKENS * p_out) / 1e6  # worst case: full write, full output
                if spent + est > a.budget_usd:
                    row["replay"] = "not sent: budget"
                else:
                    out = post("messages", b)
                    u = out.get("usage", {})
                    cost = ((u.get("input_tokens", 0) + 0.1 * u.get("cache_read_input_tokens", 0)
                             + 1.25 * u.get("cache_creation_input_tokens", 0)) * p_in + u.get("output_tokens", 0) * p_out) / 1e6
                    spent += cost
                    text = "".join(x.get("text", "") for x in out.get("content", []) if x.get("type") == "text")
                    parsed = locate.parse_summary(text)
                    row.update({"replay": "sent", "stop_reason": out.get("stop_reason"), "usage": u, "cost_usd": round(cost, 5),
                                "parsed": bool(parsed and parsed.get("claims")), "claims": len((parsed or {}).get("claims") or [])})
                    with open(os.path.join(a.out, "replay_responses.jsonl"), "a", encoding="utf-8") as fh:
                        fh.write(json.dumps({"run_id": rid, "request": b, "response": out}) + "\n")
        except Exception as e:  # recorded; such a run cannot be rebuilt
            row["error"] = f"{type(e).__name__}: {str(e)[:300]}"
            row["exact"] = False
        rows.append(row)
        print(json.dumps(row), flush=True)
    with open(os.path.join(a.out, f"{a.mode}.jsonl"), "w", encoding="utf-8") as fh:
        for r in rows:
            fh.write(json.dumps(r, sort_keys=True) + "\n")
    print(f"spent {spent:.4f} USD", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
