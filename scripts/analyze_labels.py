"""Paper 3 results that need only the human labels: the check claims and RQ1 (preregistration, Analysis 1).

Input: data/labels/human_labels.jsonl, one line per labeled claim (330: 300 sampled, 30 check claims).
Output: a JSON summary on stdout. Every number comes from evtrace.stats; bootstrap seed 20261105.
"""
from __future__ import annotations

import json
import re
import sys
from collections import Counter, defaultdict

from evtrace import stats

RATES = ("unsupported", "partly_supported", "contradicted")


def load(path: str) -> list[dict]:
    with open(path, encoding="utf-8") as fh:
        return [json.loads(line) for line in fh if line.strip()]


# Exploratory, not preregistered: claims that only report the agent's own submission or classification.
SELF_REPORT = re.compile(r"\b(submitted|classified)\b", re.IGNORECASE)


def check_claims(rows: list[dict]) -> dict:
    gold = [r for r in rows if r["is_gold"]]
    truth, human = [r["gold_label"] for r in gold], [r["label"] for r in gold]
    agree = sum(t == h for t, h in zip(truth, human))
    return {"n": len(gold), "agree": agree, "share": agree / len(gold),
            "confusion": {f"{t} -> {h}": n for (t, h), n in sorted(Counter(zip(truth, human)).items())}}


def rq1(rows: list[dict], group=None) -> dict:
    sample = [r for r in rows if not r["is_gold"]]
    out = {}
    groups = defaultdict(list)
    for r in sample:
        groups["all" if group is None else group(r)].append(r)
    for g, rs in sorted(groups.items()):
        clusters = defaultdict(list)
        for r in rs:
            if r["label"] != "not_checkable":  # rubric v1, label 5: excluded from all denominators and counted
                clusters[r["run_id"]].append(r["label"])
        cell = {"claims": len(rs), "checkable": sum(len(v) for v in clusters.values()), "runs": len(clusters),
                "labels": dict(sorted(Counter(r["label"] for r in rs).items()))}
        for lab in RATES + ("unsupported_or_contradicted",):
            want = ("unsupported", "contradicted") if lab == "unsupported_or_contradicted" else (lab,)
            p, lo, hi = stats.cluster_bootstrap(clusters, lambda xs, w=want: sum(x in w for x in xs) / len(xs))
            cell[lab] = {"rate": round(p, 4), "ci95": [round(lo, 4), round(hi, 4)]}
        out[g] = cell
    return out


def main(path: str = "data/labels/human_labels.jsonl", texts: str | None = None) -> int:
    rows = load(path)
    extra = {}
    if texts:  # claim texts by key, for the exploratory self-report split
        with open(texts, encoding="utf-8") as fh:
            text = {x["key"]: x["text"] for x in json.load(fh)["queue"]}
        self_rep = [r for r in rows if not r["is_gold"] and SELF_REPORT.search(text[r["key"]])]
        keep = [r for r in rows if r not in self_rep]
        extra = {"exploratory_self_report": {"n": len(self_rep), "keys": [r["key"] for r in self_rep],
                                             "labels": dict(sorted(Counter(r["label"] for r in self_rep).items()))},
                 "exploratory_rq1_without_self_report_by_condition": rq1(keep, lambda r: r["condition"])}
    assert len(rows) == 330 and sum(r["is_gold"] for r in rows) == 30, "expected 300 sampled and 30 check claims"
    result = {
        "check_claims": check_claims(rows),
        "rq1_all": rq1(rows),
        "rq1_by_model_condition": rq1(rows, lambda r: f"{r['model']} {r['condition']}"),
        "rq1_by_condition": rq1(rows, lambda r: r["condition"]),
        "rq1_by_model": rq1(rows, lambda r: r["model"]),
        "rq1_by_task": rq1(rows, lambda r: r["task_type"]),
        **extra,
    }
    json.dump(result, sys.stdout, indent=2, sort_keys=True)
    print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main(*sys.argv[1:]))
