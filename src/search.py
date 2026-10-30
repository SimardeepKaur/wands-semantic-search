"""Search WANDS products: plain BM25 on the alias, or vector search on a vector index.

Usage:
    python src/search.py "moen matte black hooks"
    python src/search.py "moen mate blak hooks" --fuzzy
"""
import argparse

from elasticsearch import Elasticsearch

ES_URL = "http://localhost:9200"
ALIAS = "products_live"
FIELDS = ["product_name", "product_description", "product_features"]
SOURCE_FIELDS = ["product_id", "product_name", "product_class"]


def _hits(resp):
    return [
        {"product_id": int(h["_id"]), "score": h["_score"],
         "product_name": h["_source"]["product_name"],
         "product_class": h["_source"].get("product_class")}
        for h in resp["hits"]["hits"]
    ]


def vector_knn(es, index, query_vector, k=10, num_candidates=100, es_filter=None):
    """Approximate nearest neighbours through the HNSW graph."""
    knn = {"field": "vector", "query_vector": query_vector,
           "k": k, "num_candidates": num_candidates}
    if es_filter:
        knn["filter"] = es_filter
    resp = es.search(index=index, knn=knn, size=k, source=SOURCE_FIELDS)
    return _hits(resp)


def vector_exact(es, index, query_vector, k=10):
    """Exact search: score every product with cosine similarity. Slow by design."""
    resp = es.search(index=index, size=k, query={
        "script_score": {
            "query": {"match_all": {}},
            "script": {"source": "cosineSimilarity(params.v, 'vector') + 1.0",
                       "params": {"v": query_vector}},
        },
    }, source=SOURCE_FIELDS)
    return _hits(resp)


def bm25(es, query, k=10, fuzzy=False, es_filter=None):
    """Top k products for a query, as a list of dicts, best first.

    multi_match runs the query against each field and keeps the best field's BM25 score
    (type "best_fields", the default). No field boosts: this is the plain baseline.
    """
    match = {"query": query, "fields": FIELDS}
    if fuzzy:
        # AUTO: words of 1-2 chars must match exactly, 3-5 chars allow 1 edit, 6+ allow 2.
        match["fuzziness"] = "AUTO"
    query_body = {"multi_match": match}
    if es_filter:
        query_body = {"bool": {"must": [query_body], "filter": [es_filter]}}
    resp = es.search(
        index=ALIAS,
        size=k,
        query=query_body,
        source=SOURCE_FIELDS,
    )
    return _hits(resp)


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
