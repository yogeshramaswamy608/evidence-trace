"""Stages 2 and 3 of the verifier and the label aggregation (manuscript Section 4)."""
from __future__ import annotations

import json
import os
import urllib.request
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from importlib import resources
from typing import Protocol

from . import rules
from .record import SUPPORT_LINKS, Record, parse_time

# Tolerances fixed in the rubric before labeling starts (manuscript Section 5.6).
TIME_TOLERANCE = timedelta(seconds=60)
VALUE_TOLERANCE = 0.05  # relative

VERDICTS = ("entails", "partly", "contradicts", "unrelated")

# The agent models of the study (manuscript Section 5.2); the Stage 3 judge may be none of them.
AGENT_MODELS = ("claude-sonnet-5-5", "claude-haiku-5-5")


@dataclass
class ClaimResult:
    claim_id: str
    label: str | None            # None for recommendations, which are not checkable
    reasons: list[str] = field(default_factory=list)


class Judge(Protocol):
    def __call__(self, claim: dict, items: list[dict]) -> str: ...


def render(item: dict) -> str:
    """Render one evidence item as one line of text for the judge."""
    keys = ("kind", "service", "operation", "timestamp", "error", "status", "duration_us",
            "series", "labels", "value", "source", "command", "text", "trace_id", "span_id")
    return "; ".join(f"{k}={item[k]}" for k in keys if k in item)


def consistency(claim: dict, item: dict, link_type: str) -> list[str]:
    """Stage 2: compare the claim's services, time window and value with one linked item.

    Returns reason codes for each failed comparison; an empty list means consistent."""
    out = []
    services = claim.get("services") or []
    if services and item.get("service") and item["service"] not in services:
        out.append("S2_SERVICE_MISMATCH")
    window = claim.get("window")
    ts = parse_time(item.get("timestamp"))
    if window and ts:
        start, end = parse_time(window["start"]), parse_time(window["end"])
        if ts < start - TIME_TOLERANCE or ts > end + TIME_TOLERANCE:
            out.append("S2_OUTSIDE_WINDOW")
    if "value" in claim and "value" in item:
        ref = abs(item["value"]) or 1.0
        if abs(claim["value"] - item["value"]) / ref > VALUE_TOLERANCE:
            out.append("S2_VALUE_MISMATCH")
    if link_type == "partly_supports" and services and len(services) > 1:
        out = [r for r in out if r != "S2_SERVICE_MISMATCH"]
    return out


def stage2_judge(claim: dict, items: list[dict]) -> str:
    """Baseline judge using Stage 2 only: no model, decided by the consistency checks."""
    if not items:
        return "unrelated"
    checks = [consistency(claim, it, "supports") for it in items]
    if any("S2_VALUE_MISMATCH" in c and "S2_SERVICE_MISMATCH" not in c for c in checks):
        return "contradicts"
    if not any(not c for c in checks):
        return "unrelated"
    covered = {it.get("service") for it, c in zip(items, checks) if not c}
    services = set(claim.get("services") or [])
    return "partly" if services and not services <= covered else "entails"


