# Decisions

One entry per choice. Claude fills in "Chosen", "Rejected" and "Evidence" when we have a number. I write "Why (in my words)" myself. This file is my interview script for "what stack did you use and why".

## Template

### <Decision name>
- **Chosen:**
- **Rejected:**
- **Evidence:** (a number from `results/runs.csv` or an experiment, or "not measured")
- **Why (in my words):**

---

<!-- Entries start below. Newest at the bottom. -->

### Headline metric
- **Chosen:** Strict precision@10 (only Exact counts). Lenient P@10 and unlabelled share reported next to it.
- **Rejected:** Lenient P@10 as headline (near its 0.9858 ceiling, blind to brand and colour). nDCG@10 with graded credit (credit weights are a guess).
- **Evidence:** Ceilings from run `oracle`: strict 0.5975, lenient 0.9858.
- **Why (in my words):**

### Text analyzer
- **Chosen:** Elasticsearch `english` analyzer on all text fields (lowercase, stop words removed, stemming: "hooks" -> "hook").
- **Rejected:** `standard` analyzer (lowercase only, so "hooks" does not match "hook").
- **Evidence:** not measured. `_analyze` on "Moen matte black hooks" gives `moen, matt, black, hook`.
- **Why (in my words):**

### Baseline
- **Chosen:** (written before measurement; superseded by "What goes into the patched baseline" below) BM25 plus linguistic patching, with plain BM25 kept as a floor. Measurement then rejected the synonym and spell parts: the kept baseline is BM25 plus class-boost rewriting only.
- **Rejected:** Plain BM25 as the baseline (too weak a bar). Fuzzy matching alone (fixes typos, not synonyms).
- **Evidence:** see "What goes into the patched baseline".
- **Why (in my words):**

### Fuzzy matching
- **Chosen:** No fuzzy matching by default. Spelling is handled by spell correction in the patched baseline (item 4).
- **Rejected:** `fuzziness: AUTO` on every query.
- **Evidence:** `docs/experiments.md`, item 2. On "ligth bulb" fuzzy brings in the Light Bulbs class. On "toddler couch fold out" it brings in unrelated products and cannot map "couch" to "sofa". Full set (runs `bm25_plain`, `bm25_fuzzy`): strict P@10 0.3229 -> 0.2977, difference -0.0252, 95% interval -0.0365 to -0.0140. Fuzzy is better on 48 queries and worse on 95. Lenient also drops (0.6892 -> 0.6381) and unlabelled share rises (0.2554 -> 0.3090). Median time per query 13.0 ms -> 29.7 ms.
- **Why (in my words):**

### What goes into the patched baseline
- **Chosen:** BM25 plus class-boost query rewriting only (`bm25_rewrite_v3`). Plain BM25 stays the floor and the strict bar.
- **Rejected:** Product-only synonym expansion (strict -0.0104, 95% interval -0.0188 to -0.0025). Spell correction (strict +0.0017, interval includes 0, tie goes to the simpler option). Fuzzy matching (see above).
- **Evidence:** runs `bm25_syn_v3`, `bm25_spell_v3`, `bm25_rewrite_v3`, `bm25_patched_v3` vs `bm25_plain` in `results/runs.csv`; bootstrap tables in `docs/experiments.md`. Rewrite: lenient +0.0248 (0.0067 to 0.0425), unlabelled share -0.0200, strict unchanged.
- **Why (in my words):**

