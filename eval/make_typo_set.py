"""Build the typo eval set: 50 WANDS queries, one typo each, labels kept by query_id.

Rules (fixed before any typo run, 2026-10-31):
- Queries are shuffled with a fixed seed and taken in that order.
- One typo per query, in one content word: 4+ letters, letters only, not a stop word.
- The first letter is never touched.
- Edit kinds rotate so the set is an even mix: dropped letter, swapped neighbours,
  doubled letter, wrong letter (a QWERTY neighbour of the intended key).
- A typo that lands on any word in the catalogue vocabulary (product names,
  descriptions, features, classes, category paths, the same vocabulary the
  serving code checks) is thrown out and another position or word is tried.
  That is a different problem: the catalogue has the word, so nothing can tell
  it is a typo. The throw-out count is printed, because it is the share of
  typos this kind of fix can never see.

The intent of the query is unchanged, so its WANDS labels still apply.

Usage:
    python eval/make_typo_set.py            # writes eval/typo50.csv
"""
import csv
import random
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "eval"))

from patch import STOP, build_resources  # noqa: E402
from run_eval import load_queries  # noqa: E402

SEED = 20261031
N = 50
OUT = ROOT / "eval/typo50.csv"
KINDS = ["drop", "swap", "double", "wrong"]

QWERTY = ["qwertyuiop", "asdfghjkl", "zxcvbnm"]


def neighbours(ch):
    """Keys left, right, above and below on a QWERTY keyboard."""
    for r, row in enumerate(QWERTY):
        c = row.find(ch)
        if c < 0:
            continue
        out = set()
        for rr in (r - 1, r, r + 1):
            if 0 <= rr < len(QWERTY):
                for cc in (c - 1, c, c + 1):
                    if 0 <= cc < len(QWERTY[rr]) and (rr, cc) != (r, c):
                        out.add(QWERTY[rr][cc])
        return sorted(out)
    return []


def candidates(word, kind, rng):
    """Every typo of one kind for this word, in random order. Position 0 is never edited."""
    out = []
    for i in range(1, len(word)):
        if kind == "drop":
            out.append(word[:i] + word[i + 1:])
        elif kind == "swap" and i + 1 < len(word) and word[i] != word[i + 1]:
            out.append(word[:i] + word[i + 1] + word[i] + word[i + 2:])
        elif kind == "double":
            out.append(word[:i] + word[i] + word[i:])
        elif kind == "wrong":
            out.extend(word[:i] + n + word[i + 1:] for n in neighbours(word[i]))
    out = [t for t in dict.fromkeys(out) if t != word]
    rng.shuffle(out)
    return out


def main():
    vocab = set(build_resources()["vocab"])
    queries = load_queries()
    rng = random.Random(SEED)
    order = list(range(len(queries)))
    rng.shuffle(order)

    rows, rejected, tried = [], 0, 0
    for idx in order:
        if len(rows) == N:
            break
        qid, text = int(queries.query_id.iloc[idx]), queries["query"].iloc[idx]
        tokens = text.split()
        content = [i for i, t in enumerate(tokens)
                   if t.isalpha() and len(t) >= 4 and t.lower() not in STOP]
        if not content:
            continue
        kind = KINDS[len(rows) % len(KINDS)]
        rng.shuffle(content)
        made = None
        for ti in content:
            word = tokens[ti].lower()
            for typo in candidates(word, kind, rng):
                tried += 1
                if typo in vocab:
                    rejected += 1
                    continue
                made = (ti, word, typo)
                break
            if made:
                break
        if not made:
            continue
        ti, word, typo = made
        new_tokens = tokens[:]
        new_tokens[ti] = typo
        rows.append({"query_id": qid, "original": text, "query": " ".join(new_tokens),
                     "word": word, "typo": typo, "edit": kind})

    with OUT.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["query_id", "original", "query", "word", "typo", "edit"])
        writer.writeheader()
        writer.writerows(rows)
    kinds = {k: sum(r["edit"] == k for r in rows) for k in KINDS}
    print(f"wrote {len(rows)} queries to {OUT.relative_to(ROOT)}; edit mix {kinds}")
    print(f"typos tried {tried}, thrown out as real catalogue words {rejected} "
          f"({rejected / tried:.1%})")


if __name__ == "__main__":
    main()
