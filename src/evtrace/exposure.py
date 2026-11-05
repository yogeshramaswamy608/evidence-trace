"""Exposure log: parse each observation returned to the agent into evidence items (manuscript Section 5.3).

The wrapper never changes the text the agent sees; it only records what was in it. AIOpsLab's
read_traces returns its trace CSV as a text table; the column names are matched loosely because
the pilot confirms them against the pinned commit."""
from __future__ import annotations

import csv
import io
import re
from dataclasses import dataclass, field

from .record import digest, normalize_span_id, normalize_trace_id

_TS = re.compile(r"\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:?\d{2})?")
_COLUMNS = {
    "trace_id": ("trace_id", "traceid", "trace id"),
    "span_id": ("span_id", "spanid", "span id"),
    "service": ("service_name", "service", "servicename"),
    "operation": ("operation_name", "operation", "operationname", "name"),
    "start": ("start_time", "starttime", "start", "timestamp"),
    "duration": ("duration", "duration_us"),
    "error": ("has_error", "error", "is_error"),
    "status": ("response", "status", "status_code"),
}


@dataclass
class ExposureLog:
    """Evidence items of one run keyed by their identity, with the steps that exposed them."""

    items: dict[str, dict] = field(default_factory=dict)
    _keys: dict[tuple, str] = field(default_factory=dict)

    def _add(self, key: tuple, step: int, item: dict) -> str:
        eid = self._keys.get(key)
        if eid is None:
            eid = f"e{len(self.items) + 1}"
            self._keys[key] = eid
            self.items[eid] = {"evidence_id": eid, **item, "exposed_at_steps": []}
        if step not in self.items[eid]["exposed_at_steps"]:
            self.items[eid]["exposed_at_steps"].append(step)
        return eid

    def record(self, action: str, step: int, observation: str, **meta) -> list[str]:
        """Record one observation; returns the evidence identifiers it contained."""
        action = action.lower()
        if action in ("read_traces", "get_traces"):
            ids = self.spans(step, observation)
            if ids:
                return ids
        if action in ("read_metrics", "get_metrics"):
            ids = self.metrics(step, observation)
            if ids:
                return ids
        if action == "get_logs":
            return self.logs(step, observation, meta.get("source", ""))
        return self.command(step, observation, meta.get("command", action))

    def spans(self, step: int, table: str) -> list[str]:
        rows = _table(table)
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
            out.append(self._add(("span", tid, sid), step, item))
        return out

    def metrics(self, step: int, table: str) -> list[str]:
        out = []
        for row in _table(table):
            series = _pick(row, ("__name__", "metric", "series", "name"))
            value = _pick(row, ("value", "val"))
            ts = _pick(row, ("timestamp", "time", "ts"))
            if not series or value in (None, ""):
                continue
            try:
                num = float(value)
            except ValueError:
                continue
            labels = {k: v for k, v in row.items() if k and k not in ("__name__", "metric", "series", "name", "value",
                                                                       "val", "timestamp", "time", "ts") and v}
            item = {"kind": "metric_sample", "series": series, "labels": labels, "value": num}
            service = labels.get("service") or labels.get("service_name") or labels.get("container")
            if service:
                item["service"] = service
            if ts:
                item["timestamp"] = ts
            out.append(self._add(("metric", series, tuple(sorted(labels.items())), ts), step, item))
        return out

    def logs(self, step: int, text: str, source: str) -> list[str]:
        out = []
        for i, line in enumerate(l for l in text.splitlines() if l.strip()):
            item = {"kind": "log_record", "source": source, "line_index": i, "text_digest": digest(line), "text": line}
            if source:
                item["service"] = source.split("/")[-1]
            m = _TS.search(line)
            if m:
                item["timestamp"] = m.group(0).replace(" ", "T")
            out.append(self._add(("log", source, digest(line)), step, item))
        return out

    def command(self, step: int, text: str, command: str) -> list[str]:
        out = []
        for i, line in enumerate(l for l in text.splitlines() if l.strip()):
            item = {"kind": "command_output", "command": command, "line_index": i,
                    "text_digest": digest(line), "text": line}
            out.append(self._add(("cmd", command, step, i), step, item))
        return out

    def evidence(self) -> list[dict]:
        return list(self.items.values())


def _pick(row: dict, names: tuple) -> str | None:
    lowered = {(k or "").strip().lower(): v for k, v in row.items()}
    for n in names:
        if n in lowered and lowered[n] not in (None, ""):
            return str(lowered[n]).strip()
    return None


def _table(text: str) -> list[dict]:
    """Read a CSV text or a whitespace- or pipe-aligned text table into rows."""
    text = text.strip()
    if not text:
        return []
    first = text.splitlines()[0]
    if "," in first:
        return list(csv.DictReader(io.StringIO(text)))
    sep = "|" if "|" in first else None
    lines = [l for l in text.splitlines() if l.strip() and not set(l.strip()) <= set("-+|= ")]
    header = [h.strip() for h in (lines[0].split(sep) if sep else lines[0].split())]
    rows = []
    for l in lines[1:]:
        cells = [c.strip() for c in (l.split(sep) if sep else l.split(None, len(header) - 1))]
        if sep:
            cells = cells[1:-1] if l.strip().startswith("|") else cells
            header_cells = header[1:-1] if lines[0].strip().startswith("|") else header
        else:
            header_cells = header
        if len(cells) == len(header_cells):
            rows.append(dict(zip(header_cells, cells)))
    return rows
