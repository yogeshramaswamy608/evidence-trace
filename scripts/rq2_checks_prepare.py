"""Trimmed records of the verifier's check sets for RQ2 (P2 d, Nov 12, 2026).
Usage: python scripts/rq2_checks_prepare.py ARTIFACT_DIR CORRECTED_DIR OUT_DIR
check_set_v1 (registered gold.py) is paired with the stored records, check_set_v2 (gold_v2.py) with the corrected
records; each line keeps the claim, its derived_from ancestors and the evidence items they link to, so verify()
labels it as it would label the full record."""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from rq2_prepare import ancestors, clean  # noqa: E402


def main(art: str, cdir: str, out: str, outcomes: str = "data/runs/run_outcomes.jsonl") -> int:
    art_of = {json.loads(l)["run_id"]: json.loads(l)["artifact"] for l in open(outcomes, encoding="utf-8")}
    for name in ("v1", "v2"):
        rows = [json.loads(l) for l in open(f"data/check_sets/check_set_{name}.jsonl", encoding="utf-8")]
        by_run: dict = {}
        for r in rows:
            by_run.setdefault(r["run_id"], []).append(r)
        with open(os.path.join(out, f"checks_{name}.jsonl"), "w", encoding="utf-8") as fh:
            for rid in sorted(by_run):
                rec = json.load(open(os.path.join(art, str(art_of[rid]), rid, "record.json") if name == "v1"
                                     else os.path.join(cdir, rid + ".json"), encoding="utf-8"))
                claims = {r["claim"]["claim_id"]: r["claim"] for r in by_run[rid]}
                hidden = {e["evidence_id"]: e for r in by_run[rid] for e in r["hidden"]}
                evidence = {e["evidence_id"]: e for e in rec["evidence"]} | hidden
                for r in by_run[rid]:
                    keep: set = set()
                    ancestors(claims, r["claim"]["claim_id"], keep)
                    kept = [claims[c] for c in sorted(keep)]
                    ids = {l["target"] for c in kept for l in c["links"] if l["link_type"] != "derived_from"}
                    record = {"run_id": rid, "problem_id": rec["problem_id"], "final_step": rec["final_step"],
                              "evidence": [clean(evidence[i]) for i in sorted(ids) if i in evidence], "claims": kept}
                    fh.write(json.dumps({"run_id": rid, "claim_id": r["claim"]["claim_id"], "label": r["label"],
                                         "template": r["template"], "record": record}, sort_keys=True) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(*sys.argv[1:]))
