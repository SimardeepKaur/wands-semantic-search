# Build plan

This file drives the build loop. Each loop iteration reads it, does the next unticked item, checks it, and ticks it. The rules in `CLAUDE.md` always win over this file.

The plan fixes **what each item must produce and how it is checked**. It does not fix what the numbers will be. Numbers come only from runs.

---

## 1. The loop

### One iteration

1. Read `CLAUDE.md`, this file, the last entry in `PROGRESS.md`, `git status` and `git log -5`.
2. Pick the first item below that is not ticked. If one is marked `[~]` (in progress), resume it.
3. Check its **Needs** line. If a user step is missing, mark the item `[!]` (blocked), send the user a notification, and move to the next item that does not depend on it. If nothing can move, wait.
4. Stop any service the item does not need (see "Memory rules"). Start the ones it needs.
5. Work on a branch `item-NN-<short-name>`.
6. Run the item's **Done when** checks. Every check must pass.
7. Record: eval rows through `eval/run_eval.py`, other numbers in `results/perf.csv`, a `DECISIONS.md` entry if the item makes a choice, one line in `PROGRESS.md`.
8. Tick the item `[x]` in this file on the same branch. Commit, push, open a PR, wait for CI, merge with a merge commit (not squash), so the `git_commit` of every logged run stays on `main`.
9. End the iteration. A long job (encoding, training, load test) runs in the background and the next iteration starts when it finishes.

One iteration does one item, or one clear part of a large item (item 8 has five runs).

### When a check fails

1. Say in plain words what broke and why.
2. Add one line to `PROGRESS.md` under "Things that broke".
3. Fix and retry. After 3 failed fixes for the same cause, mark the item `[!]` and notify the user.

### Stop and ask the user (the loop never decides these)

- A user-only step: sign-ins, tokens, secrets, Docker Desktop settings, a Colab run.
- An experiment says a fixed stack choice is wrong. For example, MiniLM beats MPNet, or blending beats RRF. Record the number, then stop. Changing the stack needs agreement.
- Anything public or hard to undo that this plan does not already cover.
- A sanity check fails in a way that suggests the eval itself is wrong (see "Checks on every eval").

### Checks on every eval run

The eval script refuses to log a run if any of these fail:
- All 480 queries were scored (unless the run name says otherwise).
- Scores at or below the ceilings, strict 0.5975 and lenient 0.9858, computed from the labels on every run. A score above a ceiling means a bug.
- The git tree is clean, so `git_commit` in `runs.csv` points at the code that made the number.
- Per-query results are saved to `results/per_query/<run_name>.csv`.

### Checks on every commit

- No leakage: only files in `eval/` may read `query.csv` or `label.csv` (a grep check, also run in CI). Item 4 patching code and item 8 training code must pass this.
- No secrets: no token-shaped strings in the diff.
- No data: nothing from `data/`, no `.npy`, no model files.

### How a choice is made

- The winner on strict P@10 is chosen only if a paired bootstrap over the 480 queries (10,000 resamples, numpy only) gives a 95% interval for the difference that excludes 0.
- If the interval includes 0, the simpler or cheaper option wins (cheaper means less time per query, less memory or a smaller file).
- Speed and size choices use the measured p50 and p99, not a single run.
- The chosen option of each item is the default for the items after it.

### Memory rules (8 GB RAM)

- Never at the same time: Elasticsearch, kind, model training or bulk encoding.
- Bulk encoding and training run with Docker Desktop quit entirely (`osascript -e 'quit app "Docker"'`), not just containers stopped: the Docker VM holds its memory either way. Restart Docker afterwards. Vectors are saved to `data/vectors/` first, then Elasticsearch starts and indexes them.
- Before item 15, stop the Docker Compose services.
- Before any heavy job, check `docker ps` and free memory.

---

## 2. Items

Status: `[ ]` to do, `[~]` in progress, `[!]` blocked, `[x]` done.

