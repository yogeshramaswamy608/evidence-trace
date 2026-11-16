"""Paired comparison of the link-blind baseline and the full verifier on the same claims (RQ2; plan play 4).

Usage: python scripts/rq2_paired.py SPLIT LABELS.jsonl VERIFIER.jsonl BASELINE.jsonl
Both systems labeled the same claims, so their difference is tested on the pairs, not by comparing two
separate intervals. For precision, recall and F1 of the positive class (unsupported or contradicted), the
difference baseline minus verifier gets a 95 percent cluster bootstrap interval over runs (evtrace.stats,
seed 20261105); an interval that excludes 0 is a difference. The exact McNemar test counts the claims where
one system's positive or negative call matches the author's label and the other's does not. Not checkable
claims are excluded, as in rq2_score.py. Prints JSON; nothing is printed per claim.
"""
import json
import sys

from evtrace import stats

POS = ("unsupported", "contradicted")
NORM = {"partly supported": "partly_supported", "not checkable": "not_checkable"}


def norm(x):
    x = str(x).strip().lower().replace("_", " ")
    return NORM.get(x, x)


def paired(rows_by_run: dict[str, list]) -> dict:
    """rows_by_run: run id -> list of (author positive, system B positive, system A positive). Returns B minus A."""
    rows = [x for c in rows_by_run.values() for x in c]
    out = {"claims": len(rows), "runs": len(rows_by_run), "positives": sum(t for t, _, _ in rows)}
    for i, name in enumerate(("precision", "recall", "f1")):
        d, lo, hi = stats.cluster_bootstrap(rows_by_run, lambda xs, i=i: stats.prf([t for t, _, _ in xs], [p for _, p, _ in xs])[i]
                                            - stats.prf([t for t, _, _ in xs], [q for _, _, q in xs])[i])
        out[f"{name}_difference"] = {"value": round(d, 4), "ci95": [round(lo, 4), round(hi, 4)], "excludes_0": lo > 0 or hi < 0}
    only_b = sum((p == t) and (q != t) for t, p, q in rows)
    only_a = sum((q == t) and (p != t) for t, p, q in rows)
    out["mcnemar"] = {"second_right_first_wrong": only_b, "first_right_second_wrong": only_a,
                      "p_exact": round(stats.mcnemar_exact(only_b, only_a), 6)}
    return out


def main(split: str, labels: str, verifier: str, baseline: str) -> int:
    human = {json.loads(l)["key"]: norm(json.loads(l)["label"]) for l in open(labels, encoding="utf-8")}
    v = {r["key"]: r for r in map(json.loads, open(verifier, encoding="utf-8")) if r.get("split") == split}
    b = {r["key"]: r for r in map(json.loads, open(baseline, encoding="utf-8")) if r.get("split") == split}
    assert set(v) == set(b)
    clusters: dict[str, list] = {}
    for k in sorted(v):
        if human[k] == "not_checkable":
            continue
        clusters.setdefault(v[k]["run_id"], []).append((human[k] in POS, b[k]["verifier_label"] in POS, v[k]["verifier_label"] in POS))
    out = {"split": split, "first": verifier, "second": baseline, **paired(clusters)}
    json.dump(out, sys.stdout, indent=1, sort_keys=True)
    print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main(*sys.argv[1:]))
