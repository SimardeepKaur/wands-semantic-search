"""Load test for the search API (items 10 and 12).

Each simulated user calls /search at a steady rate with a rotating furniture
query (hand-written list, so the load test never touches the eval files). A
request fails if the HTTP status is not 200 or if the hybrid list comes back
short: during an in-place index rebuild that is exactly what breaks.

Run (6 requests/s for 4 minutes):
    locust -f loadtest/locustfile.py --headless -u 6 -r 6 -t 4m \
        --host http://localhost:8000 --csv results/loadtest/run

With LOCUST_QUERIES=wands, queries are drawn at random (seed 0) from the
WANDS query export data/wands_queries.txt (written by eval/export_queries.py).
That mix defines the cache experiment's hit rate: 480 distinct queries.
"""
import itertools
import os
import random
from pathlib import Path

from locust import HttpUser, constant_throughput, task

QUERIES = [
    "smart coffee table", "leather sofa", "bar stool", "outdoor dining set",
    "velvet accent chair", "bathroom vanity", "queen bed frame", "desk lamp",
    "bookshelf with doors", "kitchen island cart", "patio umbrella",
    "entryway bench", "floating wall shelf", "recliner", "nightstand",
    "area rug", "shoe storage cabinet", "standing desk", "crib mattress",
    "wall mirror",
]
_cycle = itertools.cycle(QUERIES)
_rng = random.Random(0)
_wands = None
if os.environ.get("LOCUST_QUERIES") == "wands":
    path = Path(__file__).resolve().parents[1] / "data/wands_queries.txt"
    _wands = [line for line in path.read_text().splitlines() if line.strip()]


def next_query():
    return _rng.choice(_wands) if _wands else next(_cycle)


class SearchUser(HttpUser):
    # each user sends 1 request per second; -u sets the total rate
    wait_time = constant_throughput(1)

    @task
    def search(self):
        q = next_query()
        with self.client.get("/search", params={"q": q, "k": 10},
                             name="/search", catch_response=True) as r:
            if r.status_code != 200:
                r.failure(f"http {r.status_code}")
                return
            hybrid = r.json().get("hybrid", [])
            if len(hybrid) < 10:
                r.failure(f"short response: {len(hybrid)} results")
