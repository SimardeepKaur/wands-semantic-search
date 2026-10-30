"""The CI eval gate (item 14).

Runs the serving method (hybrid RRF) over all 480 WANDS queries against the
index CI just built, and fails if strict P@10 lands below the best logged run
of that method in results/runs.csv, minus a small documented tolerance.

The tolerance exists because two things legitimately wobble between machines
and index builds without any code being worse (both in PROGRESS.md
2026-10-30): HNSW graph building is random, so a fresh index shifts the
approximate top 100 slightly, and CPU float arithmetic differs in the last
digits across hardware. 0.005 of strict P@10 is beyond either effect in every
rebuild measured in this repo; a real regression (dropping the vector leg,
breaking the encoder, losing the rewrite) costs 0.02 or more.

Usage (Elasticsearch up, index built, run from the repo root):
    python eval/ci_gate.py
"""
import sys
import time
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "eval"))

from run_eval import N_QUERIES, load_labels, load_queries, method_hybrid, score

METHOD = "hybrid_rrf60"
TOLERANCE = 0.005


def main():
    runs = pd.read_csv(ROOT / "results/runs.csv")
    best = runs[runs.method == METHOD].p10_strict.max()
    assert pd.notna(best), f"no logged {METHOD} run in runs.csv"
    floor = round(best - TOLERANCE, 4)

    queries = load_queries()
    labels = load_labels()
    run = method_hybrid("rrf")
    start = time.time()
    results = [(int(qid), text, run(int(qid), text), 0.0)
               for qid, text in zip(queries.query_id, queries["query"])]
    per_query = score(results, labels)
    assert len(per_query) == N_QUERIES, len(per_query)
    strict = per_query.p10_strict.mean()

    print(f"strict P@10 here: {strict:.4f}  "
          f"(best logged {METHOD}: {best:.4f}, gate floor: {floor:.4f}, "
          f"{(time.time() - start) / 60:.1f} min)")
    if strict < floor:
        print("GATE FAILED: the serving method scores below the logged best.")
        raise SystemExit(1)
    print("gate passed")


if __name__ == "__main__":
    main()
