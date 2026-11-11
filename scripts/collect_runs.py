"""Collect one outcome line per main run from the downloaded GitHub Actions artifacts (paper 3).

Usage: python scripts/collect_runs.py ARTIFACT_DIR > data/runs/run_outcomes.jsonl
ARTIFACT_DIR holds one folder per artifact id, each with the run folders model-<model>-<cond>-<problem>-s<seed>.
Main-run artifacts are those with id >= 13484234500 (Nov 6, 2026); earlier ids are the pilot and the probes,
kept out of the main analysis (manuscript Section 6.4). For a run present in several main artifacts, the
latest artifact whose run has no error and a record.json is used; a run with none is reported as not reached.
"""
from __future__ import annotations

import glob
import json
import os
import sys

from evtrace import rules
from evtrace.record import Record

MAIN_FROM = 13484234500


def main(root: str) -> int:
    found: dict[str, list[tuple[int, str]]] = {}
    for meta in glob.glob(os.path.join(root, "*", "model-*", "meta.json")):
        aid = int(meta.split(os.sep)[-3])
        if aid >= MAIN_FROM:
            found.setdefault(os.path.basename(os.path.dirname(meta)), []).append((aid, os.path.dirname(meta)))
    for rid in sorted(found):
        usable = [d for _, d in sorted(found[rid])
                  if not json.load(open(os.path.join(d, "meta.json")))["error"] and os.path.exists(os.path.join(d, "record.json"))]
        d = usable[-1] if usable else sorted(found[rid])[-1][1]
        meta = json.load(open(os.path.join(d, "meta.json")))
        res = meta.get("results") or {}
        usage = json.load(open(os.path.join(d, "usage.json"))) if os.path.exists(os.path.join(d, "usage.json")) else {}
        row = {"run_id": rid, "artifact": int(d.split(os.sep)[-2]), "model": meta["model"], "condition": meta["condition"],
               "problem_id": meta["problem_id"], "seed": meta["seed"],
               "task_type": "analysis" if "analysis" in meta["problem_id"] else "localization",
               "reached": bool(usable), "error": meta["error"][:200],
               "success": res.get("success") if usable else None, "steps": res.get("steps"),
               "seconds_to_submit": res.get("TTL", res.get("TTA")), "seconds_total": meta.get("seconds"),
               "input_tokens": usage.get("input_tokens"), "output_tokens": usage.get("output_tokens"),
               "cache_read_input_tokens": usage.get("cache_read_input_tokens"),
               "cache_creation_input_tokens": usage.get("cache_creation_input_tokens"), "cost_usd": usage.get("cost_usd")}
        if usable and meta["condition"] == "B":
            rec = Record(json.load(open(os.path.join(d, "record.json"))))
            unresolved = json.load(open(os.path.join(d, "unresolved.json")))
            viol = rules.check(rec)
            ev_links = [l for c in rec.claims.values() for l in c["links"] if l["link_type"] != "derived_from"]
            row.update({"b_claims": len(rec.claims), "b_parsed": bool(rec.claims),
                        "b_violations": sorted({v.rule for v in viol}),
                        "b_evidence_links": len(ev_links),
                        "b_links_not_exposed": sum(not rules.exposed_before_final(rec, l["target"]) for l in ev_links),
                        "b_unresolved_locators": len(unresolved)})
        print(json.dumps(row, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(*sys.argv[1:]))
