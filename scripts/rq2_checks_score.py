"""Score the verifier on the check sets, whose labels are known by construction (P2 d, Nov 12, 2026).
Usage: python scripts/rq2_checks_score.py data/rq2/judge/checks_v2_judge.jsonl data/rq2/judge/checks_v1_judge.jsonl ...
Prints, per file, the agreement with the built label, the confusion table and, per template, the agreement.
Positive class unsupported or contradicted; precision, recall and F1 with a cluster bootstrap over runs."""
import json
import sys
from collections import Counter, defaultdict

from evtrace import stats

POS = ("unsupported", "contradicted")


def main(*paths: str) -> int:
    out = {}
    for p in paths:
        rows = [json.loads(l) for l in open(p, encoding="utf-8")]
        clusters = defaultdict(list)
        for r in rows:
            clusters[r["run_id"]].append((r["built_label"] in POS, r["verifier_label"] in POS))
        cell = {"claims": len(rows), "verifier_null": sum(r["verifier_label"] is None for r in rows),
                "agree": sum(r["verifier_label"] == r["built_label"] for r in rows)}
        for i, name in enumerate(("precision", "recall", "f1")):
            v, lo, hi = stats.cluster_bootstrap(clusters, lambda xs, i=i: stats.prf([t for t, _ in xs], [x for _, x in xs])[i])
            cell[name] = {"value": round(v, 4), "ci95": [round(lo, 4), round(hi, 4)]}
        cell["by_template"] = {t: f"{sum(r['verifier_label'] == r['built_label'] for r in rs)} of {len(rs)}"
                               for t, rs in sorted({t: [r for r in rows if r["template"] == t] for t in {r["template"] for r in rows}}.items())}
        cell["confusion"] = {f"{a} -> {b}": n for (a, b), n in sorted(Counter((r["built_label"], r["verifier_label"] or "none") for r in rows).items())}
        out[p] = cell
    json.dump(out, sys.stdout, indent=1, sort_keys=True)
    print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main(*sys.argv[1:]))
