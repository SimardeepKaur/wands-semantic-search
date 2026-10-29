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
- **Chosen:** BM25 plus linguistic patching: stemming, a synonym dictionary, spell correction and rule-based query rewriting. Plain BM25 kept as a floor.
- **Rejected:** Plain BM25 as the baseline (too weak: any synonym-aware method beats it). Fuzzy matching alone (fixes typos, not synonyms).
- **Evidence:** not measured.
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