### Exact vector search vs HNSW
- **Chosen:** HNSW (Elasticsearch's indexed dense_vector).
- **Rejected:** Exact search by script_score.
- **Evidence:** Runs `mpnet_hnsw` vs `mpnet_exact`: strict 0.3315 vs 0.3333, every 95% interval includes 0, so no measurable quality loss. Latency p50 63.5 vs 73.6 ms at 43k products (query encoding dominates at this size; HNSW is the scalable choice).
- **Why (in my words):**

### Encoder
- **Chosen:** `all-MiniLM-L6-v2`. The stack originally fixed `all-mpnet-base-v2`; the measurement said otherwise and the user agreed to switch (2026-10-29). All later work (pooling, hybrid, LoRA, the service) uses MiniLM.
- **Rejected:** `all-mpnet-base-v2` (bigger and slower, and it scored lower here). Calling an LLM to embed (cost and latency, not measured).
- **Evidence:** `minilm_hnsw` beats `mpnet_hnsw` on strict P@10: 0.3475 vs 0.3315 (+0.0160, 95% interval 0.0035 to 0.0281, reliable). Also fewer unlabelled results (0.1919 vs 0.2115), 4x faster query encoding (16.4 vs 63.5 ms p50), 6x faster product encoding (7.7 vs 46.1 min), half the vector size (384 vs 768). Runs `mpnet_hnsw`, `mpnet_exact`, `minilm_hnsw`; `docs/experiments.md` item 5.
- **Why (in my words):**

### Pooling (product vector from feature vectors)
- **Chosen:** No feature pooling. The product vector is the whole-text MiniLM vector (name, class, category path, description encoded as one passage).
- **Rejected:** Mean pooling over the product's feature vectors (strict P@10 0.0738 vs 0.3475, -0.2737, 95% interval -0.3056 to -0.2421). Element-wise max (0.0469). Top-3 centroid (0.0525). All reliably worse on every metric, with unlabelled share around 0.75.
- **Evidence:** runs `pool_mean`, `pool_max`, `pool_top3` vs `minilm_hnsw` in `results/runs.csv`; tables in `docs/experiments.md` item 6.
- **Why (in my words):**

### Hybrid ranking
- **Chosen:** Reciprocal Rank Fusion, hand-written, k = 60, over the top 100 from patched BM25 and the top 100 from the MiniLM index. New best system: strict P@10 0.3688, lenient 0.8069, unlabelled 0.1598.
- **Rejected:** Weighted score blending (min-max, vector weight 0.3 / 0.5 / 0.7). The best blend ties RRF on strict (0.3644, interval includes 0) and loses on lenient and unlabelled at w = 0.5; w = 0.3 is reliably worse. Blending also needs its weight tuned per corpus, and tuning it on the eval queries would leak. Vector-only and keyword-only both reliably worse than the hybrid.
- **Evidence:** runs `hybrid_rrf60`, `blend_w0.3`, `blend_w0.5`, `blend_w0.7` in `results/runs.csv`; bootstrap tables in `docs/experiments.md` item 7.
- **Why (in my words):**

### Fine-tuning method
- **Chosen:** No fine-tuning. The deployed encoder stays the off-the-shelf `all-MiniLM-L6-v2`. The stack's LoRA-via-peft pipeline was built and measured (`src/train_lora.py`, `notebooks/02_finetune_colab.ipynb`, MLflow runs in `mlruns/`), and every tuned model lost to the untuned one.
- **Rejected:** LoRA r4 (strict P@10 0.2738 vs 0.3475, -0.0737, interval -0.0929 to -0.0554). LoRA r16 (0.1727). Full fine-tuning (0.1087, and 91.9 MB saved vs a 0.16 MB adapter). The category-tree objective (the only training signal available without touching the eval labels) teaches category membership and erases brand names, cross-category styles and specs; see `docs/experiments.md` item 8 for the worst-20 pattern.
- **Evidence:** runs `lora_r4`, `lora_r16`, `full_ft` and their `_hybrid` counterparts vs `minilm_hnsw` and `hybrid_rrf60` in `results/runs.csv`; bootstrap tables and the delta trinsic example in `docs/experiments.md` item 8.
- **Why (in my words):**

### LoRA rank (conditional: if fine-tuning were used)
- **Chosen:** Rank 4. Both ranks hurt here, but r4 hurt reliably less than r16 (strict 0.2738 vs 0.1727, difference -0.1010, interval -0.1200 to -0.0827) and its adapter is a quarter the size (0.16 vs 0.6 MB). Training time identical (6.8 min on a T4).
- **Rejected:** Rank 16 (more capacity to learn the wrong objective, worse on every metric). Full fine-tuning (worst scores, 575x the artifact size).
- **Evidence:** runs `lora_r4` vs `lora_r16` in `results/runs.csv`; `results/perf.csv` finetune rows; MLflow.
- **Why (in my words):**

### Index rebuilds
- **Chosen:** Build a new dated index beside the live one, check the count, move the `products_live` alias in one atomic step (`src/rebuild_index.py`). The old index is kept as the rollback target.
- **Rejected:** Rebuilding in place under one name. Under 6 requests/s it produced 30 failed or empty responses and left the index incomplete for 139 seconds, most of that invisible to error counts (responses looked fine while missing most of the catalogue). The alias swap produced 0 failures on the same load.
- **Evidence:** `results/perf.csv` rebuild_under_load rows; Locust CSVs in `results/loadtest/`; `docs/experiments.md` item 10.
- **Why (in my words):**

### Cache
- **Chosen:** Redis (64 MB, least-recently-used eviction), checked before searching. Key: normalised query, result count, filter. 10-minute expiry. The service runs without it if Redis is down.
- **Rejected:** No cache (saturates at 23.9 of 50 requested searches per second, p50 1200 ms, p99 16000 ms on this machine). In-process cache (dies with each replica and cannot be shared between the 3 Kubernetes replicas of item 15).
- **Evidence:** `results/perf.csv` cache_50qps rows; Locust CSVs `results/loadtest/cache_off_*`, `cache_on_*`; hit rate 0.936 from Redis keyspace stats; `docs/experiments.md` item 11.
- **Why (in my words):**

### Base image
- **Chosen:** `python:3.11-slim`. Image: 2.03 GB. The same Dockerfile on full `python:3.11` gives 3.42 GB; slim drops 1.4 GB of compilers and system packages the service never uses. Wheels cover every dependency, so nothing needs compiling at build time.
- **Rejected:** `python:3.11` (3.42 GB, no benefit here). Alpine was not tried: PyTorch does not ship musl wheels, so it would mean compiling.
- **Evidence:** `results/perf.csv` docker_image rows; the slim container passes the /health, /, /search, filter and cache checks against live Elasticsearch and Redis.
- **Why (in my words):**

### Eval gate
- **Chosen:** A GitHub Actions gate on every PR and push to main: rebuild the index from released vectors, re-measure the serving method on all 480 queries, fail below best-logged strict P@10 minus 0.005 (tolerance documented in `eval/ci_gate.py`).
- **Rejected:** Manual eval before merging (nothing enforces it). A zero-tolerance gate (HNSW rebuild noise and CPU float differences would make it flaky; measured wobble is under 0.002, a real regression costs 0.02 or more).
- **Evidence:** Green on its own PR (runner strict 0.3675, floor 0.3638). Red on the deliberate regression, runner strict 0.3219: https://github.com/SimardeepKaur/wands-semantic-search/pull/16, closed unmerged.
- **Why (in my words):**

### Replica count
- **Chosen:** 3 API replicas behind one Service (`k8s/api.yaml`), each gated by a readiness probe on `/health`.
- **Rejected:** 1 replica.
- **Evidence:** Kill-a-pod experiment on kind under 6 users of load (`perf.csv`, `k8s_kill`): with 1 replica, 70 of 536 requests failed while Kubernetes rebuilt the pod and waited for it to load the model and pass readiness; with 3 replicas, the same kill failed 0 of 836.
- **Why (in my words):**

### Demo hosting hardware
- **Chosen:** Hugging Face Space on CPU Upgrade (8 vCPU, 32 GB, $0.03 per hour) paid from $5 of prepaid credits, with auto-sleep after 1 hour of inactivity. User decision 2026-10-30.
- **Rejected:** Free CPU Basic (no longer exists for new accounts: the Space was quota-paused at creation, restart returned 403, and HF staff confirmed on the forum that compute Spaces now need a paid plan). PRO at $9 per month (always on, no wake wait, but a recurring charge). Always-on paid hardware without sleep (about $21.60 per month at $0.03 per hour).
- **Evidence:** With sleep on, billing runs only while the Space is awake, so $5 covers roughly 166 awake-hours. Measured cold start on wake: 211 s; warm public search 133 ms uncached, 0.5 ms cached (`hf_space` rows in `results/perf.csv`).
- **Why (in my words):**

### Typo handling
- **Chosen:** Spell correction on the keyword leg of the hybrid: each query word the catalogue has never seen is replaced by Elasticsearch's term-suggester best guess (max 2 edits). Words the catalogue knows are never touched. The vector leg encodes the query as typed.
- **Rejected:** Per-word fuzzy fallback (fuzziness AUTO on unseen words only): tied with spell on the typo set, slower, and more matches per query. Plain hybrid (no typo handling): reliably worse on typos. Fuzzy on every word (item 2, already rejected).
- **Evidence:** Typo set of 50 WANDS queries with one typo each (`eval/typo50.csv`): strict P@10 plain 0.198, spell 0.224 (diff +0.026, 95% interval +0.008 to +0.048), fuzzy 0.250 (+0.052, +0.016 to +0.098), fuzzy vs spell a tie (-0.006 to +0.068). All 480: plain 0.3673, spell 0.3671 (interval -0.0010 to +0.0004). Extra time where it fires: spell +7.5 ms, fuzzy +11.3 ms (typo set). Runs `typo50_*` and `all480_*` in `results/runs.csv`; full write-up in `docs/experiments.md`, "Typo handling". Known gap: sound-alike typos ("sopha" becomes "sophia").
- **Why (in my words):**
