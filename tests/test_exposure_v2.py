"""Tests of the corrected trace reading (deviation 5, Nov 12, 2026)."""
from evtrace.exposure import ExposureLog
from evtrace.exposure_v2 import CorrectedExposureLog, nine_column_rows, registered_rows_differ

TABLE = """        trace_id          span_id      parent_span   service_name      operation_name       start_time  duration  has_error response
14c255f2ec4a02ca 3ea1ece8d7263404 14c255f2ec4a02ca       frontend /user.User/CheckUser 1793946309400348  10000595      False  Unknown
14c255f2ec4a02ca 14c255f2ec4a02ca             ROOT       frontend     HTTP POST /user 1793946309400306  10000662       True      500
"""


def test_rows_read_from_both_ends():
    rows = nine_column_rows(TABLE)
    assert rows[1]["operation_name"] == "HTTP POST /user"
    assert rows[1]["has_error"] == "True" and rows[1]["response"] == "500"
    assert registered_rows_differ(TABLE) == 1


def test_same_ids_and_fields_fixed():
    reg, cor = ExposureLog(), CorrectedExposureLog()
    a, b = reg.spans(1, TABLE), cor.spans(1, TABLE)
    assert a == b == ["e1", "e2"]
    assert reg.items["e1"]["operation"] == cor.items["e1"]["operation"] == "/user.User/CheckUser"
    assert reg.items["e2"]["operation"] == "HTTP"          # the registered defect, kept as it was
    assert reg.items["e2"].get("error") is False           # flag read from the wrong cell
    assert cor.items["e2"]["operation"] == "HTTP POST /user"
    assert cor.items["e2"]["error"] is True and cor.items["e2"]["status"] == "500"
    assert cor.items["e2"]["duration_us"] == 10000662.0 and cor.items["e2"]["parent_span"] == "ROOT"


def test_other_tables_unchanged():
    csv_text = "trace_id,span_id,service_name,operation_name\n" + "a" * 32 + "," + "b" * 16 + ",geo,get\n"
    reg, cor = ExposureLog(), CorrectedExposureLog()
    assert reg.spans(1, csv_text) == cor.spans(1, csv_text)
    assert reg.items == cor.items


def test_gold_v2_labels_follow_from_the_item():
    from evtrace import gold_v2
    log = CorrectedExposureLog()
    log.spans(1, TABLE)
    rec, g = gold_v2.build("r", "p", log.evidence(), 5, 20261105)
    by = {c["claim_id"]: c for c in rec["claims"]}
    items = {e["evidence_id"]: e for e in rec["evidence"]}
    for cid, lt in g.items():
        label, template = lt.split("|")
        c = by[cid]
        if template in ("V3", "V4"):
            it = items[c["links"][0]["target"]]
            assert (template == "V3") == it["error"] and label == ("supported" if it["error"] else "contradicted")
        if template == "V1":
            it = items[c["links"][0]["target"]]
            assert f"took {it['duration_us'] / 1000:g} ms" in c["text"] and label == "supported"
    assert "T5" not in {v.split("|")[1] for v in g.values()} and "T6" not in {v.split("|")[1] for v in g.values()}
