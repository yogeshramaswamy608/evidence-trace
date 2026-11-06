import json
from pathlib import Path

import pytest

from evtrace import gold, rules, session, stats
from evtrace.cli import main
from evtrace.record import Record, normalize_span_id, normalize_trace_id, schema_errors
from evtrace.verify import consistency, stage2_judge, verify

FIX = Path(__file__).parent / "fixtures" / "session_synthetic.json"
W3C_TRACE, W3C_SPAN = "0af7651916cd43dd8448eb211c80319c", "b7ad6b7169203331"


def base_record(**extra):
    rec = {"run_id": "r1", "problem_id": "p1", "final_step": 5,
           "evidence": [
               {"evidence_id": "e1", "kind": "span", "trace_id": W3C_TRACE, "span_id": W3C_SPAN,
                "service": "geo", "timestamp": "2026-11-05T08:00:01Z", "exposed_at_steps": [1]},
               {"evidence_id": "e2", "kind": "metric_sample", "series": "cpu", "value": 0.9, "service": "geo",
                "timestamp": "2026-11-05T08:00:00Z", "exposed_at_steps": [2]},
               {"evidence_id": "e3", "kind": "log_record", "text": "late", "exposed_at_steps": [7]}],
           "claims": []}
    rec.update(extra)
    return rec


def claim(cid, ctype="observation", links=(), **kw):
    return {"claim_id": cid, "text": cid, "type": ctype, "links": [dict(link_type=t, target=g) for t, g in links], **kw}


# identifiers

def test_normalize_pads_and_lowercases():
    assert normalize_span_id("7AD6B7169203331") == "07ad6b7169203331"
    assert normalize_trace_id("0x" + W3C_TRACE.upper()) == W3C_TRACE


@pytest.mark.parametrize("bad", ["", "zz", "0" * 16, "1" * 17])
def test_normalize_rejects(bad):
    with pytest.raises(ValueError):
        normalize_span_id(bad)


# schema and rules R1 to R4

def test_schema_rejects_bad_span_id():
    rec = base_record()
    rec["evidence"][0]["span_id"] = "XYZ"
    assert any("span_id" in e for e in schema_errors(rec))


def test_well_formed_record_has_no_violations():
    rec = base_record(claims=[claim("c1", links=[("supports", "e1")]),
                              claim("c2", "root_cause", links=[("derived_from", "c1")])])
    assert rules.check(Record(rec)) == []


def test_r1_missing_support():
    out = rules.check(Record(base_record(claims=[claim("c1")])))
    assert [v.rule for v in out] == ["R1"]


def test_r1_allows_explicit_no_evidence():
    assert rules.check(Record(base_record(claims=[claim("c1", no_evidence_found=True)]))) == []


def test_r2_item_exposed_after_final_answer():
    out = rules.check(Record(base_record(claims=[claim("c1", links=[("supports", "e3")])])))
    assert "R2" in {v.rule for v in out}


def test_r2_unknown_target():
    out = rules.check(Record(base_record(claims=[claim("c1", links=[("supports", "nope")])])))
    assert "R2" in {v.rule for v in out}


def test_r3_cycle():
    rec = base_record(claims=[claim("a", "inference", links=[("derived_from", "b")]),
                              claim("b", "inference", links=[("derived_from", "a")])])
    assert {v.rule for v in rules.check(Record(rec))} == {"R3"}


def test_r4_root_cause_without_path():
    rec = base_record(claims=[claim("a", "inference"), claim("rc", "root_cause", links=[("derived_from", "a")])])
    assert "R4" in {v.rule for v in rules.check(Record(rec))}


# stage 2 and aggregation

def test_consistency_value_and_window():
    item = {"service": "geo", "value": 0.9, "timestamp": "2026-11-05T08:00:00Z"}
    c = {"services": ["geo"], "value": 0.9,
         "window": {"start": "2026-11-05T07:59:00Z", "end": "2026-11-05T08:01:00Z"}}
    assert consistency(c, item, "supports") == []
    assert consistency({**c, "value": 2.0}, item, "supports") == ["S2_VALUE_MISMATCH"]
    far = {"start": "2026-11-05T09:00:00Z", "end": "2026-11-05T09:01:00Z"}
    assert consistency({**c, "window": far}, item, "supports") == ["S2_OUTSIDE_WINDOW"]


def test_labels_four_classes():
    rec = base_record(claims=[
        claim("ok", links=[("supports", "e2")], services=["geo"], value=0.9),
        claim("bad", links=[("supports", "e2")], services=["geo"], value=3.0),
        claim("none", services=["ghost"]),
        claim("part", links=[("partly_supports", "e1")], services=["geo", "rate"]),
        claim("rec", "recommendation")])
    res = verify(Record(rec))
    assert {k: r.label for k, r in res.items()} == {
        "ok": "supported", "bad": "contradicted", "none": "unsupported", "part": "partly_supported", "rec": None}


