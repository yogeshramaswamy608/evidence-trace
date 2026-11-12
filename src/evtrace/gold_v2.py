"""Gold labels by construction, version 2, written Nov 12, 2026 beside the registered gold.py (deviation 2).

Rule of this version: a template's label must follow from the recorded fields of the item it is built from,
read from the corrected record (evtrace.exposure_v2, deviation 5), or from the construction alone. A template
that cannot meet the rule is dropped. The registered gold.py stays byte for byte and the old check set is
scored beside the new one.

Why. The labeling queue's check claims came from two templates of gold.py. T5 ("A and B both showed the
fault", built as partly supported) states the state of a second service that its one linked item cannot show,
and in all 18 queue claims the linked item of A carries no fault signal either. T6 ("A served OP", built as
supported) says "served" of any span of A, also when the span is the caller's side of a call or an internal
step of A, which a span's own fields cannot tell apart (scripts/check_claim_defects.py).

Templates of version 2:
  T1, T2   as in gold.py (metric value stated exactly, or changed); no main run exposed a metric sample, so
           neither yields a claim (docs/defect_counts.json)
  T3, T4   as in gold.py; their labels follow from the construction alone (a service in no exposed item; a
           link to an item never exposed)
  T5       dropped: the second service's state is not in the linked item
  T6       replaced by V1: "A recorded a span OP that took D ms", D the span's own duration      supported
  V2       the same sentence with D multiplied by 1.5, 2 or 3                                      contradicted
  V3       "A's span OP ended with an error", built only from a span whose has_error is True       supported
  V4       the same sentence, built only from a span whose has_error is False                     contradicted
  T7, T8   as in gold.py, derived from V1/V3 claims (T7) or from T3 claims (T8)
No template yields a partly supported claim under this rule; the check set says so.
"""
from __future__ import annotations

import copy
import random

from .gold import _window

TEMPLATES = {
    "T1": "supported", "T2": "contradicted", "T3": "unsupported", "T4": "unsupported",
    "V1": "supported", "V2": "contradicted", "V3": "supported", "V4": "contradicted",
    "T7": "supported", "T8": "unsupported",
}


def _ms(us: float) -> str:
    return f"{us / 1000:g}"


def build(run_id: str, problem_id: str, evidence: list[dict], final_step: int, seed: int,
          per_template: int = 1) -> tuple[dict, dict[str, str]]:
    """Return (record, gold) for one run from its corrected evidence; gold maps claim id to 'label|template'."""
    rng = random.Random(f"{seed}:v2:{run_id}")
    ev = copy.deepcopy(evidence)
    exposed = [e for e in ev if e.get("exposed_at_steps") and min(e["exposed_at_steps"]) < final_step]
    metrics = [e for e in exposed if e["kind"] == "metric_sample" and e.get("service")]
    spans = [e for e in exposed if e["kind"] == "span" and e.get("service") and e.get("operation")
             and e.get("duration_us") is not None and "error" in e]
    err_spans = [s for s in spans if s["error"] is True]
    ok_spans = [s for s in spans if s["error"] is False]
    claims: list[dict] = []
    gold: dict[str, str] = {}

    def add(template: str, claim: dict) -> str:
        cid = f"v{len(claims) + 1}"
        claims.append({"claim_id": cid, "links": [], **claim, "template": template})
        gold[cid] = TEMPLATES[template]
        return cid

    def span_base(s: dict) -> dict:
        base = {"type": "observation", "services": [s["service"]], "window": _window(s.get("timestamp"))}
        return {k: v for k, v in base.items() if v is not None}

    supported_obs, unsupported_obs = [], []
    for _ in range(per_template):
        if metrics:
            m = rng.choice(metrics)
            base = {"type": "observation", "services": [m["service"]], "window": _window(m.get("timestamp"))}
            base = {k: v for k, v in base.items() if v is not None}
            supported_obs.append(add("T1", {**base, "text": f"{m['series']} on {m['service']} was {m['value']:g}",
                                            "value": m["value"], "links": [{"link_type": "supports", "target": m["evidence_id"]}]}))
            wrong = m["value"] * rng.choice((1.5, 2.0, 3.0)) if m["value"] else rng.choice((5.0, 10.0))
            add("T2", {**base, "text": f"{m['series']} on {m['service']} was {wrong:g}", "value": wrong,
                       "links": [{"link_type": "supports", "target": m["evidence_id"]}]})
        ghost = f"svc-{rng.randrange(10**6):06d}"
        unsupported_obs.append(add("T3", {"type": "observation", "services": [ghost], "text": f"{ghost} returned errors"}))
        hidden_id = f"h{len(claims) + 1}"
        ev.append({"evidence_id": hidden_id, "kind": "command_output", "command": "collected, not shown",
                   "text": "collected but never returned to the agent", "exposed_at_steps": []})
        add("T4", {"type": "observation", "text": "an item the agent never saw shows the fault",
                   "links": [{"link_type": "supports", "target": hidden_id}]})
        if spans:
            s = rng.choice(spans)
            link = [{"link_type": "supports", "target": s["evidence_id"]}]
            supported_obs.append(add("V1", {**span_base(s), "links": link,
                                            "text": f"{s['service']} recorded a span {s['operation']} that took {_ms(s['duration_us'])} ms"}))
            s2 = rng.choice(spans)
            wrong = s2["duration_us"] * rng.choice((1.5, 2.0, 3.0)) if s2["duration_us"] else rng.choice((5000.0, 10000.0))
            add("V2", {**span_base(s2), "links": [{"link_type": "supports", "target": s2["evidence_id"]}],
                       "text": f"{s2['service']} recorded a span {s2['operation']} that took {_ms(wrong)} ms"})
        if err_spans:
            s = rng.choice(err_spans)
            supported_obs.append(add("V3", {**span_base(s), "links": [{"link_type": "supports", "target": s["evidence_id"]}],
                                            "text": f"{s['service']}'s span {s['operation']} ended with an error"}))
        if ok_spans:
            s = rng.choice(ok_spans)
            add("V4", {**span_base(s), "links": [{"link_type": "supports", "target": s["evidence_id"]}],
                       "text": f"{s['service']}'s span {s['operation']} ended with an error"})
    for obs in supported_obs[:per_template]:
        add("T7", {"type": "root_cause", "text": f"root cause follows from {obs}",
                   "links": [{"link_type": "derived_from", "target": obs}]})
    for obs in unsupported_obs[:per_template]:
        add("T8", {"type": "root_cause", "text": f"root cause follows from {obs}",
                   "links": [{"link_type": "derived_from", "target": obs}]})
    templates = {c["claim_id"]: c.pop("template") for c in claims}
    record = {"run_id": run_id, "problem_id": problem_id, "final_step": final_step, "evidence": ev, "claims": claims}
    return record, {cid: f"{gold[cid]}|{templates[cid]}" for cid in gold}
