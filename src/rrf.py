"""Combine two rankings: Reciprocal Rank Fusion (the stack's choice) and
weighted score blending (the alternative to measure against).

RRF ignores scores and uses only ranks: a product at rank r in one list adds
1 / (k + r) to its total. k = 60 is the constant from the original RRF paper;
a larger k flattens the difference between ranks.

Blending min-max normalises each list's scores to 0..1, then mixes them:
combined = (1 - w) * bm25 + w * vector. A product missing from a list
contributes 0 from that list. Ties break by product id, so results are
deterministic.
"""


def rrf(rankings, k=60):
    """Fuse rankings (lists of product ids, best first) into one list, best first."""
    scores = {}
    for ranking in rankings:
        for rank, pid in enumerate(ranking, start=1):
            scores[pid] = scores.get(pid, 0.0) + 1.0 / (k + rank)
    return sorted(scores, key=lambda pid: (-scores[pid], pid))


def _minmax(hits):
    """{product_id: score normalised to 0..1} for a hit list, best first."""
    if not hits:
        return {}
    raw = [h["score"] for h in hits]
    lo, hi = min(raw), max(raw)
    if hi == lo:
        return {h["product_id"]: 1.0 for h in hits}
    return {h["product_id"]: (h["score"] - lo) / (hi - lo) for h in hits}


def blend(bm25_hits, vector_hits, w):
    """Mix two hit lists (dicts with product_id and score) with vector weight w."""
    bm, vec = _minmax(bm25_hits), _minmax(vector_hits)
    combined = {pid: (1 - w) * bm.get(pid, 0.0) + w * vec.get(pid, 0.0)
                for pid in set(bm) | set(vec)}
    return sorted(combined, key=lambda pid: (-combined[pid], pid))
