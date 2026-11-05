"""Stage 1, structural checks: the schema and rules R1 to R4 (manuscript Sections 3.2 and 4)."""
from __future__ import annotations

from dataclasses import dataclass

from .record import SUPPORT_LINKS, Record, schema_errors


@dataclass(frozen=True)
class Violation:
    rule: str          # SCHEMA, R1, R2, R3 or R4
    claim_id: str      # empty for record-level schema errors
    detail: str


def check(record: Record) -> list[Violation]:
    """Return every structural violation of a record; an empty list means well formed."""
    out = [Violation("SCHEMA", "", e) for e in schema_errors(record.data)]
    if out:
        return out
    out += _r1(record) + _r2(record) + _r3(record) + _r4(record)
    return out


def exposed_before_final(record: Record, evidence_id: str) -> bool:
    """True when the item was returned to the agent at a step before the final answer (R2)."""
    item = record.evidence.get(evidence_id)
    if not item or not item.get("exposed_at_steps"):
        return False
    final = record.final_step
    return final is None or min(item["exposed_at_steps"]) < final


def _r1(record: Record) -> list[Violation]:
    out = []
    for c in record.claims.values():
        if c["type"] not in ("observation", "root_cause") or c.get("no_evidence_found"):
            continue
        if not any(l["link_type"] in SUPPORT_LINKS for l in c["links"]) and not any(
            l["link_type"] == "derived_from" for l in c["links"]
        ):
            out.append(Violation("R1", c["claim_id"], "no supports or partly_supports link and no statement of no evidence"))
    return out


def _r2(record: Record) -> list[Violation]:
    out = []
    for c in record.claims.values():
        for l in c["links"]:
            if l["link_type"] == "derived_from":
                if l["target"] not in record.claims:
                    out.append(Violation("R2", c["claim_id"], f"derived_from target {l['target']} is not a claim"))
                continue
            if l["target"] not in record.evidence:
                out.append(Violation("R2", c["claim_id"], f"link target {l['target']} is not an evidence item"))
            elif not exposed_before_final(record, l["target"]):
                out.append(Violation("R2", c["claim_id"], f"evidence {l['target']} was never exposed before the final answer"))
    return out


def _r3(record: Record) -> list[Violation]:
    graph = {cid: [l["target"] for l in c["links"] if l["link_type"] == "derived_from" and l["target"] in record.claims]
             for cid, c in record.claims.items()}
    state: dict[str, int] = {}
    cyclic: set[str] = set()

    def visit(node: str) -> None:
        state[node] = 1
        for nxt in graph[node]:
            if state.get(nxt) == 1:
                cyclic.add(node)
            elif state.get(nxt) is None:
                visit(nxt)
        state[node] = 2

    for node in graph:
        if node not in state:
            visit(node)
    return [Violation("R3", cid, "derived_from links form a cycle") for cid in sorted(cyclic)]


def reaches_evidence(record: Record, claim_id: str, seen: frozenset = frozenset()) -> bool:
    """True when a claim reaches an exposed evidence item through derived_from links ending in support."""
    if claim_id in seen or claim_id not in record.claims:
        return False
    c = record.claims[claim_id]
    if any(l["link_type"] in SUPPORT_LINKS and exposed_before_final(record, l["target"]) for l in c["links"]):
        return True
    return any(reaches_evidence(record, l["target"], seen | {claim_id})
               for l in c["links"] if l["link_type"] == "derived_from")


def _r4(record: Record) -> list[Violation]:
    return [Violation("R4", cid, "root-cause claim reaches no supporting evidence item")
            for cid, c in record.claims.items()
            if c["type"] == "root_cause" and not c.get("no_evidence_found") and not reaches_evidence(record, cid)]
