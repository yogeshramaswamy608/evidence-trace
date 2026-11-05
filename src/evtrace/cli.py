"""Command line: check, verify, exposure, gold and selftest."""
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter

from . import gold, rules, session, stats
from .record import Record
from .verify import ModelJudge, stage2_judge, verify


def _judge(args):
    return ModelJudge(args.model) if args.model else stage2_judge


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="evtrace", description="Evidence-traceable root-cause claims")
    sub = p.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("check", help="Stage 1 structural checks of a provenance record")
    c.add_argument("record")
    v = sub.add_parser("verify", help="label every claim of a provenance record")
    v.add_argument("record")
    v.add_argument("--model", help="Stage 3 judge model; reads LLM_API_KEY. Without it, Stages 1 and 2 only")
    e = sub.add_parser("exposure", help="evidence items of an AIOpsLab session file")
    e.add_argument("session")
    g = sub.add_parser("gold", help="claims with labels known by construction from a session file")
    g.add_argument("session")
    g.add_argument("--seed", type=int, default=20261105)
    g.add_argument("--out", required=True)
    s = sub.add_parser("selftest", help="verifier against gold labels by construction for session files")
    s.add_argument("sessions", nargs="+")
    s.add_argument("--seed", type=int, default=20261105)
    s.add_argument("--model")
    args = p.parse_args(argv)

    if args.cmd == "check":
        out = rules.check(Record.load(args.record))
        for x in out:
            print(f"{x.rule}\t{x.claim_id}\t{x.detail}")
        return 1 if out else 0
    if args.cmd == "verify":
        res = verify(Record.load(args.record), _judge(args))
        for r in res.values():
            print(f"{r.claim_id}\t{r.label or 'not_checkable'}\t{','.join(r.reasons)}")
        return 0
    if args.cmd == "exposure":
        log, final = session.exposure(session.load(args.session))
        json.dump({"final_step": final, "evidence": log.evidence()}, sys.stdout, indent=2)
        print()
        return 0
    if args.cmd == "gold":
        data = session.load(args.session)
        log, final = session.exposure(data)
        record, labels = gold.build(data.get("run_id", args.session), data.get("problem_id", ""),
                                    log.evidence(), final, args.seed)
        with open(args.out, "w", encoding="utf-8") as fh:
            json.dump({"record": record, "gold": labels}, fh, indent=2)
        print(f"{len(labels)} claims written to {args.out}")
        return 0
    if args.cmd == "selftest":
        judge = _judge(args)
        truth, pred, clusters = [], [], {}
        for path in args.sessions:
            data = session.load(path)
            log, final = session.exposure(data)
            record, labels = gold.build(data.get("run_id", path), data.get("problem_id", ""),
                                        log.evidence(), final, args.seed)
            res = verify(Record(record), judge)
            for cid, lab in labels.items():
                t = lab.split("|")[0]
                truth.append(t)
                pred.append(res[cid].label)
                clusters.setdefault(path, []).append(t == res[cid].label)
        neg = ("unsupported", "contradicted")
        pr = stats.prf([t in neg for t in truth], [x in neg for x in pred])
        acc = stats.cluster_bootstrap(clusters, lambda xs: sum(xs) / len(xs))
        print(f"claims {len(truth)}; agreement {acc[0]:.3f} (95% CI {acc[1]:.3f} to {acc[2]:.3f}); "
              f"kappa {stats.cohen_kappa(truth, pred):.3f}; "
              f"unsupported-or-contradicted precision {pr[0]:.3f} recall {pr[1]:.3f} F1 {pr[2]:.3f}")
        for (t, x), n in sorted(Counter(zip(truth, pred)).items()):
            print(f"  gold {t:<17} verifier {x or 'none':<17} {n}")
        return 0
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
