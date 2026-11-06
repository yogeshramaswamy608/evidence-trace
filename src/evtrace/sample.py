"""Stratified claim sample of manuscript Section 5.7, standard library only.

Strata are model x condition x task type. Each stratum gets a share of the sample
proportional to its size (largest remainder), at most five claims come from any
one run, and the sample is split at random into a development and a test set.
"""
from __future__ import annotations

import random
from collections import Counter, defaultdict

STRATUM = ("model", "condition", "task_type")


def allocate(sizes: dict, n: int) -> dict:
    """Proportional allocation of n over strata by largest remainder, capped by stratum size."""
    total = sum(sizes.values())
    if total <= n:
        return dict(sizes)
    raw = {k: n * v / total for k, v in sizes.items()}
    out = {k: int(r) for k, r in raw.items()}
    for k in sorted(raw, key=lambda k: (out[k] - raw[k], str(k)))[: n - sum(out.values())]:
        out[k] += 1
    return out


def draw(claims: list[dict], n: int = 300, n_dev: int = 100, per_run: int = 5,
         seed: int = 20261105) -> tuple[list[dict], list[dict]]:
    """Return (development, test) lists of claims; each claim needs run_id, claim_id and the stratum fields."""
    rng = random.Random(seed)
    by = defaultdict(list)
    for c in sorted(claims, key=lambda c: (c["run_id"], c["claim_id"])):
        by[tuple(c[f] for f in STRATUM)].append(c)
    quota = allocate({k: len(v) for k, v in by.items()}, n)
    used, chosen = Counter(), []
    for k in sorted(by):
        pool = by[k][:]
        rng.shuffle(pool)
        got = 0
        for c in pool:
            if got == quota[k]:
                break
            if used[c["run_id"]] < per_run:
                used[c["run_id"]] += 1
                chosen.append(c)
                got += 1
    rng.shuffle(chosen)
    return chosen[:n_dev], chosen[n_dev:]


def queue(sample: list[dict], gold: list[dict], seed: int = 20261105) -> list[dict]:
    """Labeling queue: sampled and gold claims mixed in one random order, with no marker of which is which."""
    q = [{k: v for k, v in c.items() if k not in ("gold_label", "is_gold")} for c in sample + gold]
    random.Random(f"{seed}:queue").shuffle(q)
    return q
