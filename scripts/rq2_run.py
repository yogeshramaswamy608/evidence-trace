"""Run the frozen verifier on the RQ2 bundles and the check sets (P1 b, Nov 12, 2026).

Usage: python scripts/rq2_run.py JUDGE IN.jsonl OUT.jsonl [--log LOG.jsonl] [--budget-usd X]
JUDGE is "stage2" (no model; the no-judge baseline of Section 4) or a model id for Stage 3 (claude-opus-5-5,
which differs from both agent models; enforced by ModelJudge). Each input line carries a trimmed record and
the id of the claim to label; the output line holds the verifier's label and reason codes. A record on which
the verifier raises an error (the registered records hold start times the parser shifted, deviation 5) gets
label null and the reason VERIFIER_ERROR, and is counted. Every judge request and response goes to LOG with its
UTC time. Spending stops before a claim once the estimate reaches the budget (Claude Opus 5.5 at 4 and 20 USD
per million tokens, pricing page read Nov 10, 2026). Nothing here reads a human label.
"""
import argparse
import json

from evtrace import verify
from evtrace.record import Record

PRICE_IN, PRICE_OUT = 4.0, 20.0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("judge")
    ap.add_argument("inp")
    ap.add_argument("out")
    ap.add_argument("--log")
    ap.add_argument("--budget-usd", type=float, default=0.0)
    a = ap.parse_args()
    judge = verify.stage2_judge if a.judge == "stage2" else verify.ModelJudge(a.judge, log_path=a.log)
    errors = stopped = 0
    with open(a.inp, encoding="utf-8") as fh, open(a.out, "w", encoding="utf-8") as out:
        for line in fh:
            row = json.loads(line)
            res = {k: row[k] for k in ("key", "run_id", "claim_id", "split", "label", "template", "condition", "model", "self_report", "link_source") if k in row}
            if res.get("label") is not None:
                res["built_label"] = res.pop("label")
            if a.judge != "stage2":
                u = judge.usage
                spent = (u["input_tokens"] * PRICE_IN + u["output_tokens"] * PRICE_OUT) / 1e6
                if spent >= a.budget_usd:
                    stopped += 1
                    res.update({"verifier_label": None, "reasons": ["NOT_RUN_BUDGET"]})
                    out.write(json.dumps(res, sort_keys=True) + "\n")
                    continue
            try:
                r = verify.verify(Record(row["record"]), judge)[row["claim_id"]]
                res.update({"verifier_label": r.label, "reasons": r.reasons})
            except ValueError as e:
                errors += 1
                res.update({"verifier_label": None, "reasons": ["VERIFIER_ERROR", str(e)[:120]]})
            out.write(json.dumps(res, sort_keys=True) + "\n")
    usage = getattr(judge, "usage", {})
    print(json.dumps({"input": a.inp, "judge": a.judge, "verifier_errors": errors, "not_run_budget": stopped, "usage": usage,
                      "cost_usd": round((usage.get("input_tokens", 0) * PRICE_IN + usage.get("output_tokens", 0) * PRICE_OUT) / 1e6, 4)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
