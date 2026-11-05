"""Read an AIOpsLab session file and rebuild the exposure log of the run without changing AIOpsLab.

AIOpsLab saves each session as JSON with a "trace" list of {role, content} items: the agent's
response and the environment's response, in turn (aiopslab/session.py at commit 576c3f0). The
action name is the first function call in the agent's response."""
from __future__ import annotations

import json
import re

from .exposure import ExposureLog

_CALL = re.compile(r"\b([A-Za-z_][A-Za-z0-9_]*)\s*\((.*?)\)", re.S)
_ACTIONS = {"get_logs", "get_metrics", "read_metrics", "get_traces", "read_traces", "exec_shell", "submit"}


def parse_action(text: str) -> tuple[str, str]:
    """Return (action name, raw arguments) of the first known action call in an agent response."""
    for m in _CALL.finditer(text or ""):
        if m.group(1) in _ACTIONS:
            return m.group(1), m.group(2)
    return "unknown", ""


def load(path: str) -> dict:
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def exposure(session: dict) -> tuple[ExposureLog, int]:
    """Return the exposure log of a session and the step index of its final answer."""
    log = ExposureLog()
    trace = session.get("trace") or session.get("history") or []
    step, pending, final = 0, None, 0
    for item in trace:
        role, content = item.get("role"), str(item.get("content", ""))
        if role == "assistant":
            step += 1
            pending = parse_action(content)
            if pending[0] == "submit":
                final = step
        elif role == "env" or role == "environment" or role == "user":
            if pending and pending[0] not in ("submit", "unknown"):
                name, args = pending
                meta = {"command": args.strip() or name}
                if name == "get_logs":
                    meta["source"] = "/".join(a.strip().strip("'\"") for a in args.split(",") if a.strip())
                log.record(name, step, content, **meta)
            pending = None
    return log, final or step + 1
