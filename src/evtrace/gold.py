"""Gold labels by construction: claims whose true label is known because they are built from the
exposure log with a fixed rule (the replacement for a second annotator, revised design of Nov 5, 2026).

Each template writes a claim from real exposed items and states its label before any verifier runs.
These claims measure the verifier on known cases; they do not replace human labels of real agent
claims, which the author re-codes blind on a 20 percent sample."""
from __future__ import annotations

import copy
import random
from datetime import timedelta

from .record import parse_time

TEMPLATES = {
    "T1": "supported",          # metric value stated exactly, linked to its sample
    "T2": "contradicted",       # metric value changed, linked to the true sample
    "T3": "unsupported",        # a service that appears in no exposed item, no link
    "T4": "unsupported",        # linked only to an item that was never exposed
    "T5": "partly_supported",   # two services named, evidence linked for one
    "T6": "supported",          # span of a service in its window, linked to the span
    "T7": "supported",          # root cause derived from a supported observation
    "T8": "unsupported",        # root cause derived from an unsupported observation
}


def _window(ts: str | None) -> dict | None:
    t = parse_time(ts)
    if not t:
        return None
    return {"start": (t - timedelta(minutes=2)).isoformat(), "end": (t + timedelta(minutes=2)).isoformat()}


def build(run_id: str, problem_id: str, evidence: list[dict], final_step: int, seed: int,
          per_template: int = 2) -> tuple[dict, dict[str, str]]:
    """Return (record, gold) for one run: a provenance record of constructed claims and their labels."""
    rng = random.Random(f"{seed}:{run_id}")
    ev = copy.deepcopy(evidence)
    exposed = [e for e in ev if e.get("exposed_at_steps") and min(e["exposed_at_steps"]) < final_step]
    metrics = [e for e in exposed if e["kind"] == "metric_sample" and e.get("service")]
    spans = [e for e in exposed if e["kind"] == "span" and e.get("service")]
    services = sorted({e["service"] for e in exposed if e.get("service")})
    claims: list[dict] = []
    gold: dict[str, str] = {}

    def add(template: str, claim: dict) -> str:
        cid = f"g{len(claims) + 1}"
        claim = {"claim_id": cid, **claim}
        claims.append(claim)
        gold[cid] = TEMPLATES[template]
        claim.setdefault("links", [])
        claim["template"] = template
        return cid

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
        unsupported_obs.append(add("T3", {"type": "observation", "services": [ghost],
                                          "text": f"{ghost} returned errors", "links": []}))
        hidden_id = f"h{len(claims) + 1}"
        ev.append({"evidence_id": hidden_id, "kind": "command_output", "command": "collected, not shown",
                   "text": "collected but never returned to the agent", "exposed_at_steps": []})
        add("T4", {"type": "observation", "text": "an item the agent never saw shows the fault",
                   "links": [{"link_type": "supports", "target": hidden_id}]})
        if len(services) >= 1 and (spans or metrics):
            item = rng.choice(spans or metrics)
            other = rng.choice([s for s in services if s != item["service"]] or [f"svc-{rng.randrange(10**6):06d}"])
            add("T5", {"type": "observation", "services": [item["service"], other],
                       "text": f"{item['service']} and {other} both showed the fault",
                       "links": [{"link_type": "partly_supports", "target": item["evidence_id"]}]})
        if spans:
            s = rng.choice(spans)
            base = {"type": "observation", "services": [s["service"]], "window": _window(s.get("timestamp"))}
            base = {k: v for k, v in base.items() if v is not None}
            supported_obs.append(add("T6", {**base, "text": f"{s['service']} served {s.get('operation', 'a request')}",
                                            "links": [{"link_type": "supports", "target": s["evidence_id"]}]}))
    for obs in supported_obs[:per_template]:
        add("T7", {"type": "root_cause", "text": f"root cause follows from {obs}",
                   "links": [{"link_type": "derived_from", "target": obs}]})
    for obs in unsupported_obs[:per_template]:
        add("T8", {"type": "root_cause", "text": f"root cause follows from {obs}",
                   "links": [{"link_type": "derived_from", "target": obs}]})
    templates = {c["claim_id"]: c.pop("template") for c in claims}
    record = {"run_id": run_id, "problem_id": problem_id, "final_step": final_step, "evidence": ev, "claims": claims}
    return record, {cid: f"{gold[cid]}|{templates[cid]}" for cid in gold}