class ModelJudge:
    """Stage 3 judge: one model call per claim with the frozen prompt and only the linked items.

    The key is read from the environment variable LLM_API_KEY and never stored. The model
    must differ from every agent model in the study (manuscript Section 4), and every request
    and response is appended with its UTC time to log_path when one is given (Section 4, draft 0.3)."""

    def __init__(self, model: str, endpoint: str = "https://api.anthropic.com/v1/messages",
                 max_tokens: int = 16, agent_models: tuple[str, ...] = AGENT_MODELS,
                 log_path: str | None = None) -> None:
        if model in agent_models:
            raise ValueError(f"judge model {model} is also an agent model; the judge must differ")
        self.model, self.endpoint, self.max_tokens, self.log_path = model, endpoint, max_tokens, log_path
        self.prompt = resources.files("evtrace").joinpath("data/judge_prompt.txt").read_text()
        self.usage = {"calls": 0, "input_tokens": 0, "output_tokens": 0}

    def __call__(self, claim: dict, items: list[dict]) -> str:
        key = os.environ.get("LLM_API_KEY")
        if not key:
            raise RuntimeError("LLM_API_KEY is not set")
        evidence = "\n".join(f"[{i + 1}] {render(it)}" for i, it in enumerate(items)) or "(none)"
        body = {"model": self.model, "max_tokens": self.max_tokens,
                "system": self.prompt,
                "messages": [{"role": "user", "content": f"CLAIM: {claim['text']}\nEVIDENCE:\n{evidence}"}]}
        req = urllib.request.Request(self.endpoint, data=json.dumps(body).encode(), method="POST", headers={
            "content-type": "application/json", "x-api-key": key, "anthropic-version": "2023-06-01"})
        with urllib.request.urlopen(req, timeout=120) as resp:
            out = json.load(resp)
        if self.log_path:
            with open(self.log_path, "a", encoding="utf-8") as f:
                f.write(json.dumps({"utc": datetime.now(timezone.utc).isoformat(), "claim_id": claim.get("claim_id"),
                                    "request": body, "response": out}) + "\n")
        self.usage["calls"] += 1
        for k in ("input_tokens", "output_tokens"):
            self.usage[k] += out.get("usage", {}).get(k, 0)
        word = "".join(b.get("text", "") for b in out.get("content", [])).strip().lower().split()
        verdict = word[0].strip(".") if word else ""
        return verdict if verdict in VERDICTS else "unrelated"


def verify(record: Record, judge: Judge = stage2_judge) -> dict[str, ClaimResult]:
    """Label every claim of a record: supported, partly_supported, unsupported or contradicted."""
    violations = rules.check(record)
    if any(v.rule == "SCHEMA" for v in violations):
        return {cid: ClaimResult(cid, "unsupported", ["S1_SCHEMA"]) for cid in record.claims}
    failed = {}
    for v in violations:
        failed.setdefault(v.claim_id, []).append(f"S1_{v.rule}")

    direct: dict[str, ClaimResult] = {}
    for cid, c in record.claims.items():
        if c["type"] == "recommendation":
            direct[cid] = ClaimResult(cid, None, ["NOT_CHECKABLE"])
            continue
        links = [l for l in c["links"] if l["link_type"] in SUPPORT_LINKS + ("contradicts",)
                 and rules.exposed_before_final(record, l["target"])]
        items = [record.evidence[l["target"]] for l in links]
        reasons = list(failed.get(cid, []))
        s2 = [r for l, it in zip(links, items) for r in consistency(c, it, l["link_type"])]
        reasons += sorted(set(s2))
        verdict = judge(c, items) if items else "unrelated"
        reasons.append(f"S3_{verdict.upper()}")
        if verdict == "contradicts" or any(l["link_type"] == "contradicts" for l in links):
            label = "contradicted"
        elif not items or verdict == "unrelated":
            label = "unsupported"
        elif verdict == "entails" and not s2 and all(l["link_type"] == "supports" for l in links):
            label = "supported"
        else:
            label = "partly_supported"
        direct[cid] = ClaimResult(cid, label, reasons)

    # Inferences and root-cause claims inherit support through derived_from links.
    def resolve(cid: str, seen: frozenset = frozenset()) -> str | None:
        res, c = direct[cid], record.claims[cid]
        parents = [l["target"] for l in c["links"] if l["link_type"] == "derived_from" and l["target"] in record.claims]
        if not parents or res.label in (None, "contradicted") or cid in seen:
            return res.label
        labels = [resolve(p, seen | {cid}) for p in parents]
        own = res.label != "unsupported"
        if any(lab in ("unsupported", "contradicted") for lab in labels):
            res.reasons.append("INHERITED_UNSUPPORTED_PARENT")
            return "partly_supported" if own else "unsupported"
        if all(lab == "supported" for lab in labels):
            res.reasons.append("INHERITED_SUPPORTED_PARENTS")
            return res.label if own else "supported"
        res.reasons.append("INHERITED_PARTLY_SUPPORTED_PARENT")
        return "partly_supported"

    final = {cid: resolve(cid) for cid in direct}
    for cid, label in final.items():
        direct[cid].label = label
        direct[cid].reasons = list(dict.fromkeys(direct[cid].reasons))
    return direct
