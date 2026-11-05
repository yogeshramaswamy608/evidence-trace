"""Run agents on AIOpsLab problems and save one folder per run (manuscript Section 5).

Run from an AIOpsLab checkout at commit 576c3f0 with a cluster ready (see .github/workflows/pilot.yml):
  python scripts/run_aiopslab.py --agent probe --problems pod_failure_hotel_res-localization-1 --out runs
  python scripts/run_aiopslab.py --agent model --model MODEL --condition B --seeds 0 1 2 --problems ... --out runs
Each run folder holds session.json (AIOpsLab's own session file), summary.txt, record.json (Condition B,
or the evidence only for A), usage.json and meta.json."""
from __future__ import annotations

import argparse
import asyncio
import glob
import json
import os
import shutil
import sys
import time
from pathlib import Path


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--agent", choices=["probe", "model"], required=True)
    p.add_argument("--model", default="")
    p.add_argument("--condition", choices=["A", "B"], default="A")
    p.add_argument("--seeds", type=int, nargs="+", default=[0])
    p.add_argument("--problems", nargs="+", required=True)
    p.add_argument("--max-steps", type=int, default=30)
    p.add_argument("--out", required=True)
    p.add_argument("--budget-usd", type=float, default=50.0, help="stop before a run once spend reaches this")
    p.add_argument("--price-in", type=float, default=0.0, help="USD per million input tokens")
    p.add_argument("--price-out", type=float, default=0.0, help="USD per million output tokens")
    args = p.parse_args()

    sys.path.insert(0, os.getcwd())  # the AIOpsLab checkout
    from aiopslab.orchestrator import Orchestrator  # noqa: E402

    from evtrace import locate, session  # noqa: E402
    from evtrace.agent import ModelAgent, ProbeAgent  # noqa: E402

    out_root = Path(args.out)
    out_root.mkdir(parents=True, exist_ok=True)
    spent = 0.0
    for pid in args.problems:
        for seed in args.seeds:
            if spent >= args.budget_usd:
                print(f"budget reached: {spent:.2f} USD; stopping")
                return 0
            tag = f"{args.agent}-{args.model or 'none'}-{args.condition}-{pid}-s{seed}".replace("/", "_")
            run_dir = out_root / tag
            if (run_dir / "meta.json").exists():
                print(f"skip {tag}: already done")
                continue
            run_dir.mkdir(parents=True, exist_ok=True)
            agent = ProbeAgent() if args.agent == "probe" else ModelAgent(args.model, seed=seed)
            orch = Orchestrator(results_dir=run_dir / "aiopslab")
            orch.register_agent(agent, name=tag)
            t0, error, output = time.time(), "", {}
            try:
                desc, instr, apis = orch.init_problem(pid)
                agent.init_context(desc, instr, apis)
                output = asyncio.run(orch.start_problem(max_steps=args.max_steps))
            except Exception as e:  # recorded, the batch goes on
                error = f"{type(e).__name__}: {e}"
            files = sorted(glob.glob(str(run_dir / "aiopslab" / "*.json")))
            if files:
                shutil.copy(files[-1], run_dir / "session.json")
            summary = ""
            if not error:
                try:
                    summary = agent.summarize(args.condition)
                except Exception as e:
                    error = f"summary {type(e).__name__}: {e}"
            (run_dir / "summary.txt").write_text(summary)
            if (run_dir / "session.json").exists():
                data = session.load(run_dir / "session.json")
                log, final = session.exposure(data)
                record = {"run_id": tag, "problem_id": pid, "final_step": final, "evidence": log.evidence(), "claims": []}
                unresolved = []
                if args.condition == "B":
                    parsed = locate.parse_summary(summary)
                    if parsed:
                        record, unresolved = locate.to_record(parsed, tag, pid, log.evidence(), final)
                (run_dir / "record.json").write_text(json.dumps(record, indent=2))
                (run_dir / "unresolved.json").write_text(json.dumps(unresolved, indent=2))
            usage = dict(getattr(agent, "usage", {}))
            cost = (usage.get("input_tokens", 0) * args.price_in + usage.get("output_tokens", 0) * args.price_out
                    + usage.get("cache_read_input_tokens", 0) * args.price_in * 0.1
                    + usage.get("cache_creation_input_tokens", 0) * args.price_in * 1.25) / 1e6
            spent += cost
            (run_dir / "usage.json").write_text(json.dumps({**usage, "cost_usd": round(cost, 4)}, indent=2))
            meta = {"problem_id": pid, "agent": args.agent, "model": args.model, "condition": args.condition,
                    "seed": seed, "seconds": round(time.time() - t0, 1), "error": error,
                    "results": output.get("results", {}) if isinstance(output, dict) else {},
                    "notes": list(getattr(agent, "notes", []))}
            (run_dir / "meta.json").write_text(json.dumps(meta, indent=2, default=str))
            print(f"{tag}: {'ERROR ' + error if error else 'ok'}; cost {cost:.4f} USD; total {spent:.2f} USD")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
