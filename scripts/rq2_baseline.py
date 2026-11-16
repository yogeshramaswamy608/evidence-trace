"""The link-blind baseline of RQ2 (preregistration, Analysis 2; deviation 3; play 3b of the plan of Nov 11, 2026).

Usage: python scripts/rq2_baseline.py JUDGE IN.jsonl OUT.jsonl [--log LOG.jsonl] [--budget-usd X] [--judge-max-tokens N]
IN is a bundle of scripts/rq2_prepare.py. For each claim the frozen Stage 3 judge (evtrace.verify.ModelJudge, the
frozen prompt, the same model and output limit as the judge run of deviation 6) reads the claim with the capped
pool of 50 items exposed in its run (deviation 3), with no link, no Stage 1 and no Stage 2. Its one word is the
label: contradicts -> contradicted, unrelated -> unsupported, entails -> supported, partly -> partly_supported.
A recommendation is not checkable and gets no call, as in verify(). Spending stops before a claim once the
estimate reaches the budget (Claude Opus 5.5 at 4 and 20 USD per million tokens, as in rq2_run.py). The output
lines have the fields of rq2_run.py, so rq2_score.py scores them unchanged. Nothing here reads a human label.
"""
import argparse
import json

from evtrace import verify

PRICE_IN, PRICE_OUT = 4.0, 20.0
LABEL = {"contradicts": "contradicted", "unrelated": "unsupported", "entails": "supported", "partly": "partly_supported"}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("judge")
    ap.add_argument("inp")
    ap.add_argument("out")
    ap.add_argument("--log")
    ap.add_argument("--budget-usd", type=float, default=0.0)
    ap.add_argument("--judge-max-tokens", type=int, default=4096)
    a = ap.parse_args()
    judge = verify.ModelJudge(a.judge, log_path=a.log, max_tokens=a.judge_max_tokens)
    stopped = not_checkable = errors = 0
    with open(a.inp, encoding="utf-8") as fh, open(a.out, "w", encoding="utf-8") as out:
        for line in fh:
            row = json.loads(line)
            res = {k: row[k] for k in ("key", "run_id", "claim_id", "split", "condition", "model", "self_report", "link_source") if k in row}
            claim = next(c for c in row["record"]["claims"] if c["claim_id"] == row["claim_id"])
            if claim["type"] == "recommendation":
                not_checkable += 1
                res.update({"verifier_label": None, "reasons": ["NOT_CHECKABLE"]})
            else:
                u = judge.usage
                if (u["input_tokens"] * PRICE_IN + u["output_tokens"] * PRICE_OUT) / 1e6 >= a.budget_usd:
                    stopped += 1
                    res.update({"verifier_label": None, "reasons": ["NOT_RUN_BUDGET"]})
                else:
                    try:
                        verdict = judge(claim, row["pool"])
                        res.update({"verifier_label": LABEL[verdict], "reasons": [f"BASELINE_{verdict.upper()}"]})
                    except Exception as e:  # an API error is counted, never retried, so the run stays one run
                        errors += 1
                        res.update({"verifier_label": None, "reasons": ["JUDGE_ERROR", str(e)[:120]]})
            out.write(json.dumps(res, sort_keys=True) + "\n")
    usage = judge.usage
    print(json.dumps({"input": a.inp, "judge": a.judge, "baseline": "link-blind, pool 50", "judge_errors": errors,
                      "not_checkable": not_checkable, "not_run_budget": stopped, "usage": usage,
                      "cost_usd": round((usage["input_tokens"] * PRICE_IN + usage["output_tokens"] * PRICE_OUT) / 1e6, 4)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
