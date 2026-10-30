"""Export the 480 WANDS query strings for the load test.

The load test may not read the eval files (the leakage check covers loadtest/),
but the cache experiment's traffic mix is defined as random draws from the
WANDS queries. This eval-side script writes the plain query strings to
data/wands_queries.txt; the Locust file reads that export.

Usage:
    python eval/export_queries.py
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "eval"))

from run_eval import load_queries

OUT = ROOT / "data/wands_queries.txt"
queries = load_queries()["query"].tolist()
OUT.write_text("\n".join(queries) + "\n")
print(f"wrote {OUT.relative_to(ROOT)}: {len(queries)} queries")