### Phase A: setup

- [x] **1. Repo and tools**
  - Do: create `.venv` with Python 3.11, pin all dependencies. Install `gh` and `kind` into `~/.local/bin` from official releases, checking the published checksums. `git init`, first commit to `main`, create the public repo `wands-semantic-search`, push.
  - Needs: user steps 1 and 2 (Docker running, `gh auth login`). Everything except creating the repo and pushing can be done before.
  - Done when: `gh repo view` shows a public repo. `git ls-files` lists no data, vectors, models or `.env`. `gh --version` and `kind version` run. A fresh venv installs `requirements.txt` without errors.

### Phase B: text search (Elasticsearch on)

- [x] **2. Fuzzy experiment**
  - Do: run one typo query and one synonym query with and without `fuzziness: AUTO`. Show the top 10 with labels.
  - Done when: `docs/experiments.md` says which of the two fuzzy fixes, with the result lists. `DECISIONS.md` has a "Fuzzy matching" entry.

- [x] **3. Eval**
  - Do: `eval/run_eval.py` (all 480 queries, strict and lenient P@10, unlabelled share, per-query file, appends to `runs.csv` with the commit). `eval/compare.py <run_a> <run_b>` for the paired bootstrap.
  - Done when: an "oracle" run (labelled Exact products ranked first, then Partial) gives exactly the ceilings computed from the labels (strict 0.5975, lenient 0.9858). This proves the scorer. The oracle row is logged with method `oracle`. `bm25_plain` and `bm25_fuzzy` are logged, and `bm25_fuzzy` is added to the "Fuzzy matching" entry in `DECISIONS.md`.

- [x] **4. Baselines**
  - Do: BM25 plus linguistic patching. Built from `product.csv` only:
    - Synonyms: from product class names and the category tree.
    - Spell correction: Elasticsearch's term suggester over the product index.
    - Query rewriting: match query words to product classes and boost those classes.
  - Runs: `bm25_plain` (already there), then one row per patch added in turn (`+synonyms`, `+spell`, `+rewrite`), then `bm25_patched` with all of them.
  - Done when: all rows logged. Leakage check passes. `compare.py` of `bm25_patched` vs `bm25_plain` written in `docs/experiments.md`. `DECISIONS.md` "Baseline" entry has its evidence.

### Phase C: vectors

