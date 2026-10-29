"""Hand-worked examples for src/rrf.py. Run: python tests/test_rrf.py"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from rrf import blend, rrf

# RRF with k=1, rankings [1,2,3] and [3,1]:
#   id 1: 1/(1+1) + 1/(1+2) = 0.5 + 0.3333 = 0.8333
#   id 3: 1/(1+3) + 1/(1+1) = 0.25 + 0.5   = 0.75
#   id 2: 1/(1+2)                           = 0.3333
assert rrf([[1, 2, 3], [3, 1]], k=1) == [1, 3, 2]

# Perfect tie (ids 1 and 2 swap ranks): both get 1/61 + 1/62, tie breaks by id.
assert rrf([[1, 2], [2, 1]]) == [1, 2]

# One list only: RRF keeps its order.
assert rrf([[5, 4, 9]]) == [5, 4, 9]

# Blending, vector weight 0.7.
# BM25 scores 10, 6, 2 -> min-max 1.0, 0.5, 0.0. Vector 0.9, 0.5 -> 1.0, 0.0.
#   id 1: 0.3 * 1.0           = 0.30
#   id 2: 0.3 * 0.5 + 0.7 * 0 = 0.15
#   id 3: 0.3 * 0   + 0.7 * 1 = 0.70
bm = [{"product_id": 1, "score": 10}, {"product_id": 2, "score": 6},
      {"product_id": 3, "score": 2}]
vec = [{"product_id": 3, "score": 0.9}, {"product_id": 2, "score": 0.5}]
assert blend(bm, vec, 0.7) == [3, 1, 2]

# All-equal scores normalise to 1.0, not a division by zero.
same = [{"product_id": 7, "score": 4.2}, {"product_id": 8, "score": 4.2}]
assert blend(same, [], 0.5) == [7, 8]

print("test_rrf: all assertions passed")