def test_inheritance_through_derived_from():
    rec = base_record(claims=[
        claim("o1", links=[("supports", "e1")], services=["geo"]),
        claim("o2", services=["ghost"]),
        claim("rc1", "root_cause", links=[("derived_from", "o1")]),
        claim("rc2", "root_cause", links=[("derived_from", "o2")])])
    res = verify(Record(rec))
    assert res["rc1"].label == "supported" and res["rc2"].label == "unsupported"


def test_schema_failure_marks_all_unsupported():
    rec = base_record(claims=[claim("c1", links=[("supports", "e1")])])
    rec["claims"][0]["type"] = "guess"
    assert verify(Record(rec))["c1"].reasons == ["S1_SCHEMA"]


def test_custom_judge_contradiction_wins():
    rec = base_record(claims=[claim("c", links=[("supports", "e1")], services=["geo"])])
    assert verify(Record(rec), lambda c, items: "contradicts")["c"].label == "contradicted"


# session, exposure and gold labels

def test_session_exposure_counts():
    log, final = session.exposure(session.load(FIX))
    kinds = [e["kind"] for e in log.evidence()]
    assert kinds.count("span") == 3 and kinds.count("metric_sample") == 3
    assert kinds.count("log_record") == 2 and kinds.count("command_output") == 3
    assert final == 5
    span = next(e for e in log.evidence() if e["kind"] == "span" and e["service"] == "geo")
    assert span["span_id"] == "07ad6b7169203331" and span["exposed_at_steps"] == [1]


def test_exposure_record_is_schema_valid():
    log, final = session.exposure(session.load(FIX))
    rec = {"run_id": "s", "problem_id": "p", "final_step": final, "evidence": log.evidence(), "claims": []}
    assert schema_errors(rec) == []


def test_gold_by_construction_matches_verifier():
    data = session.load(FIX)
    log, final = session.exposure(data)
    record, labels = gold.build("s", "p", log.evidence(), final, seed=7)
    assert schema_errors(record) == []
    res = verify(Record(record))
    wrong = {cid: (lab, res[cid].label) for cid, lab in labels.items() if lab.split("|")[0] != res[cid].label}
    assert wrong == {}
    assert {lab.split("|")[1] for lab in labels.values()} == set(gold.TEMPLATES)


def test_gold_is_deterministic():
    data = session.load(FIX)
    log, final = session.exposure(data)
    assert gold.build("s", "p", log.evidence(), final, 7) == gold.build("s", "p", log.evidence(), final, 7)


# statistics

def test_kappa_known_value():
    a = ["x"] * 20 + ["y"] * 30
    b = ["x"] * 15 + ["y"] * 5 + ["x"] * 10 + ["y"] * 20
    # po = 35/50 = 0.7; pe = (20*25 + 30*25)/2500 = 0.5; kappa = 0.4
    assert stats.cohen_kappa(a, b) == pytest.approx(0.4)


def test_mcnemar_exact_known_values():
    assert stats.mcnemar_exact(0, 0) == 1.0
    assert stats.mcnemar_exact(0, 6) == pytest.approx(2 / 64)
    assert stats.mcnemar_exact(5, 5) == 1.0


def test_holm():
    assert stats.holm([0.01, 0.04, 0.03]) == pytest.approx([0.03, 0.06, 0.06])


def test_prf():
    assert stats.prf([True, True, False, False], [True, False, True, False]) == (0.5, 0.5, 0.5)


def test_cluster_bootstrap_bounds():
    point, lo, hi = stats.cluster_bootstrap({"a": [1, 1], "b": [0, 1], "c": [1, 0]}, lambda xs: sum(xs) / len(xs), reps=500)
    assert lo <= point <= hi


# command line

def test_cli_selftest(capsys):
    assert main(["selftest", str(FIX)]) == 0
    out = capsys.readouterr().out
    assert "kappa 1.000" in out and "recall 1.000" in out


def test_cli_gold_and_verify(tmp_path, capsys):
    out = tmp_path / "g.json"
    assert main(["gold", str(FIX), "--out", str(out)]) == 0
    rec = tmp_path / "r.json"
    rec.write_text(json.dumps(json.loads(out.read_text())["record"]))
    assert main(["verify", str(rec)]) == 0
    assert main(["check", str(rec)]) == 1  # the constructed unsupported claims break R1, R2 and R4 on purpose


# condition B locators

from evtrace import locate  # noqa: E402


def test_locate_resolves_each_kind():
    log, final = session.exposure(session.load(FIX))
    ev = log.evidence()
    span = locate.resolve(f"span:{W3C_TRACE}/7ad6b7169203331", ev)
    assert span and next(e for e in ev if e["evidence_id"] == span)["service"] == "geo"
    assert locate.resolve("log:2026-11-05T08:00:01Z ERROR geo: mongo connection refused", ev)
    assert locate.resolve("metric:container_cpu_usage_seconds_total@2026-11-05T08:00:00Z", ev)
    assert locate.resolve("cmd:geo-7d9f 0/1 CrashLoopBackOff", ev)
    assert locate.resolve("span:deadbeef/0000000000000001", ev) is None


