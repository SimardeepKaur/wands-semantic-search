"""Search the products_live alias. Day 1: plain BM25 only.

Usage:
    python src/search.py "moen matte black hooks"
    python src/search.py "moen mate blak hooks" --fuzzy
"""
import argparse

from elasticsearch import Elasticsearch

ES_URL = "http://localhost:9200"
ALIAS = "products_live"
FIELDS = ["product_name", "product_description", "product_features"]


def bm25(es, query, k=10, fuzzy=False):
    """Top k products for a query, as a list of dicts, best first.

    multi_match runs the query against each field and keeps the best field's BM25 score
    (type "best_fields", the default). No field boosts: this is the plain baseline.
    """
    match = {"query": query, "fields": FIELDS}
    if fuzzy:
        # AUTO: words of 1-2 chars must match exactly, 3-5 chars allow 1 edit, 6+ allow 2.
        match["fuzziness"] = "AUTO"
    resp = es.search(
        index=ALIAS,
        size=k,
        query={"multi_match": match},
        source=["product_id", "product_name", "product_class"],
    )
    return [
        {
            "product_id": int(hit["_id"]),
            "score": hit["_score"],
            "product_name": hit["_source"]["product_name"],
            "product_class": hit["_source"].get("product_class"),
        }
        for hit in resp["hits"]["hits"]
    ]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("query")
    parser.add_argument("--k", type=int, default=10)
    parser.add_argument("--fuzzy", action="store_true")
    args = parser.parse_args()

    es = Elasticsearch(ES_URL)
    for rank, hit in enumerate(bm25(es, args.query, args.k, args.fuzzy), start=1):
        print(f"{rank:>2}  {hit['score']:6.2f}  {hit['product_id']:>6}  "
              f"{hit['product_name'][:60]:<60}  [{hit['product_class']}]")


if __name__ == "__main__":
    main()
