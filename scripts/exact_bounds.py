"""Exact (Clopper-Pearson) one-sided 97.5 percent upper bound for a zero count (A1, Nov 12, 2026).

A bootstrap cannot move off a count of zero, so a cell with 0 of n claims also gets its exact bound:
the p at which seeing 0 of n has probability 0.025, that is 1 - 0.025 ** (1 / n). Claims are treated as
independent, which ignores clustering by run, so the bound is the best case.
Usage: python scripts/exact_bounds.py docs/results_rq1.json > docs/exact_bounds.json
"""
import json
import sys


def upper_zero(n: int, alpha: float = 0.025) -> float:
    return 1 - alpha ** (1 / n)


def main(path: str) -> int:
    d = json.load(open(path, encoding="utf-8"))
    out = {}
    for group in ("rq1_by_condition", "rq1_by_model_condition"):
        for name, cell in d[group].items():
            for lab in ("unsupported", "contradicted", "partly_supported", "unsupported_or_contradicted"):
                if cell[lab]["rate"] == 0 and cell["checkable"]:
                    out[f"{name} {lab}"] = {"count": 0, "checkable": cell["checkable"],
                                            "upper_97_5": round(upper_zero(cell["checkable"]), 4)}
    json.dump(out, sys.stdout, indent=1, sort_keys=True)
    print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main(*sys.argv[1:]))
