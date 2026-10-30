"""Drive /search once with every query in the WANDS export (item 16).

Produces a full set of request-log lines for src/log_summary.py and counts
the zero-result rate separately for the plain BM25 list and the hybrid list
in each response: the same query set, the same moment, both systems.

Reads data/wands_queries.txt (written by eval/export_queries.py); this file
never touches the eval csvs.

Usage, with the API running:
    python loadtest/drive_queries.py
"""
import json
from pathlib import Path
from urllib.parse import quote
from urllib.request import urlopen

ROOT = Path(__file__).resolve().parents[1]
QUERIES = ROOT / "data/wands_queries.txt"
BASE = "http://localhost:8000"


def main():
    queries = [q for q in QUERIES.read_text().splitlines() if q.strip()]
    bm25_zero = hybrid_zero = 0
    for q in queries:
        with urlopen(f"{BASE}/search?q={quote(q)}&k=10", timeout=30) as resp:
            d = json.load(resp)
        bm25_zero += len(d["bm25"]) == 0
        hybrid_zero += len(d["hybrid"]) == 0
    n = len(queries)
    print(f"{n} queries")
    print(f"bm25 zero-result rate   {bm25_zero / n:.4f} ({bm25_zero} queries)")
    print(f"hybrid zero-result rate {hybrid_zero / n:.4f} ({hybrid_zero} queries)")


if __name__ == "__main__":
    main()