- [x] **5. Vectors** (done; the user switched the stack's encoder to MiniLM on 2026-10-29: MiniLM measured better than MPNet. Items 6-9 use `minilm`.)
  - Do: `src/encode.py` encodes each product with `all-mpnet-base-v2` on MPS (Elasticsearch stopped). Product text: name, product class, category path, then description, cut to the model's input limit. Index a `dense_vector` field with HNSW (cosine). Add vector search to `src/search.py`.
  - Runs: `mpnet_hnsw`, `mpnet_exact` (`script_score`), `minilm_hnsw`.
  - Also measured, in `results/perf.csv`: time per query for HNSW vs exact search (p50, p99 over 480 queries), and query encoding time on CPU for MPNet vs MiniLM.
  - Done when: the vector file has 42,994 rows, no NaN values and unit norms. Three runs logged. Timings logged. `DECISIONS.md` has "Encoder" and "Exact vs HNSW" entries.

- [x] **6. Pooling** (done; all three pooled variants reliably worse than the whole-text vector, rejected)
  - Do: encode each of the 128,919 unique feature strings once with MiniLM (the chosen encoder), then build per-product vectors by lookup:
    - Mean: average of the product's feature vectors.
    - Max: element-wise max, then normalised.
    - Top-3 centroid: the mean of the 3 feature vectors closest to the product's mean vector (its 3 most typical features).
    - One index each.
  - Runs: `pool_mean`, `pool_max`, `pool_top3`, compared with `minilm_hnsw` (the whole-text vector of the chosen encoder).
  - Done when: three runs logged, compare written, `DECISIONS.md` "Pooling" entry.

### Phase D: hybrid

- [x] **7. Hybrid** (done; RRF k=60 is the new best at strict 0.3688, blending rejected as a tie that needs tuning)
  - Do: `src/rrf.py`, RRF by hand, k = 60, over the top 100 from BM25 patched (= `bm25_rewrite_v3`, class boosts only; item 4 rejected synonyms and spell) and the top 100 from the best vector index. Unit test against a small example worked out by hand.
  - Runs: `hybrid_rrf60`, `blend_w0.3`, `blend_w0.5`, `blend_w0.7` (scores min-max normalised to 0 to 1 per query).
  - Done when: four runs logged, the RRF test passes, compare written, `DECISIONS.md` "Hybrid ranking" entry.

### Phase E: fine-tuning (Elasticsearch stopped while training)

- [x] **8. LoRA** (done; every fine-tune lost to the untuned encoder, category-tree objective erases names/styles/specs; no fine-tuning deployed)
  - Do: `src/train_lora.py`. Training pairs are product pairs sampled from the category tree. The target similarity is the depth of the shared category path divided by the full depth. LoRA through `peft` on sentence-transformers, logged to MLflow (`mlruns/`). 10% of products held out for the training loss. Re-encode, re-index, eval.
  - Runs: `lora_r4`, `lora_r16`, `full_ft`. Each one vector-only and in hybrid.
  - Also measured: training time, adapter or model size on disk, both in MLflow and `results/perf.csv`.
  - If the full fine-tune does not fit in memory: write `notebooks/02_full_finetune_colab.ipynb`, mark the run `[!]` and ask the user to run it.
  - Done when: six runs logged, MLflow has every training run, `docs/experiments.md` lists the 20 queries that got worse with the pattern written down, `DECISIONS.md` has "Fine-tuning method" and "LoRA rank" entries.

### Phase F: service (Elasticsearch, Redis, API)

- [x] **9. Service** (done; smoke+consistency tests pass, API matches run hybrid_rrf60_det exactly, demo page checked in the browser)
  - Do: `src/api.py` (FastAPI). Encode the query on CPU with the chosen model, run the chosen hybrid on `products_live`, optional product-class filter, return 10. Demo page at `/`: BM25 next to hybrid, and for WANDS queries each result marked Exact, Partial or unlabelled. JSON request logs from the start (query, latency, result count, cache hit).
  - Done when: a smoke test passes for `/`, `/search` and `/health`. For 20 WANDS queries the API returns the same product IDs as the eval run of the same method.

- [x] **10. Alias swap** (done; in place: 30 failures and a 139s incomplete window, swap: 0 failures)
  - Do: `src/rebuild_index.py`: build a new dated index, check the count, move `products_live` in one atomic step.
  - Experiment: with Locust running, rebuild in place (delete and recreate under one name), then rebuild with the alias swap. Count failed and empty responses.
  - Done when: both counts in `results/perf.csv`, `DECISIONS.md` "Index rebuilds" entry.

- [x] **11. Cache** (done; off: 24 req/s at p50 1.2s; on: 44 req/s at p50 6ms, hit rate 0.936)
  - Do: Redis in `docker-compose.yml`. Key: normalised query, method, filter. Checked before searching.
  - Experiment: 50 queries per second, cache off vs on, p50 and p99. Queries drawn at random from the 480 WANDS queries (this mix is written down, since it sets the hit rate).
  - Done when: numbers and hit rate in `results/perf.csv`, `DECISIONS.md` "Cache" entry.

- [x] **12. Load test** (done; 6 qps: p50 20ms p99 660ms, 50 qps: p50 12ms p99 160ms, 0 failures)
  - Do: `loadtest/locustfile.py`. Runs at 6 and 50 queries per second, fixed duration.
  - Done when: p50, p99 and failure count for both rates in `results/perf.csv`.

- [x] **13. Dockerfile** (done; slim 2.03 GB vs full 3.42 GB, slim container passes the smoke checks)
  - Do: service image with CPU-only PyTorch.
  - Experiment: `python:3.11` vs `python:3.11-slim`, image size.
  - Done when: both sizes in `results/perf.csv`, the chosen image passes the item 9 smoke test, `DECISIONS.md` "Base image" entry.

- [x] **16. Monitoring** (done; zero-result rate bm25 0.0021 vs hybrid 0.0, summary script and committed log)
  - Do: `src/log_summary.py`: zero-result rate, p50, p99, 10 slowest queries.
  - Experiment: zero-result rate for BM25 only vs hybrid on the same query set.
  - Done when: summary output saved in `docs/experiments.md`, both rates in `results/perf.csv`.

### Phase G: ship

- [ ] **14. CI**
  - Do: put the chosen product vectors in a GitHub release. `.github/workflows/eval.yml`: start Elasticsearch, download the vectors, encode the 480 queries on CPU, run the eval, fail if strict P@10 is below the current best for that method in `runs.csv`. Also runs the leakage grep.
  - Experiment: a PR with a deliberately worse model. The check must go red. Close the PR without merging.
  - Done when: the check is green on `main`, red on the evidence PR, and the PR link is in `DECISIONS.md` "Eval gate".
  - Note: CPU query encoding on the runner can differ from MPS in the last float digits. If that moves the score, the gate compares against the score the runner itself measured on `main`, and this is written down.

- [ ] **15. Kubernetes** (Docker Compose stopped)
  - Do: `k8s/` with Deployment (3 replicas, readiness probe) and Service for the API, plus Elasticsearch and Redis. kind cluster, image loaded with `kind load`. Locust against it.
  - Experiment: kill a pod during a load test, with 1 replica and with 3. Compare failures.
  - If 3 replicas plus Elasticsearch do not fit in Docker's memory: record the measured memory, then stop and ask.
  - Done when: failure counts in `results/perf.csv`, `DECISIONS.md` "Replicas" entry.

- [ ] **17. Hugging Face Space**
  - Do: `deploy/hf/`: one image with Elasticsearch, Redis and the API. Port 7860, user uid 1000, `node.store.allow_mmap: false`. Vectors downloaded from the GitHub release at image build time and indexed at startup. `.github/workflows/deploy.yml` pushes to the Space after the eval gate passes on `main`.
  - Needs: user step 3 (Space and `HF_TOKEN` secret).
  - Done when: the public URL answers `/health` and a search. Cold start time measured (from container start to the first good search) and in `results/perf.csv`.

- [ ] **18. Write-up**
  - Do: README with what it is, the live link, an architecture diagram and how to run it. The results table is generated from `runs.csv` and `perf.csv` by a script, so no number is typed by hand. `DECISIONS.md` complete except the "Why" lines.
  - Done when: a fresh clone into a temp folder, following only the README, reaches a working search. Every number in the README matches a row in `runs.csv` or `perf.csv`.

---

## 3. Choices made in this plan (change any before the loop starts)

1. **Choices use all 480 queries**, as `CLAUDE.md` says. Many choices are made on the same queries that give the final score, so the final score is a little optimistic. The README will say so. The other option is to split the queries into 240 for choosing and 240 for the final score, at the cost of wider intervals.
2. **Top-3 centroid** means the mean of the 3 features closest to the product's mean vector.
3. **Product text for encoding:** name, class, category path, then description, cut to the model limit.
4. **Decision rule:** paired bootstrap, 95% interval, and the cheaper option wins a tie.
5. **New files** not in the target layout: `PLAN.md`, `docs/experiments.md`, `results/perf.csv`, `results/per_query/`.
6. **The loop merges its own PRs** once CI is green. Before item 14 exists, the local checks in this file act as the gate.
7. **Item 16 moves up** to sit after item 13, since the logs it reads start in item 9.
