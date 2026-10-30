"""The search service (item 9).

FastAPI app. Each /search request runs two systems over the products_live alias:
plain BM25 (the keyword floor) and the measured best hybrid (RRF k=60 over the
top 100 from patched BM25 with class-boost rewriting and the top 100 nearest
MiniLM vectors). The query is encoded on CPU at request time. Optional exact
product-class filter. Returns 10 by default.

The demo page at / shows the two result lists side by side. If the typed query
is one of the 480 WANDS queries and data/demo_labels.json exists (written by
eval/export_demo_labels.py), each result gets its label badge. Labels colour
badges only; they never touch ranking, and this file never reads the eval data.

Every request writes one JSON log line to stdout: timestamp, query, k, filter,
latency in ms, result count, cache_hit (always false until the Redis item).

Run:
    .venv/bin/uvicorn api:app --app-dir src --port 8000
"""
import json
import logging
import sys
import time
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Query
from fastapi.responses import FileResponse

sys.path.insert(0, str(Path(__file__).resolve().parent))

ROOT = Path(__file__).resolve().parents[1]
STATIC = Path(__file__).resolve().parent / "static"
LABELS_JSON = ROOT / "data/demo_labels.json"
MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"
TOP = 100       # depth of each list going into RRF, as measured in item 7
RRF_K = 60

log = logging.getLogger("wands.api")
logging.basicConfig(level=logging.INFO, format="%(message)s", stream=sys.stdout)

state = {}


@asynccontextmanager
async def lifespan(app):
    from elasticsearch import Elasticsearch
    from sentence_transformers import SentenceTransformer

    from patch import build_resources
    from search import ES_URL

    state["es"] = Elasticsearch(ES_URL, request_timeout=30)
    state["model"] = SentenceTransformer(MODEL_NAME, device="cpu")
    state["resources"] = build_resources()
    state["labels"] = (json.loads(LABELS_JSON.read_text())
                       if LABELS_JSON.exists() else {})
    yield
    state.clear()


app = FastAPI(title="WANDS semantic search", lifespan=lifespan)


def _mark(hits, label_map):
    return [dict(h, label=label_map.get(str(h["product_id"]))) for h in hits]


@app.get("/health")
def health():
    from search import ALIAS
    es = state["es"]
    alias_to = list(es.indices.get_alias(name=ALIAS).keys())
    return {"status": "ok", "alias": ALIAS, "index": alias_to,
            "docs": es.count(index=ALIAS)["count"],
            "labels_loaded": len(state["labels"])}


@app.get("/search")
def search(q: str = Query(min_length=1), k: int = Query(10, ge=1, le=50),
           product_class: str | None = None):
    from patch import bm25_patched
    from rrf import rrf
    from search import ALIAS, bm25, vector_knn

    start = time.perf_counter()
    es_filter = ({"term": {"product_class.raw": product_class}}
                 if product_class else None)

    plain = bm25(state["es"], q, k=k, es_filter=es_filter)

    vec = state["model"].encode(q, normalize_embeddings=True).tolist()
    bm_leg = bm25_patched(state["es"], q, TOP, synonyms=False, spell=False,
                          rewrite=True, resources=state["resources"],
                          es_filter=es_filter)
    vec_leg = vector_knn(state["es"], ALIAS, vec, k=TOP, num_candidates=200,
                         es_filter=es_filter)
    by_id = {h["product_id"]: h for h in bm_leg + vec_leg}
    fused = rrf([[h["product_id"] for h in bm_leg],
                 [h["product_id"] for h in vec_leg]], k=RRF_K)[:k]
    hybrid = [by_id[pid] for pid in fused]

    label_map = state["labels"].get(q.strip().lower(), {})
    took_ms = round((time.perf_counter() - start) * 1000, 1)
    log.info(json.dumps({
        "ts": time.strftime("%Y-%m-%dT%H:%M:%S"), "query": q, "k": k,
        "class_filter": product_class, "latency_ms": took_ms,
        "n_results": len(hybrid), "cache_hit": False,
    }))
    return {"query": q, "k": k, "took_ms": took_ms,
            "labels_known": bool(label_map),
            "bm25": _mark(plain, label_map), "hybrid": _mark(hybrid, label_map)}


@app.get("/")
def index():
    return FileResponse(STATIC / "index.html")
