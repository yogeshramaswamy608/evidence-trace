"""Turn a Condition B summary into a provenance record by resolving each link locator to the
evidence item the agent was shown (manuscript Sections 3 and 5.4)."""
from __future__ import annotations

import json
import re

from .record import digest, normalize_span_id, normalize_trace_id


def parse_summary(text: str) -> dict | None:
    """Return the JSON object of a Condition B summary, or None when there is none."""
    text = (text or "").strip()
    fenced = re.search(r"```(?:json)?\s*(\{.*\})\s*```", text, re.S)
    candidate = fenced.group(1) if fenced else text[text.find("{"): text.rfind("}") + 1]
    try:
        obj = json.loads(candidate)
    except (ValueError, TypeError):
        return None
    return obj if isinstance(obj, dict) and isinstance(obj.get("claims"), list) else None


def resolve(locator: str, evidence: list[dict]) -> str | None:
    """Return the evidence_id a locator names, or None when no exposed item matches."""
    kind, _, rest = locator.partition(":")
    kind, rest = kind.strip().lower(), rest.strip()
    if kind == "span" and "/" in rest:
        t, s = rest.split("/", 1)
        try:
            t, s = normalize_trace_id(t), normalize_span_id(s)
        except ValueError:
            return None
        return next((e["evidence_id"] for e in evidence if e["kind"] == "span"
                     and e.get("trace_id") == t and e.get("span_id") == s), None)
    if kind in ("log", "cmd"):
        want = "log_record" if kind == "log" else "command_output"
        d = digest(rest)
        exact = next((e["evidence_id"] for e in evidence if e["kind"] == want and e.get("text_digest") == d), None)
        if exact:
            return exact
        return next((e["evidence_id"] for e in evidence if e["kind"] == want and rest and rest in e.get("text", "")), None)
    if kind == "metric":
        series, _, ts = rest.partition("@")
        return next((e["evidence_id"] for e in evidence if e["kind"] == "metric_sample"
                     and e.get("series") == series.strip() and (not ts or e.get("timestamp") == ts.strip())), None)
    return None


def to_record(summary: dict, run_id: str, problem_id: str, evidence: list[dict], final_step: int) -> tuple[dict, list[str]]:
    """Return (record, unresolved locators). Unresolved links point to a placeholder that is never
    exposed, so rule R2 flags them, as the protocol requires."""
    claim_ids = {c.get("claim_id") for c in summary.get("claims", [])}
    unresolved, claims = [], []
    for c in summary.get("claims", []):
        links = []
        for l in c.get("links", []) or []:
            target, ltype = str(l.get("target", "")), l.get("link_type", "")
            if ltype == "derived_from" or target in claim_ids:
                links.append({"link_type": ltype, "target": target})
                continue
            eid = resolve(target, evidence)
            if eid is None:
                unresolved.append(target)
                eid = f"unresolved:{len(unresolved)}"
            links.append({"link_type": ltype, "target": eid})
        claim = {"claim_id": str(c.get("claim_id")), "text": str(c.get("text", "")), "type": c.get("type"),
                 "links": links}
        for k in ("no_evidence_found", "services"):
            if k in c:
                claim[k] = c[k]
        claims.append(claim)
    record = {"run_id": run_id, "problem_id": problem_id, "final_step": final_step,
              "evidence": evidence, "claims": claims}
    return record, unresolved
