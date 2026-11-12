"""Test the 30 check claims of the labeling queue against the corrected exposure records (P2 b, deviation 2).

Usage: python scripts/check_claim_defects.py QUEUE_KEY.json ARTIFACT_DIR CORRECTED_DIR > OUT.json
QUEUE_KEY.json is the private answer key of the labeling queue (kept outside this repository until the
re-code of Nov 24, 2026); it holds the check claims and their labels by construction, and no human label.

Each check claim is rebuilt with the registered gold.py from the stored record of its run, with the build
call of the labeling queue (seed 20261105, one claim per template), and must give the same text back.
Then the item it is linked to, and the run's corrected record (evtrace.exposure_v2), are tested with the
rules below. The rules were written before this script was first run and do not change after it.

Fault signal of an item (FAULT): a span whose has_error is True or whose response is a number of 400 or
more; a log record or command output line holding one of ERROR_WORDS (case-insensitive word match).
T5 ("A and B both showed the fault", built as partly supported, linked to one item of A):
  a_fault   the linked item carries a fault signal
  b_items   exposed items that name B: spans and log records of service B, command output lines holding B
  b_fault   one of them carries a fault signal
  b_clean   B has items and none carries a fault signal: the record speaks against B's part
T6 ("A served OP", built as supported, linked to one span of A):
  op_cut     the registered record's operation differs from the table row (the parser defect, R11)
  caller     a span of another service in the same trace has this span as its parent and the same
             operation name: the linked span is the caller's side of that call
  internal   the span's parent is a span of the same service: an internal step, not a request served
Each test is also run on the registered record (fields ending "_registered" or the registered operation),
so the output shows which outcomes the parser defect changes.
Nothing here reads a human label.
"""
from __future__ import annotations

import glob
import json
import os
import re
import sys

from evtrace import gold
from evtrace.record import normalize_span_id

ERROR_WORDS = ("error", "errors", "exception", "failed", "failure", "refused", "crashloopbackoff",
               "oomkilled", "timeout", "timed out", "unavailable", "panic", "fatal")
_WORDS = re.compile(r"\b(" + "|".join(re.escape(w) for w in ERROR_WORDS) + r")\b", re.IGNORECASE)


def fault(e: dict) -> bool:
    if e["kind"] == "span":
        st = str(e.get("status", ""))
        return bool(e.get("error")) or (st.isdigit() and int(st) >= 400)
    return bool(_WORDS.search(e.get("text", "") or ""))


def norm(span: str | None) -> str | None:
    try:
        return normalize_span_id(span) if span and span != "ROOT" else span
    except ValueError:
        return span


def names(e: dict, svc: str) -> bool:
    if e["kind"] in ("span", "log_record"):
        return e.get("service") == svc
    return bool(re.search(r"(?<![\w-])" + re.escape(svc) + r"(?![\w-])", e.get("text", "") or ""))


def rebuild(src: dict, art: str) -> tuple[dict, dict, str]:
    for meta_path in sorted(glob.glob(os.path.join(art, "*", src["run_id"], "meta.json"))):
        d = os.path.dirname(meta_path)
        meta = json.load(open(meta_path, encoding="utf-8"))
        if meta.get("error") or not os.path.exists(os.path.join(d, "record.json")):
            continue
        rec = json.load(open(os.path.join(d, "record.json"), encoding="utf-8"))
        built, g = gold.build(src["run_id"], meta["problem_id"], rec["evidence"], rec.get("final_step", 99),
                              20261105, per_template=1)
        for c in built["claims"]:
            if c["claim_id"] == src["claim_id"] and c["text"] == src["text"]:
                return c, rec, g[c["claim_id"]]
    raise SystemExit(f"check claim {src['run_id']} {src['claim_id']} does not rebuild")


def main(key_path: str, art: str, cdir: str) -> int:
    key = json.load(open(key_path, encoding="utf-8"))
    out = []
    for q in key["queue"]:
        src = q["source"]
        if not src.get("is_gold"):
            continue
        claim, rec, built = rebuild(src, art)
        label, template = built.split("|")
        cor = {e["evidence_id"]: e for e in json.load(open(os.path.join(cdir, src["run_id"] + ".json"), encoding="utf-8"))["evidence"]}
        reg = {e["evidence_id"]: e for e in rec["evidence"]}
        target = claim["links"][0]["target"]
        item, item_reg = cor[target], reg[target]
        exposed = [e for e in cor.values() if e.get("exposed_at_steps")]
        row = {"key": q["key"], "run_id": src["run_id"], "template": template, "built_label": label, "text": src["text"],
               "item": target, "item_kind": item["kind"], "item_service": item.get("service")}
        if template == "T5":
            a, b = claim["services"]
            b_items = [e for e in exposed if names(e, b)]
            reg_b = [e for e in reg.values() if e.get("exposed_at_steps") and names(e, b)]
            row.update({"a_fault_registered": fault(item_reg), "b_fault_registered": any(fault(e) for e in reg_b)})
            row.update({"a": a, "b": b, "a_fault": fault(item), "b_items": len(b_items),
                        "b_fault": any(fault(e) for e in b_items),
                        "b_clean": bool(b_items) and not any(fault(e) for e in b_items)})
        elif template == "T6":
            children = [e for e in exposed if e["kind"] == "span" and e.get("trace_id") == item["trace_id"]
                        and norm(e.get("parent_span")) == item["span_id"]]
            parent = [e for e in exposed if e["kind"] == "span" and e.get("trace_id") == item["trace_id"]
                      and e["span_id"] == norm(item.get("parent_span"))]
            row.update({"operation_registered": item_reg.get("operation"), "operation_table": item.get("operation"),
                        "op_cut": item_reg.get("operation") != item.get("operation"),
                        "caller": any(c.get("service") != item.get("service") and c.get("operation") == item.get("operation")
                                      for c in children),
                        "internal": any(p.get("service") == item.get("service") for p in parent),
                        "parent_service": parent[0].get("service") if parent else ("ROOT" if item.get("parent_span") == "ROOT" else None)})
        out.append(row)
    json.dump(out, sys.stdout, indent=1, sort_keys=True)
    print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main(*sys.argv[1:]))
