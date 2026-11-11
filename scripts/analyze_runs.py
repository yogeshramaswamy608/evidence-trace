"""Paper 3, RQ3 and the Condition B format measures (manuscript Sections 6.1 and 6.3).

Input: data/runs/run_outcomes.jsonl (scripts/collect_runs.py). Output: JSON on stdout.
Primary: per model, exact McNemar on 41 per-problem outcomes, a problem correct in a condition when at
least 2 of its 3 runs are correct (a run not reached counts as not correct), Holm across the two models.
Secondary: logistic regression with condition and model fixed and a random intercept for problem, fitted by
maximum likelihood with 30-point Gauss-Hermite quadrature (numpy and scipy). Bootstrap seed 20261105.
"""
from __future__ import annotations

import json
import sys
from collections import defaultdict

import numpy as np
from scipy import optimize, special

from evtrace import stats

MODELS = ("claude-haiku-5-5", "claude-sonnet-5-5")


def load(path):
    with open(path, encoding="utf-8") as fh:
        return [json.loads(line) for line in fh if line.strip()]


def per_problem(rows, model, rule="primary"):
    """{problem: {cond: correct}} with the 2-of-3 rule; rule='available' uses a majority of reached runs."""
    runs = defaultdict(lambda: defaultdict(list))
    for r in rows:
        if r["model"] == model:
            runs[r["problem_id"]][r["condition"]].append(r)
    out = {}
    for p, by in runs.items():
        cell = {}
        for c in ("A", "B"):
            rs = by[c]
            wins = sum(bool(r["success"]) for r in rs)
            if rule == "primary":
                cell[c] = wins >= 2
            else:
                reached = [r for r in rs if r["reached"]]
                cell[c] = wins * 2 > len(reached) if reached else None
        out[p] = cell
    return out


def mcnemar(rows, rule="primary"):
    res = {}
    for m in MODELS:
        pp = {p: v for p, v in per_problem(rows, m, rule).items() if None not in v.values()}
        a = sum(v["A"] for v in pp.values()); b = sum(v["B"] for v in pp.values())
        only_a = sum(v["A"] and not v["B"] for v in pp.values()); only_b = sum(v["B"] and not v["A"] for v in pp.values())
        clusters = {p: [int(v["B"]) - int(v["A"])] for p, v in pp.items()}
        diff = stats.cluster_bootstrap(clusters, lambda xs: sum(xs) / len(xs))
        res[m] = {"problems": len(pp), "correct_A": a, "correct_B": b, "only_A": only_a, "only_B": only_b,
                  "p_exact": stats.mcnemar_exact(only_a, only_b),
                  "diff_B_minus_A": round(diff[0], 4), "diff_ci95": [round(diff[1], 4), round(diff[2], 4)]}
    adj = stats.holm([res[m]["p_exact"] for m in MODELS])
    for m, p in zip(MODELS, adj):
        res[m]["p_holm"] = p
    return res


def run_level(rows):
    """Run-level accuracy per model and condition, with a bootstrap interval over problems."""
    out = {}
    for m in MODELS:
        for c in ("A", "B"):
            rs = [r for r in rows if r["model"] == m and r["condition"] == c]
            clusters = defaultdict(list)
            for r in rs:
                clusters[r["problem_id"]].append(int(bool(r["success"])))
            p, lo, hi = stats.cluster_bootstrap(clusters, lambda xs: sum(xs) / len(xs))
            out[f"{m} {c}"] = {"runs": len(rs), "correct": sum(int(bool(r["success"])) for r in rs),
                               "accuracy": round(p, 4), "ci95": [round(lo, 4), round(hi, 4)]}
    return out


