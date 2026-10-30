"""Rebuild the live product index with zero downtime (item 10).

Builds a brand-new dated index from the stored vectors, checks the document
count, then moves the products_live alias from the old index to the new one in
ONE atomic actions call. Searches never see a gap: every request hits either
the complete old index or the complete new one. The old index is kept (delete
it later with --drop-old once the new one is trusted).

The measured alternative, rebuilding in place under one name, is
loadtest/rebuild_inplace.py; docs/experiments.md item 10 holds the counts.

Usage:
    python src/rebuild_index.py --model minilm
    python src/rebuild_index.py --model minilm --suffix v2 --drop-old
"""
import argparse
import datetime as dt

from elasticsearch import Elasticsearch

from index_vectors import DIMS, build_index
from search import ALIAS, ES_URL


def rebuild(es, model, suffix=None, drop_old=False):
    date = f"{dt.date.today():%Y%m%d}"
    index = f"products_{model}_{date}" + (f"_{suffix}" if suffix else "")
    old = list(es.indices.get_alias(name=ALIAS).keys()) \
        if es.indices.exists_alias(name=ALIAS) else []
    if index in old:
        raise SystemExit(f"{index} is live right now. Pass --suffix to rebuild today.")

    build_index(es, model, index=index, recreate=True)  # count-checked inside

    actions = [{"remove": {"index": o, "alias": ALIAS}} for o in old]
    actions.append({"add": {"index": index, "alias": ALIAS}})
    es.indices.update_aliases(actions=actions)  # one atomic step
    print(f"{ALIAS}: {old or ['(nothing)']} -> {index}")

    if drop_old:
        for o in old:
            es.indices.delete(index=o)
            print(f"deleted {o}")
    return index


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", choices=DIMS, default="minilm")
    parser.add_argument("--suffix", help="extra index-name suffix for same-day rebuilds")
    parser.add_argument("--drop-old", action="store_true")
    args = parser.parse_args()
    es = Elasticsearch(ES_URL, request_timeout=120)
    rebuild(es, args.model, suffix=args.suffix, drop_old=args.drop_old)


if __name__ == "__main__":
    main()
