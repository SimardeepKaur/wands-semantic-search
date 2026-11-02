"""Report the typo experiment from logged per-query files (written before any run).

For each arm against the plain run on the same queries: mean strict and lenient
P@10, unlabelled share, the paired bootstrap on strict P@10 (eval/compare.py),
and time per query on the queries where the arm can fire (at least one word the
catalogue has never seen, the trigger both arms share).

Usage:
    python eval/typo_report.py --plain typo50_plain --arms typo50_spell typo50_fuzzyword \
        --clean typo50_clean_plain
    python eval/typo_report.py --plain all480_plain --arms all480_spell all480_fuzzyword
"""
import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "eval"))

from compare import compare, load  # noqa: E402
from patch import build_resources, unseen, words  # noqa: E402


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--plain", required=True)
    parser.add_argument("--arms", nargs="+", required=True)
    parser.add_argument("--clean", help="the same queries without typos, for scale")
    args = parser.parse_args()

    res = build_resources()
    plain = load(args.plain)
    fires = plain["query"].map(lambda q: any(unseen(res, w) for w in words(q)))
    print(f"queries: {len(plain)}; with at least one word the catalogue has never seen: "
          f"{int(fires.sum())}\n")

    rows = ([args.clean] if args.clean else []) + [args.plain] + args.arms
    print(f"{'run':<24}{'strict':>8}{'lenient':>9}{'unlab':>8}"
          f"{'ms/query (fires)':>18}{'ms/query (all)':>16}")
    for run in rows:
        d = load(run)
        on = d.loc[fires[fires].index] if run != args.clean else d
        print(f"{run:<24}{d.p10_strict.mean():>8.4f}{d.p10_lenient.mean():>9.4f}"
              f"{d.unlabelled_share.mean():>8.4f}"
              f"{on.seconds.median() * 1000:>18.1f}{d.seconds.median() * 1000:>16.1f}")

    for arm in args.arms:
        table, a, b = compare(args.plain, arm)
        s = table[table.metric == "p10_strict"].iloc[0]
        extra = (b.seconds - a.seconds).loc[fires[fires].index] * 1000
        print(f"\n{arm} minus {args.plain}, strict P@10: diff {s['diff']:+.4f}, "
              f"95% interval {s.ci_low:+.4f} to {s.ci_high:+.4f}, "
              f"interval excludes 0: {s.excludes_0}; better {s.better}, worse {s.worse}, "
              f"same {s.same}")
        print(f"  extra time on queries where it fires: median {extra.median():+.1f} ms "
              f"(n={len(extra)})")


if __name__ == "__main__":
    main()
