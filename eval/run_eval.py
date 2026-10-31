"""Score one search method on the WANDS queries and log the run.

For each query: precision@10 strict (only Exact counts), lenient (Exact and Partial count)
and unlabelled share (results with no label for that query). Unlabelled counts as not relevant.

Writes results/per_query/<run_name>.csv and appends one row to results/runs.csv.
Refuses to log if the run breaks a sanity check (see check_run).

Usage:
    python eval/run_eval.py --method bm25_plain --run-name bm25_plain
    python eval/run_eval.py --method oracle --run-name oracle --notes "scorer check"
    python eval/run_eval.py --method bm25_plain --run-name tmp --no-log   # print only
"""
import argparse
import csv
import datetime as dt
import subprocess
import sys
import time
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

DATA = ROOT / "data/WANDS/dataset"
RUNS_CSV = ROOT / "results/runs.csv"
PER_QUERY_DIR = ROOT / "results/per_query"
RUN_COLUMNS = ["run_name", "date", "git_commit", "method", "p10_strict", "p10_lenient",
               "unlabelled_share", "notes"]
K = 10
N_QUERIES = 480
GRADE = {"Irrelevant": 0, "Partial": 1, "Exact": 2}


def load_queries():
    return pd.read_csv(DATA / "query.csv", sep="\t")


def load_labels():
    """One label per (query, product).

    1,467 pairs appear more than once in label.csv and 14 of them disagree.
    Rule: majority vote, a tie goes to the better label.
    """
    raw = pd.read_csv(DATA / "label.csv", sep="\t")
    counts = raw.groupby(["query_id", "product_id", "label"]).size().rename("n").reset_index()
    counts["grade"] = counts.label.map(GRADE)
    counts = counts.sort_values(["query_id", "product_id", "n", "grade"],
                                ascending=[True, True, False, False])
    best = counts.drop_duplicates(["query_id", "product_id"])
    return {qid: dict(zip(g.product_id, g.label)) for qid, g in best.groupby("query_id")}


def ceilings(labels, query_ids):
    """Best possible scores: every Exact first, then every Partial."""
    strict, lenient = [], []
    for qid in query_ids:
        lab = labels.get(qid, {})
        n_exact = sum(v == "Exact" for v in lab.values())
        n_partial = sum(v == "Partial" for v in lab.values())
        strict.append(min(n_exact, K) / K)
        lenient.append(min(n_exact + n_partial, K) / K)
    return sum(strict) / len(strict), sum(lenient) / len(lenient)


# Which encoder embeds the query for each vector index. Pooled indexes hold pooled
# MiniLM vectors, so plain MiniLM encodes the query; fine-tuned indexes (item 8)
# use their own tuned model, saved by src/train_lora.py.
_MINILM = "sentence-transformers/all-MiniLM-L6-v2"
QUERY_MODELS = {"mpnet": "sentence-transformers/all-mpnet-base-v2",
                "minilm": _MINILM,
                "pool_mean": _MINILM, "pool_max": _MINILM, "pool_top3": _MINILM,
                "lora_r4": str(ROOT / "data/models/lora_r4_merged"),
                "lora_r16": str(ROOT / "data/models/lora_r16_merged"),
                "full_ft": str(ROOT / "data/models/full_ft_merged")}


# ---- methods: each returns a function (query_id, query_text) -> list of product ids ----

def method_oracle(labels):
    def run(qid, _text):
        lab = labels.get(qid, {})
        return sorted(lab, key=lambda pid: (-GRADE[lab[pid]], pid))[:K]
    return run


def method_bm25(fuzzy):
    from elasticsearch import Elasticsearch
    from search import ES_URL, bm25
    es = Elasticsearch(ES_URL)

    def run(_qid, text):
        return [h["product_id"] for h in bm25(es, text, K, fuzzy=fuzzy)]
    return run


def method_patched(synonyms, spell, rewrite):
    from elasticsearch import Elasticsearch
    from patch import bm25_patched, build_resources
    from search import ES_URL
    es = Elasticsearch(ES_URL)
    resources = build_resources()

    def run(_qid, text):
        hits = bm25_patched(es, text, K, synonyms=synonyms, spell=spell,
                            rewrite=rewrite, resources=resources)
        return [h["product_id"] for h in hits]
    return run


def latest_index(es, model_key):
    """The newest products_<model>_<date> index. Eval used to build the name from
    today's date, which broke the day after indexing."""
    names = sorted(es.indices.get(index=f"products_{model_key}_*", expand_wildcards="open"))
    if not names:
        raise SystemExit(f"No products_{model_key}_* index. Run src/index_vectors.py first.")
    return names[-1]


