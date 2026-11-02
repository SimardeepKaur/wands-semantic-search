"""Build the real-misspelling eval set: 50 WANDS queries, one human misspelling each.

The misspellings come from the Birkbeck spelling error corpus (Roger Mitton), real
errors people made in writing, not from any rule we wrote. Download it first:
    mkdir -p data/misspellings
    curl -o data/misspellings/missp.dat https://www.dcs.bbk.ac.uk/~ROGER/missp.dat
Format: a line "$word" for the correct word, then one misspelling per line.

Rules (fixed before any run, 2026-11-02):
- Chosen over Wikipedia's machine-readable common misspellings list because it
  covers far more WANDS queries (348 vs 54 of 480).
- Queries are shuffled with a fixed seed and taken in that order.
- One misspelling per query, in one content word: 4+ letters, letters only, not a
  stop word, and the corpus has at least one usable misspelling for it.
- Usable: letters only, not the word itself, and not any catalogue word (the same
  throw-out as typo50; a catalogue word cannot be seen as a typo).
- Among the content words that qualify, and then among their usable misspellings,
  one is picked at random. Edit distance is not filtered; it is printed.

The intent of the query is unchanged, so its WANDS labels still apply.

Usage:
    python eval/make_soundalike_set.py      # writes eval/soundalike50.csv
"""
import csv
import random
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "eval"))

from patch import STOP, build_resources  # noqa: E402
from run_eval import load_queries  # noqa: E402

SEED = 20261102
N = 50
CORPUS = ROOT / "data/misspellings/missp.dat"
OUT = ROOT / "eval/soundalike50.csv"


def load_corpus():
    """Correct word -> set of misspellings, all lowercased."""
    out, cur = defaultdict(set), None
    for line in CORPUS.read_text(encoding="latin-1").splitlines():
        line = line.strip()
        if not line:
            continue
        if line.startswith("$"):
            cur = line[1:].lower()
        else:
            out[cur].add(line.split()[0].lower())
    return out


def distance(a, b):
    """Damerau-Levenshtein (adjacent swaps count as one edit)."""
    d = [[0] * (len(b) + 1) for _ in range(len(a) + 1)]
    for i in range(len(a) + 1):
        d[i][0] = i
    for j in range(len(b) + 1):
        d[0][j] = j
    for i in range(1, len(a) + 1):
        for j in range(1, len(b) + 1):
            cost = a[i - 1] != b[j - 1]
            d[i][j] = min(d[i - 1][j] + 1, d[i][j - 1] + 1, d[i - 1][j - 1] + cost)
            if i > 1 and j > 1 and a[i - 1] == b[j - 2] and a[i - 2] == b[j - 1]:
                d[i][j] = min(d[i][j], d[i - 2][j - 2] + 1)
    return d[len(a)][len(b)]


def main():
    vocab = set(build_resources()["vocab"])
    corpus = load_corpus()
    queries = load_queries()
    rng = random.Random(SEED)
    order = list(range(len(queries)))
    rng.shuffle(order)

    def usable(word):
        return sorted(m for m in corpus.get(word, ())
                      if m.isalpha() and m != word and m not in vocab)

    rows = []
    for idx in order:
        if len(rows) == N:
            break
        qid, text = int(queries.query_id.iloc[idx]), queries["query"].iloc[idx]
        tokens = text.split()
        content = [i for i, t in enumerate(tokens)
                   if t.isalpha() and len(t) >= 4 and t.lower() not in STOP
                   and usable(t.lower())]
        if not content:
            continue
        ti = rng.choice(content)
        word = tokens[ti].lower()
        typo = rng.choice(usable(word))
        new_tokens = tokens[:]
        new_tokens[ti] = typo
        rows.append({"query_id": qid, "original": text, "query": " ".join(new_tokens),
                     "word": word, "typo": typo, "edits": distance(word, typo)})

    with OUT.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["query_id", "original", "query", "word",
                                               "typo", "edits"])
        writer.writeheader()
        writer.writerows(rows)
    mix = dict(sorted(Counter(min(r["edits"], 3) for r in rows).items()))
    print(f"wrote {len(rows)} queries to {OUT.relative_to(ROOT)}; "
          f"edit distance mix (3 = 3 or more) {mix}")


if __name__ == "__main__":
    main()
