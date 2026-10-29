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
