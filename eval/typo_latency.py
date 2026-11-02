"""Time the typo arms fairly: full hybrid request, arms interleaved query by query.

The eval loop's own timings depend on run order (whichever run goes first pays
warm-up), so they cannot compare arms. Here every arm sees every query once in
a warm-up pass, then REPS rounds alternate the arms on each query, so machine
noise lands on all arms alike. Reported: per-query median, then the median over
queries, and the median of the paired extra time against plain.

Query groups: the typo set (every query has a word the catalogue never saw)
and the 480 queries where an arm can fire (same trigger).

Usage:
    python eval/typo_latency.py           # print only
    python eval/typo_latency.py --log     # also append rows to results/perf.csv
"""
import argparse
import csv
import datetime as dt
import statistics
import sys
import time
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "eval"))

from patch import build_resources, unseen, words  # noqa: E402
from run_eval import load_queries, method_hybrid  # noqa: E402

REPS = 5
ARMS = {"plain": {}, "spell": {"spell": True}, "fuzzyword": {"fuzzy_unseen": True}}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--log", action="store_true")
    args = parser.parse_args()

    res = build_resources()
    all480 = load_queries()
    fired480 = [q for q in all480["query"] if any(unseen(res, w) for w in words(q))]
    groups = {"typo50": list(pd.read_csv(ROOT / "eval/typo50.csv")["query"]),
              "all480_fires": fired480}
    runs = {name: method_hybrid("rrf", **kw) for name, kw in ARMS.items()}

    for qs in groups.values():
        for q in qs:
            for run in runs.values():
                run(0, q)

    rows = []
    for group, qs in groups.items():
        per = {name: [] for name in ARMS}
        for q in qs:
            times = {name: [] for name in ARMS}
            for _ in range(REPS):
                for name, run in runs.items():
                    t = time.perf_counter()
                    run(0, q)
                    times[name].append((time.perf_counter() - t) * 1000)
            for name in ARMS:
                per[name].append(statistics.median(times[name]))
        print(f"{group} ({len(qs)} queries, {REPS} interleaved rounds after warm-up)")
        for name in ARMS:
            med = statistics.median(per[name])
            extra = statistics.median(a - p for a, p in zip(per[name], per["plain"]))
            print(f"  {name:<10} median {med:7.1f} ms   paired extra vs plain {extra:+6.1f} ms")
            rows.append((group, name, med, extra, len(qs)))

    if args.log:
        with (ROOT / "results/perf.csv").open("a", newline="") as f:
            w = csv.writer(f)
            for group, name, med, extra, n in rows:
                note = (f"full hybrid request, {n} queries where the arm can fire, {REPS} "
                        "interleaved rounds after warm-up, local M2 laptop under swap pressure")
                w.writerow([dt.date.today().isoformat(), f"typo_{group}", f"{name}_ms",
                            round(med, 1), note])
                if name != "plain":
                    w.writerow([dt.date.today().isoformat(), f"typo_{group}",
                                f"{name}_extra_ms", round(extra, 1),
                                "median paired difference against plain on the same queries"])
        print("Logged to results/perf.csv")


if __name__ == "__main__":
    main()
