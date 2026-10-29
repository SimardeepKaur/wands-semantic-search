"""Create a BM25 index of all WANDS products and point the products_live alias at it.

Usage:
    python src/index_products.py             # index name products_bm25_<today>
    python src/index_products.py --recreate  # delete and rebuild today's index if it exists
"""
import argparse
import datetime as dt
import math

import pandas as pd
from elasticsearch import Elasticsearch, helpers

ES_URL = "http://localhost:9200"
PRODUCTS_CSV = "data/WANDS/dataset/product.csv"
ALIAS = "products_live"

# The mapping is the index schema. "text" fields are split into words and scored with BM25.
# "keyword" fields are stored whole, for exact filters and counts.
# The "english" analyzer lowercases, drops stop words and stems ("hooks" -> "hook").
MAPPING = {
    "properties": {
        "product_id": {"type": "keyword"},
        "product_name": {"type": "text", "analyzer": "english"},
        "product_class": {
            "type": "text",
            "analyzer": "english",
            "fields": {"raw": {"type": "keyword"}},
        },
        "category_hierarchy": {"type": "text", "analyzer": "english"},
        "product_description": {"type": "text", "analyzer": "english"},
        "product_features": {"type": "text", "analyzer": "english"},
        "rating_count": {"type": "float"},
        "average_rating": {"type": "float"},
        "review_count": {"type": "float"},
    }
}

# One shard (a shard is one slice of an index, stored and searched on its own) is enough for
# 43k products. Zero replicas (copies of a shard on another node), because we have one node.
SETTINGS = {"number_of_shards": 1, "number_of_replicas": 0}


def clean(value):
    """Pandas uses NaN for empty cells. Elasticsearch wants null instead."""
    if isinstance(value, float) and math.isnan(value):
        return None
    return value


def actions(df, index):
    """One bulk action per product. The product id becomes the document id."""
    for row in df.itertuples(index=False):
        yield {
            "_index": index,
            "_id": str(row.product_id),
            "_source": {
                "product_id": str(row.product_id),
                "product_name": clean(row.product_name),
                "product_class": clean(row.product_class),
                "category_hierarchy": clean(row.category_hierarchy),
                "product_description": clean(row.product_description),
                "product_features": clean(row.product_features),
                "rating_count": clean(row.rating_count),
                "average_rating": clean(row.average_rating),
                "review_count": clean(row.review_count),
            },
        }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--recreate", action="store_true")
    args = parser.parse_args()

    index = f"products_bm25_{dt.date.today():%Y%m%d}"
    es = Elasticsearch(ES_URL)

    if es.indices.exists(index=index):
        if not args.recreate:
            raise SystemExit(f"{index} already exists. Use --recreate to rebuild it.")
        es.indices.delete(index=index)

    df = pd.read_csv(PRODUCTS_CSV, sep="\t")
    df = df.rename(columns={"category hierarchy": "category_hierarchy"})

    es.indices.create(index=index, settings=SETTINGS, mappings=MAPPING)
    ok, errors = helpers.bulk(es, actions(df, index), chunk_size=2000, raise_on_error=False)
    if errors:
        raise SystemExit(f"{len(errors)} documents failed. First error: {errors[0]}")

    # New documents become searchable after a refresh. Force one so the count is accurate.
    es.indices.refresh(index=index)
    count = es.count(index=index)["count"]
    print(f"{index}: loaded {count} documents, expected {len(df)}")
    if count != len(df):
        raise SystemExit("Count mismatch. Not moving the alias.")

    # Point the alias at the new index. Day 5 turns this into a proper swap from an old index.
    es.indices.update_aliases(actions=[{"add": {"index": index, "alias": ALIAS}}])
    print(f"{ALIAS} -> {index}")


if __name__ == "__main__":
    main()
