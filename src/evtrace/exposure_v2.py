"""Corrected reading of trace tables, written Nov 12, 2026 beside the registered exposure.py (deviation 5).

Why. AIOpsLab's read_traces returns a whitespace-aligned table with nine columns: trace_id, span_id,
parent_span, service_name, operation_name, start_time, duration, has_error, response. The registered
parser (exposure._table) splits a row from the left, one cell per column. An operation name that holds a
space ("HTTP POST /user", "router frontend egress") then pushes its later words into the next cells: the
record keeps the operation cut to its first word, a wrong start time and duration (or none), the error flag
read from the wrong cell and the response merged with other cells. Ids, trace ids, span ids and services
are not affected (Rulings of Nov 11, 2026, R11).

What this file does. For a table whose header is exactly those nine columns, a row is read from both ends:
four cells from the left, four from the right, and what lies between is the operation name. The parent
span, which the registered record never kept, is kept as "parent_span". Every other table, and every other
kind of observation, is read exactly as the registered parser reads it, so a corrected record has the same
item ids, in the same order, as the registered record of the same run.

The registered exposure.py and every stored record.json stay byte for byte as they are.
"""
from __future__ import annotations

from .exposure import ExposureLog, _COLUMNS, _pick, _table
from .record import normalize_span_id, normalize_trace_id

HEAD = ["trace_id", "span_id", "parent_span", "service_name"]
TAIL = ["start_time", "duration", "has_error", "response"]


def nine_column_rows(table: str) -> list[dict] | None:
    """Rows of an AIOpsLab trace table read from both ends, or None when the header is not that table."""
    text = table.strip()
    if not text:
        return None
    lines = [l for l in text.splitlines() if l.strip() and not set(l.strip()) <= set("-+|= ")]
    header = lines[0].split()
    if header != HEAD + ["operation_name"] + TAIL:
        return None
    rows = []
    for line in lines[1:]:
        t = line.split()
        if len(t) < 9:
            continue  # the registered parser drops a short row too
        rows.append(dict(zip(HEAD, t[:4])) | {"operation_name": " ".join(t[4:-4])} | dict(zip(TAIL, t[-4:])))
    return rows


class CorrectedExposureLog(ExposureLog):
    """ExposureLog whose spans() reads the nine-column trace table from both ends."""

    def spans(self, step: int, table: str) -> list[str]:
        rows = nine_column_rows(table)
        if rows is None:
            return super().spans(step, table)
        out = []
        for row in rows:
            col = {k: _pick(row, names) for k, names in _COLUMNS.items()}
            if not col["trace_id"] or not col["span_id"]:
                continue
            try:
                tid, sid = normalize_trace_id(col["trace_id"]), normalize_span_id(col["span_id"])
            except ValueError:
                continue
            item = {"kind": "span", "trace_id": tid, "span_id": sid, "service": col["service"] or ""}
            if col["operation"]:
                item["operation"] = col["operation"]
            if col["start"]:
                item["timestamp"] = col["start"]
            if col["duration"]:
                try:
                    item["duration_us"] = float(col["duration"])
                except ValueError:
                    pass
            if col["error"]:
                item["error"] = col["error"].strip().lower() in ("true", "1", "yes")
            if col["status"]:
                item["status"] = col["status"]
            parent = (row.get("parent_span") or "").strip()
            if parent:
                item["parent_span"] = parent
            out.append(self._add(("span", tid, sid), step, item))
        return out


def registered_rows_differ(table: str) -> int:
    """Number of rows of a nine-column trace table that the registered parser reads into shifted cells."""
    rows = nine_column_rows(table)
    if rows is None:
        return 0
    return sum(1 for r in rows if " " in r["operation_name"])


__all__ = ["CorrectedExposureLog", "nine_column_rows", "registered_rows_differ", "_table"]
