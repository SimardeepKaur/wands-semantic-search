"""Smoke and consistency tests for the service (item 9's "done when").

Needs Elasticsearch up with products_live pointing at the MiniLM index.
Run: python tests/test_api.py

The consistency check calls /search for 20 WANDS queries and compares the
hybrid product ids with the logged eval run of the same method
(results/per_query/hybrid_rrf60.csv), so the service provably serves the
system the numbers were measured on.
"""
import sys
from pathlib import Path

import pandas as pd
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from api import app  # noqa: E402

PER_QUERY = ROOT / "results/per_query/hybrid_rrf60_det.csv"


def main():
    with TestClient(app) as client:
        # /health
        h = client.get("/health").json()
        assert h["status"] == "ok" and h["docs"] == 42994, h
        print(f"health ok: alias -> {h['index']}, {h['docs']} docs, "
              f"{h['labels_loaded']} demo label queries")

        # / serves the demo page
        r = client.get("/")
        assert r.status_code == 200 and "<title>WANDS Search</title>" in r.text
        print("demo page ok")

        # /search basics on a WANDS query
        d = client.get("/search", params={"q": "smart coffee table"}).json()
        assert len(d["hybrid"]) == 10 and len(d["bm25"]) == 10, d["took_ms"]
        assert d["labels_known"], "WANDS query should have labels in the demo export"
        print(f"search ok: {d['took_ms']} ms, labels shown")

        # class filter returns only that class
        d = client.get("/search", params={"q": "chair", "product_class": "Sofas"}).json()
        classes = {h["product_class"] for h in d["hybrid"]} | \
                  {h["product_class"] for h in d["bm25"]}
        assert classes <= {"Sofas"}, classes
        print("class filter ok")

        # consistency with the logged eval run, 20 queries
        rows = pd.read_csv(PER_QUERY).head(20)
        mismatches = []
        for _, row in rows.iterrows():
            d = client.get("/search", params={"q": row["query"], "k": 10}).json()
            got = [h["product_id"] for h in d["hybrid"]]
            want = [int(x) for x in str(row["top10"]).split()]
            if got != want:
                mismatches.append((row["query"], want, got))
        assert not mismatches, f"{len(mismatches)} queries differ from the eval run: " \
                               f"{mismatches[0][0]!r}"
        print("consistency ok: 20 queries match run hybrid_rrf60_det exactly")


if __name__ == "__main__":
    main()
    print("test_api: all checks passed")
