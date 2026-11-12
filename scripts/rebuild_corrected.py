"""Rebuild a corrected exposure record for every main run from its stored session.json (deviation 5).

Usage: python scripts/rebuild_corrected.py ARTIFACT_DIR OUT_DIR > data/corrected/manifest.jsonl
ARTIFACT_DIR holds the downloaded GitHub Actions artifacts (one folder per artifact id), as for
scripts/collect_runs.py; the run of each main run is the one data/runs/run_outcomes.jsonl names.
For each run it writes OUT_DIR/<run_id>.json (the registered record with its evidence replaced by the
corrected reading of evtrace.exposure_v2) and prints one manifest line: the sha256 of the stored
record.json and of the corrected record, and the defect counts. It checks, and stops if not, that the
corrected evidence has the same item ids in the same order as the stored record, that every item that is
not a span is equal, and that the registered parser run on the same session gives the stored evidence back.
Nothing here reads a label.
"""
from __future__ import annotations

import hashlib
import json
import os
import sys

from evtrace import session
from evtrace.exposure import ExposureLog
from evtrace.exposure_v2 import CorrectedExposureLog

FIELDS = ("operation", "timestamp", "duration_us", "error", "status")


def exposure(data: dict, log_cls) -> ExposureLog:
    """session.exposure with the log class given; the step and action logic is the registered one."""
    log = log_cls()
    trace = data.get("trace") or data.get("history") or []
    step, pending = 0, None
    for item in trace:
        role, content = item.get("role"), str(item.get("content", ""))
        if role == "assistant":
            step += 1
            pending = session.parse_action(content)
        elif role in ("env", "environment", "user"):
            if pending and pending[0] not in ("submit", "unknown"):
                name, args = pending
                meta = {"command": args.strip() or name}
                if name == "get_logs":
                    meta["source"] = "/".join(a.strip().strip("'\"") for a in args.split(",") if a.strip())
                log.record(name, step, content, **meta)
            pending = None
    return log


def sha(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def main(root: str, out: str, outcomes: str = "data/runs/run_outcomes.jsonl") -> int:
    os.makedirs(out, exist_ok=True)
    for line in open(outcomes, encoding="utf-8"):
        o = json.loads(line)
        if not o["reached"]:
            continue
        d = os.path.join(root, str(o["artifact"]), o["run_id"])
        raw = open(os.path.join(d, "record.json"), "rb").read()
        rec = json.loads(raw)
        data = json.load(open(os.path.join(d, "session.json"), encoding="utf-8"))
        reg = exposure(data, ExposureLog).evidence()
        cor = exposure(data, CorrectedExposureLog).evidence()
        stored = [e for e in rec["evidence"] if e.get("exposed_at_steps")]  # gold.py adds hidden items only later
        assert json.dumps(reg, sort_keys=True) == json.dumps(stored, sort_keys=True), f"{o['run_id']}: registered parse differs"
        assert [e["evidence_id"] for e in cor] == [e["evidence_id"] for e in stored], f"{o['run_id']}: item ids differ"
        shifted, err_lost, err_gained, metric_rows = 0, 0, 0, 0
        for a, b in zip(stored, cor):
            if a["kind"] != "span":
                assert a == b, f"{o['run_id']} {a['evidence_id']}: a non-span item changed"
                metric_rows += a["kind"] == "metric_sample"
                continue
            assert all(a.get(k) == b.get(k) for k in ("trace_id", "span_id", "service")), f"{o['run_id']}: span identity changed"
            if any(a.get(k) != b.get(k) for k in FIELDS):
                shifted += 1
                err_lost += bool(b.get("error")) and not a.get("error")
                err_gained += bool(a.get("error")) and not b.get("error")
        fixed = dict(rec, evidence=cor + [e for e in rec["evidence"] if not e.get("exposed_at_steps")])
        body = json.dumps(fixed, indent=2).encode()
        open(os.path.join(out, o["run_id"] + ".json"), "wb").write(body)
        spans = sum(e["kind"] == "span" for e in stored)
        print(json.dumps({"run_id": o["run_id"], "artifact": o["artifact"], "problem_id": o["problem_id"],
                          "record_sha256": sha(raw), "corrected_sha256": sha(body), "items": len(stored),
                          "spans": spans, "spans_shifted": shifted, "error_flags_lost": err_lost,
                          "error_flags_gained": err_gained, "metric_samples": metric_rows}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(*sys.argv[1:]))
