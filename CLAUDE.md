# CLAUDE.md

This file tells Claude Code how to work in this repo. Read it, then `PROGRESS.md`, at the start of every session.

## What this project is

A full rebuild of a production semantic search system, end to end, on Wayfair's public WANDS dataset: data, model, indexing, serving, deployment, CI, monitoring, and a public hosted demo.

The goal is a finished portfolio project that a recruiter can click, read and run. It must be built the standard way a real team at this scale would build it, with every choice backed by a number we measured.

## Build mode

**Claude builds and runs everything.** This is not a teaching project. Do not write "learn first" paragraphs, do not explain each file, and do not hand commands to the user to run. Run them yourself, including Docker, Elasticsearch, kind, Locust and GitHub Actions.

Stop and ask the user only for:
- Things only they can do: sign-ins (`gh auth login`, Hugging Face), creating tokens, adding GitHub secrets, changing Docker Desktop settings, running a Colab notebook.
- Changes to the fixed stack below.
- Anything hard to undo or public that the plan does not already cover.

There is a separate teaching copy of this project in `~/Documents/semantic-search-rebuild`. Do not edit it.

## Who you are working with

A data scientist with a strong ML, stats and modelling background (embeddings, losses, LoRA, fine-tuning: no need to explain). Newer to production infrastructure. When you report results, use plain words for infrastructure terms.

Never say "as you know", "obviously" or "simply".

## Rules

- **The stack is fixed.** See the table below. Do not add tools that are not in it (no Spark, no LangChain, no Gradio, no vector database other than Elasticsearch, no managed search service such as Elastic Cloud). If something should change, stop, explain why, and wait for agreement.
- **No invented numbers.** Every precision, latency or size figure must come from something run in this repo. If it has not been measured, say so.
- **Every eval run goes into `results/runs.csv`.** Never write a metric anywhere (README, DECISIONS.md, the demo page) that did not come from a logged run.
- **DECISIONS.md:** for each choice, fill in "Chosen", "Rejected" and "Evidence". Leave "Why (in my words)" blank. The user writes it. When they have, check it and say plainly if anything is wrong or missing.
- **Run every "try the alternative" experiment** in the build list. They are the evidence behind each decision.
- **No client details.** This project is modelled on earlier client work, which is private. Never write any client name, client numbers, client domain or client description into code, README, DECISIONS.md, commit messages or the demo. Everything here is about WANDS only.
- **No secrets in git.** Tokens and keys go in `.env` (gitignored) or GitHub secrets. Never print them.
- **No data in git.** `data/`, vectors and model files stay out of git. Files that CI or the demo need go in a GitHub release.
- **Keep it runnable.** The README must work from a fresh clone at every commit to `main`.
- **If something breaks,** say what broke and why in plain words before fixing it, and add one line to `PROGRESS.md` under "Things that broke".
- **Git:** the first commit goes straight to `main`. After that, work on a branch per piece of work, open a PR, let CI run, then merge. End commit messages with the attribution line the harness gives you.

## Writing style

- Simple English. Short sentences. One idea per sentence.
- No em dashes. Use a period, comma, colon or brackets instead.
- Lead with the answer, then the detail.
- No filler, no praise.

## The stack

| Layer | Chosen | Main rejected alternatives |
|---|---|---|
| Data | WANDS (Wayfair ANnotation DataSet) | Amazon ESCI, scraping a retailer, synthetic data |
| Containers | Docker, Docker Compose | Installing everything directly on the laptop |
| Search engine | Elasticsearch 8.15 (free tier), BM25 plus `dense_vector` with HNSW | OpenSearch, pgvector, Chroma, Pinecone, FAISS alone |
| Hybrid ranking | Reciprocal Rank Fusion, written by hand in Python | Elasticsearch's paid RRF, weighted score blending |
| Encoder | `all-mpnet-base-v2` via sentence-transformers | `all-MiniLM-L6-v2`, calling an LLM |
| Fine-tuning | LoRA via `peft` | Full fine-tuning, frozen encoder plus layers |
| Experiment tracking | MLflow (local `mlruns/`) | Notebook names and spreadsheets |
| Embedding job | One Python script | Spark, Ray |
| Index rebuilds | New dated index plus alias swap (`products_live`) | Rebuilding in place |
| Service | FastAPI | Flask, Django |
| Demo page | Plain HTML and JS served by FastAPI | Gradio, Streamlit, a React app |
| Cache | Redis | No cache, in-process cache |
| Load testing | Locust | Hand-written loops |
| CI | GitHub Actions with an eval gate | Manual eval before merging |
| Deployment | Kubernetes, locally with kind | Cloud Run, a single VM with Docker Compose |
| Public demo hosting | Hugging Face Space (Docker SDK, free CPU tier) | Paid cloud VM with k3s, managed Kubernetes, no live demo |
| Monitoring | Structured JSON request logs plus a summary script | No logging |

