"""Link recovery for free-form claims (manuscript Section 4; P1 of the rulings of Nov 11, 2026).

Condition A summaries carry no links. To verify them, candidate links are proposed by matching the
entities and words of each claim against the items exposed to the agent before its final answer.

The written rule, with no label in it:
  1. Services named. A service of the run's exposed items is named by a claim when its name appears in the
     claim text, case-insensitive, not inside a longer word; a pod name such as "user-service-5b54-xk2" names
     its service. Longer names are matched first, and a matched span of text is not matched again.
  2. Score of an item. 3 if the item belongs to a named service (its service field, or, for a command output
     line, the service name in its text), plus the number of distinct content words the claim and the item
     share (words of three or more characters, not in STOP), plus 2 if a number of the claim appears in the item.
  3. Order. Score, highest first; then the later exposure step first (closer to the conclusion), then the
     item id.
  4. Links. The first K items whose score is at least MIN_SCORE become "supports" links, flagged as recovered.
K and MIN_SCORE are chosen on the 100 development claims only, by scripts/rq2_tune.py, and frozen in FROZEN.

The capped pool of the link-blind baseline (deviation 3) uses steps 1 to 3 with K = 50 and no minimum.
"""
from __future__ import annotations

import re

STOP = frozenset("""the and was were are with that this from for not but has had have its into onto than then
they them their there which while when where who whom what also all any each both only very more most some such
pod pods service services namespace showed shows show returned return reported report agent submission
none none""".split())

_WORD = re.compile(r"[a-z0-9][a-z0-9._/:-]*[a-z0-9]")
_NUM = re.compile(r"(?<![\w.])\d+(?:\.\d+)?(?![\w.])")

FROZEN = {"k": 2, "min_score": 0}  # chosen Nov 12, 2026 by scripts/rq2_tune.py on the development claims (docs/rq2_tune.json)


def words(text: str) -> set[str]:
    return {w for w in _WORD.findall((text or "").lower()) if len(w) >= 3 and w not in STOP}


def item_text(e: dict) -> str:
    return " ".join(str(e.get(k, "")) for k in ("service", "operation", "status", "command", "source", "series", "text")
                    if e.get(k) not in (None, ""))


def named_services(claim_text: str, services: list[str]) -> list[str]:
    text = (claim_text or "").lower()
    found = []
    for s in sorted(set(services), key=lambda s: (-len(s), s)):
        pat = re.compile(r"(?<![\w-])" + re.escape(s.lower()) + r"(?![\w])")
        m = pat.search(text)
        if m:
            found.append(s)
            text = text[: m.start()] + " " * (m.end() - m.start()) + text[m.end():]
    return sorted(found)


def rank(claim_text: str, exposed: list[dict]) -> tuple[list[tuple[int, dict]], list[str]]:
    """Exposed items with their scores, best first, and the services the claim names."""
    services = sorted({e["service"] for e in exposed if e.get("service")})
    named = named_services(claim_text, services)
    cw, nums = words(claim_text), set(_NUM.findall(claim_text or ""))
    scored = []
    for e in exposed:
        t = item_text(e)
        own = e.get("service") in named or (e["kind"] == "command_output"
                                            and any(re.search(r"(?<![\w-])" + re.escape(s) + r"(?![\w])", t.lower()) for s in named))
        score = 3 * own + len(cw & words(t)) + 2 * bool(nums & set(_NUM.findall(t)))
        scored.append((score, e))
    scored.sort(key=lambda se: (-se[0], -max(se[1].get("exposed_at_steps") or [0]), _idnum(se[1]["evidence_id"])))
    return scored, named


def _idnum(eid: str) -> int:
    return int(eid[1:]) if eid[1:].isdigit() else 10**9


def exposed_items(record: dict) -> list[dict]:
    final = record.get("final_step")
    return [e for e in record["evidence"] if e.get("exposed_at_steps")
            and (final is None or min(e["exposed_at_steps"]) < final)]


def recover(claim: dict, record: dict, k: int, min_score: int) -> dict:
    """The claim with recovered supports links and the services it names."""
    scored, named = rank(claim["text"], exposed_items(record))
    links = [{"link_type": "supports", "target": e["evidence_id"]} for s, e in scored[:k] if s >= min_score]
    out = {"claim_id": claim["claim_id"], "text": claim["text"], "type": claim["type"], "links": links, "recovered": True}
    if named:
        out["services"] = named
    return out


def pool(claim_text: str, record: dict, cap: int = 50) -> list[dict]:
    """The capped pool of the link-blind baseline: the first `cap` items in the order of steps 1 to 3."""
    scored, _ = rank(claim_text, exposed_items(record))
    return [e for _, e in scored[:cap]]
