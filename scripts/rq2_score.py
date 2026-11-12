"""Score the verifier against the author's labels for RQ2 (preregistration, Analysis 2; P1, Nov 12, 2026).

Usage: python scripts/rq2_score.py SPLIT LABELS.jsonl VERIFIER.jsonl [VERIFIER2.jsonl ...]
SPLIT is dev or test. LABELS.jsonl holds the author's labels of that split only (key, label). The test labels
are read once, by this script, after the verifier is frozen; the commit is recorded in EB1A_Decisions.txt.
Positive class: unsupported or contradicted. Not checkable claims are excluded, as in RQ1. A claim the
verifier could not label (null) counts as a miss of the positive class and is reported. Precision, recall and
F1 carry a 95 percent cluster bootstrap interval over runs (evtrace.stats, seed 20261105); the four-class
confusion table, macro F1 and unweighted kappa follow. Every cell is also given for Condition A (recovered
links) and Condition B (agent links) apart, and, exploratory, without the self-reports (P3).
Prints JSON; nothing is printed per claim.
"""
import json
import sys
from collections import Counter, defaultdict

from evtrace import stats

NORM = {"supported": "supported", "partly supported": "partly_supported", "unsupported": "unsupported",
        "contradicted": "contradicted", "not checkable": "not_checkable"}
LABELS = ("supported", "partly_supported", "unsupported", "contradicted")
POS = ("unsupported", "contradicted")


def norm(x: str | None) -> str | None:
    return None if x is None else NORM.get(str(x).strip().lower().replace("_", " "), str(x))


def cell(rows: list[dict]) -> dict:
    if not rows:
        return {"claims": 0}
    clusters = defaultdict(list)
    for r in rows:
        clusters[r["run_id"]].append((r["human"] in POS, r["verifier"] in POS))
    out = {"claims": len(rows), "positives": sum(r["human"] in POS for r in rows),
           "verifier_null": sum(r["verifier"] is None for r in rows)}
    for i, name in enumerate(("precision", "recall", "f1")):
        p, lo, hi = stats.cluster_bootstrap(clusters, lambda xs, i=i: stats.prf([t for t, _ in xs], [v for _, v in xs])[i])
        out[name] = {"value": round(p, 4), "ci95": [round(lo, 4), round(hi, 4)]}
    h, v = [r["human"] for r in rows], [r["verifier"] or "none" for r in rows]
    out["confusion"] = {f"{a} -> {b}": n for (a, b), n in sorted(Counter(zip(h, v)).items())}
    f1s = []
    for lab in LABELS:
        f1s.append(stats.prf([x == lab for x in h], [y == lab for y in v])[2])
    out["macro_f1"] = round(sum(f1s) / len(f1s), 4)
    out["kappa"] = round(stats.cohen_kappa(h, v), 4)
    return out


def main(split: str, labels_path: str, *verifiers: str) -> int:
    human = {}
    for line in open(labels_path, encoding="utf-8"):
        r = json.loads(line)
        human[r["key"]] = norm(r["label"])
    result = {"split": split}
    for path in verifiers:
        rows = []
        for line in open(path, encoding="utf-8"):
            v = json.loads(line)
            if v.get("split") != split:
                continue
            h = human[v["key"]]
            if h == "not_checkable":
                continue
            rows.append({"run_id": v["run_id"], "human": h, "verifier": v["verifier_label"],
                         "condition": v["condition"], "self_report": v["self_report"]})
        assert len({r["run_id"] for r in rows}) and len(rows) <= len(human)
        result[path] = {"all": cell(rows),
                        "A_recovered_links": cell([r for r in rows if r["condition"] == "A"]),
                        "B_agent_links": cell([r for r in rows if r["condition"] == "B"]),
                        "exploratory_without_self_reports": cell([r for r in rows if not r["self_report"]])}
    json.dump(result, sys.stdout, indent=1, sort_keys=True)
    print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main(*sys.argv[1:]))