## Decisions already made by the user (2026-10-28)

- **Model work runs on the Mac first** (PyTorch MPS backend): encoding, LoRA, and the full fine-tune comparison. Only if a run does not fit in memory, write a Colab notebook in `notebooks/` for that one run and ask the user to run it and put the output in `data/`.
- **Public GitHub repo** named `wands-semantic-search`.
- **Hosting:** a Hugging Face Space. Deployed by a GitHub Actions workflow that pushes to the Space with a `HF_TOKEN` repo secret, after the eval gate passes on `main`.
- **Kubernetes stays local on kind.** It is the evidence for replicas, rolling restarts and the killed-replica experiment. The HF Space is the always-available public link.

## Machine and environment

- MacBook, Apple M2, 8 GB RAM, about 30 GB free disk. Memory is the main constraint. Do not run Elasticsearch, kind and model training at the same time.
- Python 3.11 is at `/Users/simardeepkaur/anaconda3/bin/python3.11`. Use a virtual environment in `.venv` (create it in this folder). Pin every dependency in `requirements.txt`.
- Docker Desktop is installed but may not be running. `kubectl` is installed (from Docker Desktop).
- **Not installed:** Homebrew, `gh`, `kind`. Install `gh` and `kind` as standalone binaries into `~/.local/bin` (official release downloads). Do not install Homebrew.

## Steps that need the user

Ask for these at the start of the first session, all together, so the build is not blocked later:

1. Start Docker Desktop. In Settings > Resources, set memory to at least 6 GB.
2. Run `gh auth login` after `gh` is installed.
3. Create a Hugging Face account and an empty Space (SDK: Docker) named `wands-search`. Create a write token and add it as a GitHub repo secret named `HF_TOKEN`. Claude never sees the token.
4. Later: write the "Why (in my words)" lines in DECISIONS.md.

## Dataset facts (checked 2026-10-27)

Files are in `data/WANDS/dataset/`, tab separated:
- `product.csv`: 42,994 products. Columns include `product_id`, `product_name`, `product_class`, `category hierarchy` (with a space, renamed to `category_hierarchy` on load), `product_description`, `product_features`, `rating_count`, `average_rating`, `review_count`. `product_features` is a `|`-separated list of `key:value` features. Treat each feature as one keyword.
- `query.csv`: 480 queries (`query_id`, `query`, `query_class`). Queries average 3.4 words.
- `label.csv`: 233,448 labels (`id`, `query_id`, `product_id`, `label`). Labels are Exact (11.0%), Partial (62.8%), Irrelevant (26.2%).

Verify column names against the files before relying on them.

## Metrics

- **Precision@10, strict:** only Exact counts as relevant. This is the headline metric.
- **Precision@10, lenient:** Exact and Partial both count.
- **Unlabelled share:** fraction of the top 10 with no label for that query. Unlabelled results count as not relevant in both scores. It is a warning light: when it rises, the scores are less trustworthy (labels came from earlier systems, so new methods are biased against).
- **Ceilings** (best possible, from the labels): strict 0.5975, lenient 0.9858 (run `oracle` in `runs.csv`). Strict is capped because 101 queries have 0 Exact labels. An earlier figure of 0.599 counted repeated label rows twice.
- Every eval uses all 480 queries unless the run name says otherwise.
- `results/runs.csv` columns: `run_name, date, git_commit, method, p10_strict, p10_lenient, unlabelled_share, notes`.

## Conventions

- Index names: `products_<method>_<YYYYMMDD>`. The service always queries the alias `products_live`, never an index name.
- Elasticsearch: `english` analyzer on text fields. One shard, zero replicas locally.
- Vectors saved as `.npy` in `data/vectors/`, named by model and pooling.
- Full problem statement, ceilings, baseline definition and known label issues: `docs/PROBLEM.md`.

## What is built so far

- `docker-compose.yml`: one Elasticsearch 8.15.3 node, security off, 1 GB heap, 2 GB memory cap, named volume.
- `src/index_products.py`: creates `products_bm25_<date>` with the mapping, bulk loads all products, checks the count, points `products_live` at it.
- `src/search.py`: plain BM25 `multi_match` over name, description and features, with an optional `--fuzzy` flag.
- `notebooks/01_explore.ipynb`: data exploration.
- `docs/PROBLEM.md`: problem statement, metrics, baseline, known limits.
- `DECISIONS.md`: 3 entries (headline metric, text analyzer, baseline). "Why" lines blank.
- Nothing is committed. There is no git repo or remote yet.

## What is left to build

Build in this order. Each part lists its "try the alternative" experiments, which are required.

