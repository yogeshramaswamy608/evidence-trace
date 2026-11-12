"""Count the registered trace parser's defect over all main runs (deviation 5), from data/corrected/manifest.jsonl
and the corrected records it names, and count the metric tables the agents read, which the registered parser
keeps as command output lines (its metric reader knows no "kpi_name" column), from the stored session files.
Usage: python scripts/defect_counts.py CORRECTED_DIR ARTIFACT_DIR > docs/defect_counts.json"""
import json
import sys

from evtrace import session


def metric_tables(art: str, m: list[dict]) -> dict:
    tables, rows, runs, headers = 0, 0, set(), set()
    for x in m:
        data = json.load(open(f"{art}/{x['artifact']}/{x['run_id']}/session.json", encoding="utf-8"))
        pending = None
        for it in data.get("trace", []):
            if it.get("role") == "assistant":
                pending = session.parse_action(str(it.get("content", "")))[0]
            elif pending:
                lines = [l for l in str(it.get("content", "")).strip().splitlines() if l.strip()]
                if pending in ("read_metrics", "get_metrics") and lines and "value" in lines[0].split():
                    tables += 1
                    rows += len(lines) - 1
                    runs.add(x["run_id"])
                    headers.add(" ".join(lines[0].split()))
                pending = None
    return {"metric_tables_read": tables, "metric_table_rows": rows, "runs_with_metric_tables": len(runs),
            "metric_table_headers": sorted(headers)}


def main(cdir: str, art: str, manifest: str = "data/corrected/manifest.jsonl") -> int:
    m = [json.loads(l) for l in open(manifest, encoding="utf-8")]
    err = 0
    for x in m:
        rec = json.load(open(f"{cdir}/{x['run_id']}.json", encoding="utf-8"))
        err += sum(1 for e in rec["evidence"] if e["kind"] == "span" and e.get("error"))
    out = {"runs": len(m), "items": sum(x["items"] for x in m), "spans": sum(x["spans"] for x in m),
           "spans_shifted": sum(x["spans_shifted"] for x in m), "runs_with_shifted_spans": sum(x["spans_shifted"] > 0 for x in m),
           "spans_with_error_in_table": err, "error_flags_lost": sum(x["error_flags_lost"] for x in m),
           "error_flags_gained": sum(x["error_flags_gained"] for x in m),
           "metric_samples_recorded": sum(x["metric_samples"] for x in m), **metric_tables(art, m)}
    json.dump(out, sys.stdout, indent=2, sort_keys=True)
    print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main(*sys.argv[1:]))