def test_condition_b_summary_to_record():
    log, final = session.exposure(session.load(FIX))
    text = "```json\n" + json.dumps({"claims": [
        {"claim_id": "c1", "text": "geo span failed", "type": "observation", "services": ["geo"],
         "links": [{"link_type": "supports", "target": f"span:{W3C_TRACE}/07ad6b7169203331"}]},
        {"claim_id": "c2", "text": "made up", "type": "observation",
         "links": [{"link_type": "supports", "target": "log:never shown"}]},
        {"claim_id": "c3", "text": "geo is the root cause", "type": "root_cause",
         "links": [{"link_type": "derived_from", "target": "c1"}]}]}) + "\n```"
    rec, unresolved = locate.to_record(locate.parse_summary(text), "r", "p", log.evidence(), final)
    assert unresolved == ["log:never shown"]
    assert schema_errors(rec) == []
    res = verify(Record(rec))
    assert res["c1"].label == "supported" and res["c2"].label == "unsupported" and res["c3"].label == "supported"


def test_parse_summary_rejects_free_text():
    assert locate.parse_summary("the geo service failed") is None


def test_empty_reply_is_sent_as_marker(monkeypatch):
    # Pilot run 42138467998 (Nov 5, 2026): an empty assistant reply with cache_control gave HTTP 400.
    import io, json as _json
    from evtrace import agent as ag
    sent = {}

    class Resp(io.BytesIO):
        def __enter__(self): return self
        def __exit__(self, *a): return False

    def fake_urlopen(req, timeout=0):
        sent["body"] = _json.loads(req.data)
        return Resp(_json.dumps({"content": [{"type": "text", "text": "ok"}], "usage": {}}).encode())

    monkeypatch.setenv("LLM_API_KEY", "x")
    monkeypatch.setattr(ag.urllib.request, "urlopen", fake_urlopen)
    a = ag.ModelAgent("claude-haiku-5-5") if hasattr(ag, "ModelAgent") else None
    if a is None:
        cls = [v for k, v in vars(ag).items() if isinstance(v, type) and hasattr(v, "_call")][0]
        a = cls("claude-haiku-5-5")
    a.system = "s"
    a.messages = [{"role": "user", "content": "q"}, {"role": "assistant", "content": ""}, {"role": "user", "content": "next"}]
    a._call()
    texts = [m["content"] if isinstance(m["content"], str) else m["content"][0]["text"] for m in sent["body"]["messages"]]
    assert "" not in texts and ag.EMPTY_REPLY in texts
    assert a.messages[1]["content"] == ""


def test_judge_must_differ_from_agents():
    import pytest
    from evtrace.verify import ModelJudge
    with pytest.raises(ValueError):
        ModelJudge("claude-sonnet-5-5")
    assert ModelJudge("claude-opus-5-5").model == "claude-opus-5-5"


def test_judge_logs_request_and_response(tmp_path, monkeypatch):
    import io, json as _json
    from evtrace import verify as vf

    class Resp(io.BytesIO):
        def __enter__(self): return self
        def __exit__(self, *a): return False

    monkeypatch.setenv("LLM_API_KEY", "x")
    monkeypatch.setattr(vf.urllib.request, "urlopen",
                        lambda req, timeout=0: Resp(_json.dumps({"content": [{"type": "text", "text": "entails"}], "usage": {}}).encode()))
    log = tmp_path / "judge.jsonl"
    j = vf.ModelJudge("claude-opus-5-5", log_path=str(log))
    assert j({"claim_id": "c1", "text": "geo errors"}, [{"kind": "log", "service": "geo", "text": "error"}]) == "entails"
    rows = [_json.loads(l) for l in log.read_text().splitlines()]
    assert len(rows) == 1 and rows[0]["claim_id"] == "c1" and rows[0]["request"]["model"] == "claude-opus-5-5" and rows[0]["utc"]


def test_sample_strata_cap_and_split():
    from evtrace import sample
    claims = [{"run_id": f"r{r}", "claim_id": f"c{i}", "model": m, "condition": cnd, "task_type": t}
              for r, (m, cnd, t) in enumerate([(m, c, t) for m in "SH" for c in "AB" for t in ("loc", "ana")] * 10)
              for i in range(12)]
    dev, test = sample.draw(claims)
    assert len(dev) == 100 and len(test) == 200
    from collections import Counter
    assert max(Counter(c["run_id"] for c in dev + test).values()) <= 5
    assert sample.draw(claims) == (dev, test)
    q = sample.queue(dev, [{"run_id": "g", "claim_id": "g1", "gold_label": "supported", "is_gold": True}])
    assert len(q) == 101 and all("gold_label" not in c for c in q)


def test_parse_time_epoch_units():
    from evtrace.record import parse_time
    a = parse_time("1793944967277000"); b = parse_time("1793944967277"); c = parse_time("1793944967")
    assert a.year == 2026 and abs((a - b).total_seconds()) < 0.001 and abs((b - c).total_seconds()) < 1
