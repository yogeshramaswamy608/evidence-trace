"""Build the verifier's check sets for research question 2 (P2 d, deviation 2).

Usage: python scripts/build_check_sets.py ARTIFACT_DIR CORRECTED_DIR OUT_DIR
Writes OUT_DIR/check_set_v1.jsonl (registered gold.py on each stored record.json) and
OUT_DIR/check_set_v2.jsonl (gold_v2.py on each corrected record), one line per claim:
run_id, claim (as built), label and template. Seed 20261105, one claim per template per run, every reached
main run. The verifier is scored on v2, with v1's score beside it. Nothing here reads a human label.
"""
import json
import os
import sys
from collections import Counter

from evtrace import gold, gold_v2


def main(art: str, cdir: str, out: str, outcomes: str = "data/runs/run_outcomes.jsonl") -> int:
    os.makedirs(out, exist_ok=True)
    counts = {}
    for name, mod in (("v1", gold), ("v2", gold_v2)):
        tally = Counter()
        with open(os.path.join(out, f"check_set_{name}.jsonl"), "w", encoding="utf-8") as fh:
            for line in open(outcomes, encoding="utf-8"):
                o = json.loads(line)
                if not o["reached"]:
                    continue
                path = (os.path.join(art, str(o["artifact"]), o["run_id"], "record.json") if name == "v1"
                        else os.path.join(cdir, o["run_id"] + ".json"))
                rec = json.load(open(path, encoding="utf-8"))
                try:
                    built, g = mod.build(o["run_id"], o["problem_id"], rec["evidence"], rec.get("final_step", 99), 20261105, per_template=1)
                except ValueError:  # the registered gold.py fails on a shifted start time (deviation 5); the queue build skipped such runs too
                    tally[("run skipped", "ValueError")] += 1
                    continue
                for c in built["claims"]:
                    label, template = g[c["claim_id"]].split("|")
                    tally[(template, label)] += 1
                    fh.write(json.dumps({"run_id": o["run_id"], "claim": c, "label": label, "template": template,
                                         "hidden": [e for e in built["evidence"] if not e.get("exposed_at_steps")]}, sort_keys=True) + "\n")
        counts[name] = {f"{t} {l}": n for (t, l), n in sorted(tally.items())}
    json.dump(counts, sys.stdout, indent=1, sort_keys=True)
    print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main(*sys.argv[1:]))