1. **Repo and tools.** `git init`, `.gitignore` (already has `data/`, `.venv/`, `.env`, `mlruns/`), install `gh` and `kind`, first commit, create the public repo, push.
2. **Fuzzy experiment.** `fuzziness: AUTO` on one typo query and one synonym query. Write down which it fixes.
3. **Eval.** `eval/run_eval.py`: all 480 queries, strict and lenient P@10, unlabelled share, appended to `runs.csv` with the git commit.
4. **Baselines.** Plain BM25 (the floor). Then BM25 plus linguistic patching (the baseline): stemming, a synonym dictionary, spell correction, rule-based query rewriting with product-class boosting. Synonyms, spelling vocabulary and rewrite rules come from `product.csv` only, never from the eval queries or labels.
5. **Vectors.** Encode products with `all-mpnet-base-v2`. `dense_vector` field with HNSW, vector search in `src/search.py`, eval.
   - Alternatives: exact search (`script_score`) vs HNSW (P@10 and time per query). `all-MiniLM-L6-v2` vs MPNet (P@10 and query encoding time).
6. **Pooling.** Each feature is a keyword. Mean, max and top-3 centroid pooled vectors, one index each, eval each.
7. **Hybrid.** `src/rrf.py`: RRF by hand, k = 60. Hybrid search, eval.
   - Alternative: weighted score blending with scores normalised to 0 to 1, weights 0.3, 0.5, 0.7. Eval each.
8. **LoRA.** Training pairs from the category tree, target similarity set by tree distance. LoRA with sentence-transformers and `peft`, logged to MLflow. Re-encode, re-index, eval. Look at the 20 queries that got worse and write down the pattern.
   - Alternatives: one full fine-tuning run (P@10, training time, saved size). LoRA rank 4 vs rank 16 (P@10, adapter size).
9. **Service.** `src/api.py` with FastAPI: encode the query on CPU with the chosen model, hybrid search on `products_live`, optional filter, return 10. A demo page at `/` that shows BM25 next to hybrid and, for WANDS queries, marks each result Exact, Partial or unlabelled.
10. **Alias swap.** `src/rebuild_index.py`: build a new dated index, check the count, move the alias in one atomic step.
    - Alternative: rebuild in place (delete and recreate under one name) while Locust runs. Count failed or empty responses. Then do it with the alias swap.
11. **Cache.** Redis in `docker-compose.yml`, checked before searching.
    - Alternative: cache off vs on at 50 queries per second, p50 and p99.
12. **Load test.** `loadtest/locustfile.py`. Run at 6 and 50 queries per second. Record p50 and p99.
13. **Dockerfile** for the service.
    - Alternative: `python:3.11` vs `python:3.11-slim` base image size.
14. **CI.** `.github/workflows/eval.yml`: start Elasticsearch, load stored vectors from a GitHub release, run eval, fail if strict P@10 drops below the current best.
    - Alternative: push a deliberately worse model and confirm the check goes red. Keep that PR closed, not merged, as evidence.
15. **Kubernetes.** `k8s/` Deployment (3 replicas) and Service for the API, plus Elasticsearch and Redis. Deploy to kind. Locust against it.
    - Alternative: kill a replica during a load test with 1 replica, then with 3. Compare failures.
16. **Monitoring.** Structured JSON logs in `src/api.py` (query, latency, result count, cache hit). `src/log_summary.py`: zero-result rate, p50, p99, 10 slowest queries.
    - Alternative: zero-result rate for BM25 only vs hybrid on the same query set.
17. **Hugging Face Space.** One Docker image that runs Elasticsearch, Redis and the API together (Spaces allow one container). Notes: Spaces expect port 7860 and a non-root user (uid 1000). Spaces cannot change kernel settings, so set `node.store.allow_mmap: false` for Elasticsearch. The Space has no persistent disk on the free tier, so index from vectors baked into the image at startup. It sleeps after 48 hours with no visitors. Measure the cold start time and put it in the README. Deploy with a GitHub Actions workflow after the eval gate passes.
18. **Write-up.** README: what it is, the live demo link, a results table drawn from `runs.csv`, an architecture diagram, and how to run it from a fresh clone. DECISIONS.md complete except the "Why" lines.

Stretch, only if everything above is done: pad the index to a few million synthetic vectors and rerun the load test (watch the 8 GB RAM limit). Relevance is always scored on the real WANDS products only.

## Repo layout (target)

```
.
├── CLAUDE.md
├── README.md
├── DECISIONS.md
├── PROGRESS.md
├── docs/PROBLEM.md
├── data/                 # WANDS files and vectors, not in git
├── notebooks/
├── src/                  # index_products, search, rrf, encode, train_lora, rebuild_index, api, log_summary
├── eval/run_eval.py
├── results/runs.csv
├── loadtest/locustfile.py
├── k8s/
├── deploy/hf/            # Hugging Face Space image and startup script
├── .github/workflows/
├── docker-compose.yml
├── Dockerfile
└── requirements.txt
```