def glmm(rows, points=30):
    """Random-intercept logistic regression: success ~ condition_B + model_sonnet + (1 | problem), reached runs."""
    rs = [r for r in rows if r["reached"]]
    probs = sorted({r["problem_id"] for r in rs})
    idx = {p: i for i, p in enumerate(probs)}
    X = np.array([[1.0, r["condition"] == "B", r["model"] == "claude-sonnet-5-5"] for r in rs], dtype=float)
    y = np.array([bool(r["success"]) for r in rs], dtype=float)
    g = np.array([idx[r["problem_id"]] for r in rs])
    nodes, weights = np.polynomial.hermite.hermgauss(points)

    def nll(theta):
        beta, log_sd = theta[:3], theta[3]
        sd = np.exp(log_sd)
        eta = X @ beta
        total = 0.0
        for j in range(len(probs)):
            mask = g == j
            u = np.sqrt(2.0) * sd * nodes
            lin = eta[mask][:, None] + u[None, :]
            ll = (y[mask][:, None] * lin - np.logaddexp(0.0, lin)).sum(axis=0)
            total += special.logsumexp(ll, b=weights / np.sqrt(np.pi))
        return -total

    fit = optimize.minimize(nll, np.zeros(4), method="BFGS")
    hess = optimize.approx_fprime(fit.x, lambda t: optimize.approx_fprime(t, nll, 1e-5), 1e-5)
    cov = np.linalg.inv((hess + hess.T) / 2)
    se = np.sqrt(np.diag(cov))
    names = ["intercept", "condition_B", "model_sonnet", "log_sd_problem"]
    out = {"runs": len(rs), "problems": len(probs), "converged": bool(fit.success), "neg_log_lik": round(float(fit.fun), 4)}
    for i, n in enumerate(names):
        est = float(fit.x[i])
        out[n] = {"estimate": round(est, 4), "se": round(float(se[i]), 4),
                  "ci95": [round(est - 1.96 * se[i], 4), round(est + 1.96 * se[i], 4)]}
        if i in (1, 2):
            z = est / se[i]
            out[n]["odds_ratio"] = round(float(np.exp(est)), 4)
            out[n]["p_wald"] = float(2 * special.ndtr(-abs(z)))
    out["sd_problem"] = round(float(np.exp(fit.x[3])), 4)
    return out


def secondary(rows):
    out = {}
    for m in MODELS:
        for c in ("A", "B"):
            rs = [r for r in rows if r["model"] == m and r["condition"] == c and r["reached"]]
            med = lambda k: float(np.median([r[k] for r in rs if r.get(k) is not None]))
            tok = [sum((r.get(k) or 0) for k in ("input_tokens", "output_tokens", "cache_read_input_tokens",
                                                 "cache_creation_input_tokens")) for r in rs]
            cell = {"runs": len(rs), "median_steps": med("steps"), "median_tokens": float(np.median(tok)),
                    "median_seconds_to_submit": round(med("seconds_to_submit"), 2),
                    "cost_usd": round(sum(r.get("cost_usd") or 0 for r in rs), 4)}
            if c == "B":
                cell.update({"format_failures": sum(not r["b_parsed"] for r in rs),
                             "format_failure_rate": round(sum(not r["b_parsed"] for r in rs) / len(rs), 4),
                             "records_with_rule_violation": sum(bool(r["b_violations"]) for r in rs if r["b_parsed"]),
                             "parsed_records": sum(r["b_parsed"] for r in rs),
                             "evidence_links": sum(r["b_evidence_links"] for r in rs),
                             "links_not_exposed": sum(r["b_links_not_exposed"] for r in rs),
                             "violations_by_rule": {k: sum(k in r["b_violations"] for r in rs) for k in ("SCHEMA", "R1", "R2", "R3", "R4")}})
                cell["share_links_not_exposed"] = round(cell["links_not_exposed"] / cell["evidence_links"], 4) if cell["evidence_links"] else None
                cell["share_parsed_records_with_violation"] = round(cell["records_with_rule_violation"] / cell["parsed_records"], 4) if cell["parsed_records"] else None
            out[f"{m} {c}"] = cell
    return out


def main(path="data/runs/run_outcomes.jsonl"):
    rows = load(path)
    assert len(rows) == 492, "expected 492 main runs"
    result = {"not_reached": [r["run_id"] for r in rows if not r["reached"]],
              "rq3_mcnemar_primary": mcnemar(rows), "rq3_mcnemar_reached_runs_majority": mcnemar(rows, "available"),
              "rq3_run_accuracy": run_level(rows), "rq3_glmm": glmm(rows), "secondary": secondary(rows)}
    json.dump(result, sys.stdout, indent=2, sort_keys=True)
    print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main(*sys.argv[1:]))
