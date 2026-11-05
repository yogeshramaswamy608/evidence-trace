"""Statistics of the evaluation plan (manuscript Section 6), standard library only."""
from __future__ import annotations

import math
import random
from collections import Counter
from typing import Callable, Sequence


def cohen_kappa(a: Sequence[str], b: Sequence[str]) -> float:
    """Unweighted Cohen's kappa of two label sequences (Cohen 1960)."""
    if len(a) != len(b) or not a:
        raise ValueError("label sequences must be non-empty and of equal length")
    n = len(a)
    po = sum(x == y for x, y in zip(a, b)) / n
    ca, cb = Counter(a), Counter(b)
    pe = sum(ca[k] * cb[k] for k in set(ca) | set(cb)) / (n * n)
    return 1.0 if pe == 1 else (po - pe) / (1 - pe)


def mcnemar_exact(b: int, c: int) -> float:
    """Two-sided exact McNemar p-value for b and c discordant pairs."""
    n = b + c
    if n == 0:
        return 1.0
    k = min(b, c)
    tail = sum(math.comb(n, i) for i in range(k + 1)) / 2 ** n
    return min(1.0, 2 * tail)


def holm(pvalues: Sequence[float]) -> list[float]:
    """Holm-adjusted p-values, in the input order."""
    m = len(pvalues)
    order = sorted(range(m), key=lambda i: pvalues[i])
    adjusted, running = [0.0] * m, 0.0
    for rank, i in enumerate(order):
        running = max(running, min(1.0, (m - rank) * pvalues[i]))
        adjusted[i] = running
    return adjusted


def prf(truth: Sequence[bool], predicted: Sequence[bool]) -> tuple[float, float, float]:
    """Precision, recall and F1 for the positive class."""
    tp = sum(t and p for t, p in zip(truth, predicted))
    fp = sum(p and not t for t, p in zip(truth, predicted))
    fn = sum(t and not p for t, p in zip(truth, predicted))
    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / (tp + fn) if tp + fn else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    return precision, recall, f1


def cluster_bootstrap(clusters: dict[str, list], stat: Callable[[list], float], reps: int = 2000,
                      seed: int = 20261105, level: float = 0.95) -> tuple[float, float, float]:
    """Point estimate and percentile interval, resampling whole clusters (runs) with replacement."""
    keys = sorted(clusters)
    point = stat([x for k in keys for x in clusters[k]])
    rng = random.Random(seed)
    draws = []
    for _ in range(reps):
        sample = [x for k in (rng.choice(keys) for _ in keys) for x in clusters[k]]
        if sample:
            draws.append(stat(sample))
    draws.sort()
    lo = draws[int((1 - level) / 2 * len(draws))]
    hi = draws[min(len(draws) - 1, int((1 + level) / 2 * len(draws)))]
    return point, lo, hi
