"""Build the 2-edit real-misspelling eval set: 50 WANDS queries, one misspelling each.

Misspellings people actually made, pooled from five public lists, each entry tagged
with the list(s) it came from. Download into data/misspellings/ first:
    curl -o data/misspellings/missp.dat          https://www.dcs.bbk.ac.uk/~ROGER/missp.dat
    curl -o data/misspellings/aspell.dat         https://www.dcs.bbk.ac.uk/~ROGER/aspell.dat
    curl -o data/misspellings/holbrook-missp.dat https://www.dcs.bbk.ac.uk/~ROGER/holbrook-missp.dat
    curl -o data/misspellings/birkbeck-site-wikipedia.dat https://www.dcs.bbk.ac.uk/~ROGER/wikipedia.dat
    curl -o data/misspellings/wikipedia-for-machines.txt \
      "https://en.wikipedia.org/w/index.php?title=Wikipedia:Lists_of_common_misspellings/For_machines&action=raw"

Rules (fixed before any run, 2026-11-02):
- Exactly 2 edits from the intended word (Damerau-Levenshtein). This is the case
  closest-first spell correction gets wrong ("sopha" to "sophia"); 1-edit
  misspellings were covered by typo50 and soundalike50.
- The intended word must appear in at least one product name, since shoppers
  misspell product words. This filters which word is misspelled, not how.
- Content words only: 4+ letters, letters only, not a stop word.
- Usable misspelling: letters only, and not any catalogue word (same throw-out as
  typo50 and soundalike50).
- Queries shuffled with a fixed seed; among qualifying words, then among their
  usable misspellings, one is picked at random.
- Wikipedia entries with several possible corrections are skipped.

Usage:
    python eval/make_misspell2_set.py      # writes eval/misspell2e50.csv
"""
import csv
import random
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "eval"))

from make_soundalike_set import distance  # noqa: E402
from patch import STOP, build_resources  # noqa: E402
from run_eval import load_queries  # noqa: E402

SEED = 20261102
N = 50
DIR = ROOT / "data/misspellings"
OUT = ROOT / "eval/misspell2e50.csv"
DOLLAR_LISTS = {"birkbeck": "missp.dat", "aspell": "aspell.dat",
                "holbrook": "holbrook-missp.dat", "wikipedia_bbk": "birkbeck-site-wikipedia.dat"}
WIKI = "wikipedia-for-machines.txt"


def load_dollar(path):
    """'$word' then one misspelling per line (Holbrook adds a count after it)."""
    out, cur = defaultdict(set), None
    for line in path.read_text(encoding="latin-1").splitlines():
        line = line.strip()
        if not line:
            continue
        if line.startswith("$"):
            cur = line[1:].lower()
        else:
            out[cur].add(line.split()[0].lower())
    return out


def load_wiki(path):
    """'misspelling->word' lines."""
    out = defaultdict(set)
    for line in path.read_text(encoding="utf-8").splitlines():
        if "->" not in line:
            continue
        bad, good = line.strip().split("->", 1)
        if "," not in good:
            out[good.strip().lower()].add(bad.strip().lower())
    return out


def load_pool():
    """Intended word -> {misspelling: sorted list of source names}."""
    lists = {name: load_dollar(DIR / f) for name, f in DOLLAR_LISTS.items()}
    lists["wikipedia"] = load_wiki(DIR / WIKI)
    pool = defaultdict(lambda: defaultdict(set))
    for name, m in lists.items():
        for word, typos in m.items():
            for t in typos:
                pool[word][t].add(name)
    return pool


def main():
    res = build_resources()
    vocab, name_words = set(res["vocab"]), set(res["df"])
    pool = load_pool()
    queries = load_queries()
    rng = random.Random(SEED)
    order = list(range(len(queries)))
    rng.shuffle(order)

    def usable(word):
        return sorted(t for t in pool.get(word, ())
                      if t.isalpha() and t not in vocab and distance(word, t) == 2)

    rows = []
    for idx in order:
        if len(rows) == N:
            break
        qid, text = int(queries.query_id.iloc[idx]), queries["query"].iloc[idx]
        tokens = text.split()
        content = [i for i, t in enumerate(tokens)
                   if t.isalpha() and len(t) >= 4 and t.lower() not in STOP
                   and t.lower() in name_words and usable(t.lower())]
        if not content:
            continue
        ti = rng.choice(content)
        word = tokens[ti].lower()
        typo = rng.choice(usable(word))
        new_tokens = tokens[:]
        new_tokens[ti] = typo
        rows.append({"query_id": qid, "original": text, "query": " ".join(new_tokens),
                     "word": word, "typo": typo, "edits": distance(word, typo),
                     "sources": "|".join(sorted(pool[word][typo]))})

    with OUT.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["query_id", "original", "query", "word",
                                               "typo", "edits", "sources"])
        writer.writeheader()
        writer.writerows(rows)
    print(f"wrote {len(rows)} queries to {OUT.relative_to(ROOT)}")
    print("edit mix:", dict(Counter(r["edits"] for r in rows)))
    print("entries per source (an entry can be in several):",
          dict(Counter(s for r in rows for s in r["sources"].split("|")).most_common()))
    print("only in one list:",
          dict(Counter(r["sources"] for r in rows if "|" not in r["sources"]).most_common()))


if __name__ == "__main__":
    main()