def method_vector(model_key, exact=False):
    from elasticsearch import Elasticsearch
    from sentence_transformers import SentenceTransformer

    from search import ES_URL, vector_exact, vector_knn

    es = Elasticsearch(ES_URL, request_timeout=60)
    model = SentenceTransformer(QUERY_MODELS[model_key], device="cpu")
    index = latest_index(es, model_key)
    search = vector_exact if exact else vector_knn

    def run(_qid, text):
        vec = model.encode(text, normalize_embeddings=True).tolist()
        return [h["product_id"] for h in search(es, index, vec, K)]
    return run


def method_hybrid(kind, w=None, model_key="minilm", spell=False, fuzzy_unseen=False):
    """RRF (k=60) or weighted blend over the top 100 from the patched BM25
    (class-boost rewrite, the item 4 winner) and the top 100 from a vector index.

    spell / fuzzy_unseen change only the keyword leg; the vector leg always
    encodes the query as typed."""
    from elasticsearch import Elasticsearch
    from sentence_transformers import SentenceTransformer

    from patch import bm25_patched, build_resources
    from rrf import blend, rrf
    from search import ES_URL, vector_knn

    es = Elasticsearch(ES_URL, request_timeout=60)
    model = SentenceTransformer(QUERY_MODELS[model_key], device="cpu")
    resources = build_resources()
    index = latest_index(es, model_key)
    top = 100

    def run(_qid, text):
        bm = bm25_patched(es, text, top, synonyms=False, spell=spell, rewrite=True,
                          resources=resources, fuzzy_unseen=fuzzy_unseen)
        vec = model.encode(text, normalize_embeddings=True).tolist()
        vc = vector_knn(es, index, vec, k=top, num_candidates=200)
        if kind == "rrf":
            fused = rrf([[h["product_id"] for h in bm], [h["product_id"] for h in vc]])
        else:
            fused = blend(bm, vc, w)
        return fused[:K]
    return run


def get_method(name, labels):
    if name == "oracle":
        return method_oracle(labels)
    if name == "bm25_plain":
        return method_bm25(fuzzy=False)
    if name == "bm25_fuzzy":
        return method_bm25(fuzzy=True)
    if name == "bm25_syn":
        return method_patched(True, False, False)
    if name == "bm25_spell":
        return method_patched(False, True, False)
    if name == "bm25_rewrite":
        return method_patched(False, False, True)
    if name == "bm25_patched":
        return method_patched(True, True, True)
    if name == "mpnet_hnsw":
        return method_vector("mpnet")
    if name == "mpnet_exact":
        return method_vector("mpnet", exact=True)
    if name == "minilm_hnsw":
        return method_vector("minilm")
    if name in ("pool_mean", "pool_max", "pool_top3"):
        return method_vector(name)
    if name == "hybrid_rrf60":
        return method_hybrid("rrf")
    if name == "hybrid_rrf60_spell":
        return method_hybrid("rrf", spell=True)
    if name == "hybrid_rrf60_fuzzyword":
        return method_hybrid("rrf", fuzzy_unseen=True)
    if name.startswith("blend_w"):
        return method_hybrid("blend", w=float(name.removeprefix("blend_w")))
    if name in ("lora_r4", "lora_r16", "full_ft"):
        return method_vector(name)
    if name.endswith("_hybrid") and name.removesuffix("_hybrid") in ("lora_r4", "lora_r16", "full_ft"):
        return method_hybrid("rrf", model_key=name.removesuffix("_hybrid"))
    raise SystemExit(f"Unknown method {name!r}")


# ---- scoring and checks ----

def score(results, labels):
    rows = []
    for qid, text, pids, secs in results:
        lab = labels.get(qid, {})
        marks = [lab.get(pid) for pid in pids[:K]]
        rows.append({
            "query_id": qid,
            "query": text,
            "p10_strict": sum(m == "Exact" for m in marks) / K,
            "p10_lenient": sum(m in ("Exact", "Partial") for m in marks) / K,
            "unlabelled_share": sum(m is None for m in marks) / K,
            "n_results": len(pids),
            "seconds": round(secs, 5),
            "top10": " ".join(str(p) for p in pids[:K]),
        })
    return pd.DataFrame(rows)


def git_commit():
    return subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=ROOT,
                          capture_output=True, text=True, check=True).stdout.strip()


