"""Choose K and MIN_SCORE of link recovery on the 100 development claims only (P1 a, Nov 12, 2026).

Usage: python scripts/rq2_tune.py QUEUE_KEY.json DEV_LABELS.jsonl CORRECTED_DIR
DEV_LABELS.jsonl holds the author's labels of the 100 development claims only (key, label, evids), cut from
the label file by script; no test label is read here. The target is the author's own cited evidence: for each
Condition A development claim with cited items, the F1 between the recovered links and the cited items.
The grid is fixed: K in 1, 2, 3, 5, 8, 10 and MIN_SCORE in 0, 2, 3, 4, 5, 6. The best mean F1 wins; a tie
goes to the smaller K, then the higher MIN_SCORE. Prints the grid and the choice.
"""
import json
import os
import re
import sys

from evtrace import recover

GRID_K, GRID_T = (1, 2, 3, 5, 8, 10), (0, 2, 3, 4, 5, 6)


def cited(evids: str) -> set[str]:
    out = set()
    for tok in re.findall(r"e\d+(?:\s*-\s*e?\d+)?", evids or ""):
        if "-" in tok:
            a, b = (int(x) for x in re.findall(r"\d+", tok))
            out |= {f"e{i}" for i in range(a, b + 1)}
        else:
            out.add(tok)
    return out


def main(key_path: str, dev_path: str, cdir: str) -> int:
    key = {q["key"]: q["source"] for q in json.load(open(key_path, encoding="utf-8"))["queue"]}
    dev = [json.loads(l) for l in open(dev_path, encoding="utf-8")]
    assert len(dev) == 100 and all(key[d["key"]]["split"] == "dev" for d in dev)
    cases = []
    for d in dev:
        src = key[d["key"]]
        c = cited(d["evids"])
        if src["condition"] != "A" or not c:
            continue
        rec = json.load(open(os.path.join(cdir, src["run_id"] + ".json"), encoding="utf-8"))
        scored, _ = recover.rank(src["text"], recover.exposed_items(rec))
        cases.append((scored, c))
    grid = {}
    for k in GRID_K:
        for t in GRID_T:
            f1s = []
            for scored, c in cases:
                got = {e["evidence_id"] for s, e in scored[:k] if s >= t}
                tp = len(got & c)
                f1s.append(0.0 if not tp else 2 * tp / (len(got) + len(c)))
            grid[(k, t)] = sum(f1s) / len(f1s)
    best = sorted(grid, key=lambda kt: (-round(grid[kt], 6), kt[0], -kt[1]))[0]
    json.dump({"cases": len(cases), "grid": {f"K={k} MIN_SCORE={t}": round(v, 4) for (k, t), v in sorted(grid.items())},
               "chosen": {"k": best[0], "min_score": best[1], "mean_f1": round(grid[best], 4)}}, sys.stdout, indent=1)
    print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main(*sys.argv[1:]))
