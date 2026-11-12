"""Summarize the P4 count and replay of the failed Condition B summaries (deviation 4, Nov 12, 2026).
Usage: python scripts/replay_report.py > docs/replay_report.json
Inputs: data/replay/count.jsonl, data/replay/replay.jsonl and data/replay/replay_responses.jsonl.gz, from the
replay workflow (runs 43314840266, count, and 43315863561, replay)."""
import gzip
import json
import statistics as st
import sys
from collections import Counter

REGISTERED_LIMIT = 2048


def main() -> int:
    count = {r["run_id"]: r for r in map(json.loads, open("data/replay/count.jsonl"))}
    rep = {r["run_id"]: r for r in map(json.loads, open("data/replay/replay.jsonl"))}
    resp = {}
    with gzip.open("data/replay/replay_responses.jsonl.gz", "rt", encoding="utf-8") as fh:
        for line in fh:
            d = json.loads(line)
            resp[d["run_id"]] = d["response"]
    out = {"runs": len(count), "rebuilt_exactly": sum(r["exact"] for r in count.values()),
           "replay_cost_usd": round(sum(r.get("cost_usd", 0) for r in rep.values()), 4)}
    for model in sorted({r["model"] for r in count.values()}):
        ids = [k for k, r in count.items() if r["model"] == model]
        stored = [count[k]["summary_tokens"] for k in ids if count[k]["summary_chars"]]
        usage = [resp[k]["usage"] for k in ids]
        total = [u["output_tokens"] for u in usage]
        thinking = [(u.get("output_tokens_details") or {}).get("thinking_tokens", 0) for u in usage]
        out[model] = {
            "failed_runs": len(ids), "stored_empty": sum(not count[k]["summary_chars"] for k in ids),
            "stored_text_tokens_median": st.median(stored) if stored else None,
            "stored_text_tokens_max": max(stored) if stored else None,
            "replay_stop_reasons": dict(Counter(rep[k].get("stop_reason") for k in ids)),
            "replay_with_thinking_block": sum(any(b.get("type") == "thinking" for b in resp[k].get("content", [])) for k in ids),
            "replay_output_tokens_median": st.median(total), "replay_output_tokens_max": max(total),
            "replay_thinking_tokens_median": st.median(thinking),
            "replay_over_registered_limit": sum(t > REGISTERED_LIMIT for t in total),
            "replay_parsed": sum(bool(rep[k].get("parsed")) for k in ids),
            "replay_claims": sum(rep[k].get("claims", 0) for k in ids),
        }
    json.dump(out, sys.stdout, indent=1, sort_keys=True)
    print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
