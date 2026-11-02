"""Smoke and consistency tests for the service (item 9's "done when").

Needs Elasticsearch up with products_live pointing at the MiniLM index.
Run: python tests/test_api.py

The consistency check calls /search for 20 WANDS queries and compares the
hybrid product ids with the eval code path (run_eval.method_hybrid) executed
in-process against the current index, so the service provably serves the same
method the numbers were measured with. It does not compare against a stored
per-query file: each index rebuild grows a fresh HNSW graph, graph building
is random, and the approximate top 100 shifts slightly per build (PROGRESS.md
2026-10-30), so exact ids are only stable within one index build.
"""
import sys
from pathlib import Path

import pandas as pd
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from api import app  # noqa: E402

sys.path.insert(0, str(ROOT / "eval"))

PER_QUERY = ROOT / "results/per_query/hybrid_rrf60_det.csv"  # supplies the 20 queries


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

        # consistency with the eval code path on the current index, 20 queries
        from run_eval import method_hybrid
        eval_run = method_hybrid("rrf", spell=True)
        rows = pd.read_csv(PER_QUERY).head(20)
        mismatches = []
        for _, row in rows.iterrows():
            d = client.get("/search", params={"q": row["query"], "k": 10}).json()
            got = [h["product_id"] for h in d["hybrid"]]
            want = eval_run(None, row["query"])[:10]
            if got != want:
                mismatches.append((row["query"], want, got))
        # One wobble is allowed: when two products have identical vectors
        # (duplicate listings), which of them makes the knn top-100 cut is
        # decided inside the graph search, before any sort can break the tie.
        assert len(mismatches) <= 1, \
            f"{len(mismatches)} queries differ from the eval code: {mismatches[0]!r}"
        print(f"consistency ok: {20 - len(mismatches)}/20 queries match the eval "
              f"method exactly")


if __name__ == "__main__":
    main()
    print("test_api: all checks passed")
