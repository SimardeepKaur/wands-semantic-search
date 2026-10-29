"""Item 2: plain BM25 vs BM25 with fuzziness AUTO on a few chosen WANDS queries.

Prints the top 10 for each query, with and without fuzzy, and each result's label.

Usage:
    python eval/fuzzy_experiment.py 305 "toddler couch fold out"
    (each argument is a query_id or the exact query text)
"""
import sys
from pathlib import Path

import pandas as pd
from elasticsearch import Elasticsearch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from search import ES_URL, bm25  # noqa: E402

DATA = Path("data/WANDS/dataset")


def load():
    queries = pd.read_csv(DATA / "query.csv", sep="\t")
    labels = pd.read_csv(DATA / "label.csv", sep="\t")
    return queries, labels


def find_query(queries, arg):
    if arg.isdigit():
        row = queries[queries.query_id == int(arg)]
    else:
        row = queries[queries["query"] == arg]
    if row.empty:
        raise SystemExit(f"No query matches {arg!r}")
    return int(row.query_id.iloc[0]), row["query"].iloc[0]


def show(es, labels, qid, text, fuzzy):
    lab = labels[labels.query_id == qid].set_index("product_id")["label"].to_dict()
    hits = bm25(es, text, 10, fuzzy)
    marks = [lab.get(h["product_id"], "-") for h in hits]
    strict = sum(m == "Exact" for m in marks) / 10
    lenient = sum(m in ("Exact", "Partial") for m in marks) / 10
    unlab = sum(m == "-" for m in marks) / 10
    print(f"\n### {'fuzzy AUTO' if fuzzy else 'plain'}: strict {strict:.1f}, "
          f"lenient {lenient:.1f}, unlabelled {unlab:.1f}\n")
    print("| rank | label | product | class |\n|---|---|---|---|")
    for i, (h, m) in enumerate(zip(hits, marks), start=1):
        print(f"| {i} | {m} | {h['product_name'][:60]} | {h['product_class']} |")


def main():
    queries, labels = load()
    es = Elasticsearch(ES_URL)
    for arg in sys.argv[1:]:
        qid, text = find_query(queries, arg)
        print(f"\n## Query {qid}: \"{text}\"")
        for fuzzy in (False, True):
            show(es, labels, qid, text, fuzzy)


if __name__ == "__main__":
    main()
