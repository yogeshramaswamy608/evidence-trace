"""Build the RQ2 claim bundles of the 300 sampled claims (P1, deviations 3 and 5, Nov 12, 2026).

Usage: python scripts/rq2_prepare.py QUEUE_KEY.json ARTIFACT_DIR CORRECTED_DIR OUT_DIR
Writes OUT_DIR/bundle_corrected.jsonl and OUT_DIR/bundle_registered.jsonl, one line per sampled claim:
key, run_id, claim_id, split, model, condition, self_report (the fixed rule of scripts/analyze_labels.py),
link_source (agent or recovered), a trimmed provenance record that verify() labels exactly as it labels the
full record (the claim, its derived_from ancestors in Condition B, and only the evidence items they link to),
and the capped pool of the link-blind baseline (50 items, deviation 3). Condition A links are recovered with
evtrace.recover at its FROZEN values; Condition B links are the agent's own, as resolved in record.json.
Evidence items keep only the fields of the provenance schema (the corrected reading's parent_span is dropped).
Nothing here reads a label.
"""
import json
import os
import re
import sys

from evtrace import recover

SELF_REPORT = re.compile(r"\b(submitted|classified)\b", re.IGNORECASE)
SCHEMA_FIELDS = ("evidence_id", "kind", "trace_id", "span_id", "service", "operation", "timestamp", "error", "status",
                 "duration_us", "source", "line_index", "text_digest", "text", "series", "labels", "value", "command",
                 "exposed_at_steps")


def clean(e: dict) -> dict:
    return {k: e[k] for k in SCHEMA_FIELDS if k in e}


def ancestors(claims: dict, cid: str, seen: set) -> None:
    if cid in seen or cid not in claims:
        return
    seen.add(cid)
    for l in claims[cid]["links"]:
        if l["link_type"] == "derived_from":
            ancestors(claims, l["target"], seen)


def main(key_path: str, art: str, cdir: str, out: str, outcomes: str = "data/runs/run_outcomes.jsonl") -> int:
    os.makedirs(out, exist_ok=True)
    art_of = {json.loads(l)["run_id"]: json.loads(l)["artifact"] for l in open(outcomes, encoding="utf-8")}
    queue = [q for q in json.load(open(key_path, encoding="utf-8"))["queue"] if not q["source"].get("is_gold")]
    assert len(queue) == 300
    k, t = recover.FROZEN["k"], recover.FROZEN["min_score"]
    for version in ("corrected", "registered"):
        with open(os.path.join(out, f"bundle_{version}.jsonl"), "w", encoding="utf-8") as fh:
            for q in sorted(queue, key=lambda q: q["key"]):
                s = q["source"]
                stored = json.load(open(os.path.join(art, str(art_of[s["run_id"]]), s["run_id"], "record.json"), encoding="utf-8"))
                rec = stored if version == "registered" else json.load(open(os.path.join(cdir, s["run_id"] + ".json"), encoding="utf-8"))
                if s["condition"] == "B":
                    claims = {c["claim_id"]: c for c in stored["claims"]}
                    keep: set = set()
                    ancestors(claims, s["claim_id"], keep)
                    kept = [claims[c] for c in sorted(keep)]
                    assert claims[s["claim_id"]]["text"] == s["text"]
                    source = "agent"
                else:
                    kept = [recover.recover({"claim_id": s["claim_id"], "text": s["text"], "type": s["type"]}, rec, k, t)]
                    for c in kept:
                        c.pop("recovered")
                    source = "recovered"
                ids = {l["target"] for c in kept for l in c["links"] if l["link_type"] != "derived_from"}
                ev = [clean(e) for e in rec["evidence"] if e["evidence_id"] in ids]
                record = {"run_id": s["run_id"], "problem_id": stored["problem_id"], "final_step": stored["final_step"],
                          "evidence": ev, "claims": kept}
                pool = [clean(e) for e in recover.pool(s["text"], rec, cap=50)]
                fh.write(json.dumps({"key": q["key"], "run_id": s["run_id"], "claim_id": s["claim_id"], "split": s["split"],
                                     "model": s["model"], "condition": s["condition"], "type": s["type"],
                                     "self_report": bool(SELF_REPORT.search(s["text"])), "link_source": source,
                                     "record": record, "pool": pool}, sort_keys=True) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(*sys.argv[1:]))
