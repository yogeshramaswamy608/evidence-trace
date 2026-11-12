"""Condition A summaries that end mid-sentence (P4 f, Nov 12, 2026).
A summary ends mid-sentence when its last character, after trailing spaces and markdown marks, is not one of
. ! ? or a closing quote or bracket after one of them. Empty summaries are counted apart.
Usage: python scripts/a_endings.py ARTIFACT_DIR > docs/a_endings.json"""
import json
import os
import re
import sys
from collections import Counter

END = re.compile(r"[.!?][\"')\]]*$")


def main(art: str, outcomes: str = "data/runs/run_outcomes.jsonl") -> int:
    tally = Counter()
    for line in open(outcomes, encoding="utf-8"):
        o = json.loads(line)
        if o["condition"] != "A" or not o["reached"]:
            continue
        text = open(os.path.join(art, str(o["artifact"]), o["run_id"], "summary.txt"), encoding="utf-8").read()
        t = text.rstrip().rstrip("*_` ").rstrip()
        kind = "empty" if not t else "complete" if END.search(t) else "mid_sentence"
        tally[(o["model"], kind)] += 1
        tally[("all", kind)] += 1
    json.dump({f"{m} {k}": n for (m, k), n in sorted(tally.items())}, sys.stdout, indent=1, sort_keys=True)
    print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main(*sys.argv[1:]))