def git_dirty():
    """Uncommitted changes outside results/ (results/ is what this script writes)."""
    out = subprocess.run(["git", "status", "--porcelain", "--", ".", ":!results"], cwd=ROOT,
                         capture_output=True, text=True, check=True).stdout
    return out.strip()


def check_run(per_query, ceil, full_set):
    problems = []
    if full_set and len(per_query) != N_QUERIES:
        problems.append(f"scored {len(per_query)} queries, expected {N_QUERIES}")
    strict, lenient = per_query.p10_strict.mean(), per_query.p10_lenient.mean()
    if strict > ceil[0] + 1e-9:
        problems.append(f"strict {strict:.4f} is above its ceiling {ceil[0]:.4f}")
    if lenient > ceil[1] + 1e-9:
        problems.append(f"lenient {lenient:.4f} is above its ceiling {ceil[1]:.4f}")
    return problems


def append_run(row):
    RUNS_CSV.parent.mkdir(parents=True, exist_ok=True)
    new = not RUNS_CSV.exists()
    if not new:
        existing = pd.read_csv(RUNS_CSV)
        if row["run_name"] in set(existing.run_name):
            raise SystemExit(f"Run name {row['run_name']!r} is already in runs.csv")
    with RUNS_CSV.open("a", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=RUN_COLUMNS)
        if new:
            writer.writeheader()
        writer.writerow(row)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--method", required=True)
    parser.add_argument("--run-name", required=True)
    parser.add_argument("--notes", default="")
    parser.add_argument("--limit", type=int, help="score only the first N queries (not logged as a full run)")
    parser.add_argument("--no-log", action="store_true", help="print scores, write nothing")
    parser.add_argument("--queries", type=Path,
                        help="another query set keyed by WANDS query_id, e.g. eval/typo50.csv")
    parser.add_argument("--query-column", default="query",
                        help="which column of --queries holds the text to search")
    args = parser.parse_args()

    queries = load_queries()
    set_tag = None
    if args.queries:
        queries = pd.read_csv(args.queries)[["query_id", args.query_column]]
        queries = queries.rename(columns={args.query_column: "query"})
        set_tag = args.queries.stem + ("" if args.query_column == "query"
                                       else f".{args.query_column}")
    if args.limit:
        queries = queries.head(args.limit)
    full_set = args.limit is None and set_tag is None
    labels = load_labels()
    ceil = ceilings(labels, queries.query_id)

    if not args.no_log:
        if set_tag and args.queries.stem not in args.run_name:
            raise SystemExit(f"A run on {args.queries.name} must have "
                             f"{args.queries.stem!r} in its name.")
        if not set_tag and not full_set and "subset" not in args.run_name:
            raise SystemExit("A run on part of the queries must have 'subset' in its name.")
        dirty = git_dirty()
        if dirty:
            raise SystemExit(f"Commit your changes first, so git_commit matches the code:\n{dirty}")

    run = get_method(args.method, labels)
    results = []
    for qid, text in zip(queries.query_id, queries["query"]):
        start = time.perf_counter()
        pids = run(int(qid), text)
        results.append((int(qid), text, pids, time.perf_counter() - start))
    per_query = score(results, labels)

    strict = per_query.p10_strict.mean()
    lenient = per_query.p10_lenient.mean()
    unlab = per_query.unlabelled_share.mean()
    print(f"{args.run_name}: strict {strict:.4f}  lenient {lenient:.4f}  unlabelled {unlab:.4f}"
          f"  (ceilings {ceil[0]:.4f} / {ceil[1]:.4f}, {len(per_query)} queries,"
          f" median {per_query.seconds.median() * 1000:.1f} ms per query)")

    problems = check_run(per_query, ceil, full_set)
    if problems:
        raise SystemExit("Not logged. Sanity check failed: " + "; ".join(problems))
    if args.no_log:
        return

    PER_QUERY_DIR.mkdir(parents=True, exist_ok=True)
    per_query.to_csv(PER_QUERY_DIR / f"{args.run_name}.csv", index=False)
    append_run({
        "run_name": args.run_name,
        "date": dt.date.today().isoformat(),
        "git_commit": git_commit(),
        # Runs on another query set carry its tag, so the CI gate (which reads the
        # best run of the exact serving method name) only ever sees 480-query runs.
        "method": args.method + (f"@{set_tag}" if set_tag else ""),
        "p10_strict": round(strict, 4),
        "p10_lenient": round(lenient, 4),
        "unlabelled_share": round(unlab, 4),
        "notes": args.notes,
    })
    print(f"Logged to {RUNS_CSV.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
