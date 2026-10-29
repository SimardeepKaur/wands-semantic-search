"""Compare two logged runs query by query, with a paired bootstrap.

Resamples the queries with replacement 10,000 times and takes the mean of
(run_b - run_a) each time. The 95% interval is the 2.5th to 97.5th percentile.
If it excludes 0, run_b is reliably different from run_a on these queries.

Usage:
    python eval/compare.py bm25_plain bm25_fuzzy
    python eval/compare.py bm25_plain bm25_fuzzy --worst 20   # also list the queries that dropped most
"""
import argparse
from pathlib import Path

import numpy as np
import pandas as pd

PER_QUERY_DIR = Path(__file__).resolve().parents[1] / "results/per_query"
METRICS = ["p10_strict", "p10_lenient", "unlabelled_share"]


def load(run):
    path = PER_QUERY_DIR / f"{run}.csv"
    if not path.exists():
        raise SystemExit(f"No per-query file for run {run!r} at {path}")
    return pd.read_csv(path).set_index("query_id")


def bootstrap(diff, n_resamples=10_000, seed=0):
    rng = np.random.default_rng(seed)
    idx = rng.integers(0, len(diff), size=(n_resamples, len(diff)))
    means = diff[idx].mean(axis=1)
    return np.percentile(means, [2.5, 97.5])


def compare(run_a, run_b):
    a, b = load(run_a), load(run_b)
    common = a.index.intersection(b.index)
    if len(common) != len(a) or len(common) != len(b):
        raise SystemExit(f"Runs cover different queries ({len(a)} vs {len(b)}, {len(common)} shared)")
    a, b = a.loc[common], b.loc[common]
    out = []
    for m in METRICS:
        diff = (b[m] - a[m]).to_numpy()
        lo, hi = bootstrap(diff)
        out.append({
            "metric": m,
            run_a: round(a[m].mean(), 4),
            run_b: round(b[m].mean(), 4),
            "diff": round(diff.mean(), 4),
            "ci_low": round(lo, 4),
            "ci_high": round(hi, 4),
            "excludes_0": bool(lo > 0 or hi < 0),
            "better": int((diff > 0).sum()),
            "worse": int((diff < 0).sum()),
            "same": int((diff == 0).sum()),
        })
    return pd.DataFrame(out), a, b


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("run_a")
    parser.add_argument("run_b")
    parser.add_argument("--worst", type=int, default=0)
    args = parser.parse_args()

    table, a, b = compare(args.run_a, args.run_b)
    print(f"{args.run_b} minus {args.run_a}, {len(a)} queries, paired bootstrap 10,000 resamples\n")
    print(table.to_string(index=False))
    if args.worst:
        drop = (b.p10_strict - a.p10_strict).sort_values().head(args.worst)
        worst = pd.DataFrame({"query": a.loc[drop.index, "query"],
                              args.run_a: a.loc[drop.index, "p10_strict"],
                              args.run_b: b.loc[drop.index, "p10_strict"]})
        print("\nQueries where strict P@10 dropped most:\n")
        print(worst.to_string())


if __name__ == "__main__":
    main()
