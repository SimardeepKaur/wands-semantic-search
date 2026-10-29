"""Create a product index that holds both the BM25 text fields and a dense vector.

Reads the saved vectors from data/vectors/ (made by src/encode.py), so indexing
never needs the encoder in memory. The vector field uses HNSW (Elasticsearch's
default for an indexed dense_vector) with cosine similarity; exact search over the
same field works through script_score, so one index serves both.

Usage:
    python src/index_vectors.py --model mpnet    # -> products_mpnet_<date>
    python src/index_vectors.py --model minilm   # -> products_minilm_<date>
"""
import argparse
import datetime as dt

import numpy as np
import pandas as pd
from elasticsearch import Elasticsearch, helpers

from index_products import MAPPING, SETTINGS, clean
from search import ES_URL

PRODUCTS_CSV = "data/WANDS/dataset/product.csv"
DIMS = {"mpnet": 768, "minilm": 384}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", choices=DIMS, required=True)
    parser.add_argument("--recreate", action="store_true")
    args = parser.parse_args()

    index = f"products_{args.model}_{dt.date.today():%Y%m%d}"
    es = Elasticsearch(ES_URL, request_timeout=120)

    vectors = np.load(f"data/vectors/products_{args.model}.npy")
    ids = np.load(f"data/vectors/product_ids_{args.model}.npy")
    assert vectors.shape == (len(ids), DIMS[args.model]), vectors.shape

    if es.indices.exists(index=index):
        if not args.recreate:
            raise SystemExit(f"{index} already exists. Use --recreate to rebuild it.")
        es.indices.delete(index=index)

    mapping = dict(MAPPING["properties"])
    mapping["vector"] = {"type": "dense_vector", "dims": DIMS[args.model],
                         "index": True, "similarity": "cosine"}
    es.indices.create(index=index, settings=SETTINGS, mappings={"properties": mapping})

    df = pd.read_csv(PRODUCTS_CSV, sep="\t")
    df = df.rename(columns={"category hierarchy": "category_hierarchy"})
    by_id = dict(zip(ids, vectors))

    def actions():
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
                    "vector": by_id[row.product_id].tolist(),
                },
            }

    ok, errors = helpers.bulk(es, actions(), chunk_size=500, raise_on_error=False)
    if errors:
        raise SystemExit(f"{len(errors)} documents failed. First: {errors[0]}")
    es.indices.refresh(index=index)
    count = es.count(index=index)["count"]
    print(f"{index}: {count} documents, expected {len(df)}")
    if count != len(df):
        raise SystemExit("Count mismatch.")


if __name__ == "__main__":
    main()
