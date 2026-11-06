"""Provenance records: loading, schema validation and identifier normalization (manuscript Section 3)."""
from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from importlib import resources
from typing import Any

import jsonschema

LABELS = ("supported", "partly_supported", "unsupported", "contradicted")
SUPPORT_LINKS = ("supports", "partly_supports")
_HEX = re.compile(r"^[0-9a-fA-F]+$")


def schema() -> dict:
    """Return the JSON Schema of a provenance record."""
    return json.loads(resources.files("evtrace").joinpath("data/provenance.schema.json").read_text())


def schema_errors(record: dict) -> list[str]:
    """Return every schema violation of a record as 'path: message'."""
    validator = jsonschema.Draft202012Validator(schema(), format_checker=jsonschema.FormatChecker())
    out = []
    for err in sorted(validator.iter_errors(record), key=lambda e: list(e.absolute_path)):
        path = "/".join(str(p) for p in err.absolute_path) or "(record)"
        out.append(f"{path}: {err.message}")
    return out


def normalize_trace_id(raw: str) -> str:
    """Return the OpenTelemetry form of a trace identifier: 32 lowercase hex characters.

    Jaeger may print identifiers without leading zeros; they are padded back. A value that is
    not hex, is longer than 32 characters or is all zeros raises ValueError."""
    return _normalize(raw, 32)


def normalize_span_id(raw: str) -> str:
    """Return the OpenTelemetry form of a span identifier: 16 lowercase hex characters."""
    return _normalize(raw, 16)


def _normalize(raw: str, width: int) -> str:
    value = str(raw).strip().lower()
    if value.startswith("0x"):
        value = value[2:]
    if not value or not _HEX.match(value) or len(value) > width:
        raise ValueError(f"not a {width}-character hex identifier: {raw!r}")
    value = value.rjust(width, "0")
    if set(value) == {"0"}:
        raise ValueError(f"all-zero identifier is invalid: {raw!r}")
    return value


def digest(text: str) -> str:
    """Return the first 16 hex characters of the SHA-256 of a text line."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]


def parse_time(value: str | None) -> datetime | None:
    """Parse an ISO 8601 date and time; a value without a zone is read as UTC."""
    if not value:
        return None
    raw = str(value).strip()
    if raw.isdigit():  # epoch time as Jaeger and Prometheus store it: seconds, ms, microseconds or ns
        n = int(raw)
        scale = 1e9 if len(raw) >= 19 else 1e6 if len(raw) >= 16 else 1e3 if len(raw) >= 13 else 1
        return datetime.fromtimestamp(n / scale, tz=timezone.utc)
    dt = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


@dataclass
class Record:
    """One provenance record with lookup tables built once."""

    data: dict[str, Any]
    evidence: dict[str, dict] = field(init=False)
    claims: dict[str, dict] = field(init=False)

    def __post_init__(self) -> None:
        self.evidence = {e["evidence_id"]: e for e in self.data.get("evidence", [])}
        self.claims = {c["claim_id"]: c for c in self.data.get("claims", [])}

    @classmethod
    def load(cls, path: str) -> "Record":
        with open(path, encoding="utf-8") as fh:
            return cls(json.load(fh))

    @property
    def final_step(self) -> int | None:
        return self.data.get("final_step")
