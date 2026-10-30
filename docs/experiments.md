# Experiments

Notes and raw output for each "try the alternative" experiment. Full-set scores live in `results/runs.csv` only.

## Item 2: fuzzy matching (2026-10-28)

Two WANDS queries, plain BM25 (`multi_match` over name, description, features) vs the same query with `fuzziness: AUTO`. Output of `python eval/fuzzy_experiment.py 305 "toddler couch fold out"` on index `products_bm25_20261028`.

**What it shows:**
- Typo query "ligth bulb": fuzzy helps. Without it only "bulb" matches, and the list fills with holiday string lights. With it, "ligth" matches "light" and products from the Light Bulbs class come in.
- Synonym query "toddler couch fold out": fuzzy hurts. It cannot turn "couch" into "sofa". Instead it loosens every word and brings in unrelated products (a slow cooker, a bulletin board, a pillow insert).
- So fuzzy fixes typos, not synonyms. Synonyms need a dictionary (item 4) or vectors (item 5).
- The full-set effect is below, under "Full set (item 3)".


## Query 305: "ligth bulb"

### plain: strict 0.7, lenient 0.7, unlabelled 0.3

| rank | label | product | class |
|---|---|---|---|
| 1 | Exact | retrofit t50 led bulb | Holiday Lighting |
| 2 | Exact | light bulb | Holiday Lighting |
| 3 | - | 7 light bubble lights | Holiday Lighting |
| 4 | - | 48 ft led outdoor waterproof 15 string lights | Holiday Lighting |
| 5 | Exact | 7 light light bulbs | Holiday Lighting |
| 6 | Exact | incandescent mini vintage 25 light light bulb | Holiday Lighting |
| 7 | Exact | 5 light light bulb | Holiday Lighting |
| 8 | Exact | 100 light bulb | Holiday Lighting |
| 9 | Exact | 24 light bulb | Holiday Lighting |
| 10 | - | 5000 portable transmissive projector | Projectors |

### fuzzy AUTO: strict 0.8, lenient 0.8, unlabelled 0.2

| rank | label | product | class |
|---|---|---|---|
| 1 | Exact | 40 watt equivalent st19 dimmable light bulb 2700k e26/medium | Light Bulbs |
| 2 | Exact | retrofit t50 led bulb | Holiday Lighting |
| 3 | Exact | 60 watt equivalent a19 led dimmable clear glass filament lig | Light Bulbs |
| 4 | Exact | 60 watt equivalent b11 led dimmable led edison candle light  | Light Bulbs |
| 5 | Exact | light bulb | Holiday Lighting |
| 6 | - | 48 ft led outdoor waterproof 15 string lights | Holiday Lighting |
| 7 | - | 7 light bubble lights | Holiday Lighting |
| 8 | Exact | 6.5 watt ( 60 watt equivalent ) , a19 led dimmable light bul | Light Bulbs |
| 9 | Exact | 6 watt ( 60 watt equivalent ) , a15 led light bulb , warm wh | Light Bulbs |
| 10 | Exact | 5.5 watt ( 60 watt equivalent ) , ca10 led , dimmable light  | Light Bulbs |

## Query 42: "toddler couch fold out"

### plain: strict 0.0, lenient 0.6, unlabelled 0.4

| rank | label | product | class |
|---|---|---|---|
| 1 | Partial | kids sleeper | Soft Seating|Kids Chairs |
| 2 | - | kids foam chair | Kids Chairs|Soft Seating |
| 3 | - | reita fold-out console table | Sofa & Console Tables |
| 4 | Partial | waytrim indoor chaise lounge sofa , folding lazy sofa floor  | Indoor Chaise Lounges |
| 5 | Partial | duchess fold-out sleeper dog bolster | Dog Beds & Mats |
| 6 | Partial | bernartice oxygen fold out kids cotton sleeper | Kids Chairs |
| 7 | - | robidoux solid wood convertible toddler bed | Kids Beds |
| 8 | - | blair toddler bed | Kids Beds |
| 9 | Partial | haywood floor couch and sofa fabric folding chaise lounge | Indoor Chaise Lounges |
| 10 | Partial | elmo 2 in 1 flip open kids foam sofa | Licensed Products|Kids Chairs |

### fuzzy AUTO: strict 0.0, lenient 0.3, unlabelled 0.5

| rank | label | product | class |
|---|---|---|---|
| 1 | - | reita fold-out console table | Sofa & Console Tables |
| 2 | Partial | kids sleeper | Soft Seating|Kids Chairs |
| 3 | - | kids foam chair | Kids Chairs|Soft Seating |
| 4 | - | alwyn home full body pillow insert without cover , soft long | Standard Bed Pillows |
| 5 | Partial | duchess fold-out sleeper dog bolster | Dog Beds & Mats |
| 6 | Irrelevant | baby seat booster high chair -portable space saver high chai | None |
| 7 | - | kalorik 8 quart digital slow cooker with locking glass lid | Slow Cookers |
| 8 | Partial | czech toddler flip zebra kids sleeper | Kids Chairs |
| 9 | - | photo calendar bulletin board cut out | Classroom Decorations |
| 10 | Irrelevant | bauder twin or smaller 41.7 '' convertible sofa | Futons|Sofas |

### Full set (item 3)

Output of `python eval/compare.py bm25_plain bm25_fuzzy`:

```
bm25_fuzzy minus bm25_plain, 480 queries, paired bootstrap 10,000 resamples

          metric  bm25_plain  bm25_fuzzy    diff  ci_low  ci_high  excludes_0  better  worse  same
      p10_strict      0.3229      0.2977 -0.0252 -0.0365  -0.0140        True      48     95   337
     p10_lenient      0.6892      0.6381 -0.0510 -0.0675  -0.0354        True      84    169   227
unlabelled_share      0.2554      0.3090  0.0535  0.0379   0.0698        True     172     81   227
```

Fuzzy is reliably worse on the full set: it helps a few typo queries and loosens every other query.

## Item 4: BM25 plus linguistic patching (2026-10-28)

All resources come from product.csv only (leakage check: `eval/check_leakage.sh`).
Patches: synonyms (a word that lives mostly in one product class expands with that class's
name words), spell correction (term suggester, only for words the catalogue has never seen),
query rewriting (boost the product class a query word points at).

**Two bugs found by the eval, both fixed:**
1. Spell v1 checked product names only, so it "corrected" real words: "wishbone chair" lost 0.7 strict P@10 because wishbone only appears in descriptions. v2 checks all text fields.
2. The patch tokenizer kept letters only, so "e12", "7", "48" and "4.5" were dropped from queries ("7 draw white dresser" went from 0.6 to 0.0). v3 keeps digits and decimals.
The v1/v2 rows stay in runs.csv as the record of this.

**Final comparison (fixed code, `eval/compare.py` against bm25_plain, 480 queries):**

```
== bm25_syn_v3
          metric  bm25_plain  bm25_syn_v3    diff  ci_low  ci_high  excludes_0  better  worse  same
      p10_strict      0.3229       0.3125 -0.0104 -0.0188  -0.0025        True      24     49   407
     p10_lenient      0.6892       0.6812 -0.0079 -0.0198   0.0035       False      53     64   363
unlabelled_share      0.2554       0.2617  0.0062 -0.0038   0.0165       False      60     50   370
== bm25_spell_v3
          metric  bm25_plain  bm25_spell_v3    diff  ci_low  ci_high  excludes_0  better  worse  same
      p10_strict      0.3229         0.3246  0.0017 -0.0006   0.0058       False       2      2   476
     p10_lenient      0.6892         0.6871 -0.0021 -0.0071   0.0029       False       2      7   471
unlabelled_share      0.2554         0.2581  0.0027 -0.0025   0.0079       False       8      2   470
== bm25_rewrite_v3
          metric  bm25_plain  bm25_rewrite_v3    diff  ci_low  ci_high  excludes_0  better  worse  same
      p10_strict      0.3229           0.3208 -0.0021 -0.0112   0.0071       False      37     35   408
     p10_lenient      0.6892           0.7140  0.0248  0.0067   0.0425        True      97     43   340
unlabelled_share      0.2554           0.2354 -0.0200 -0.0358  -0.0035        True      46     85   349
== bm25_patched_v3
          metric  bm25_plain  bm25_patched_v3    diff  ci_low  ci_high  excludes_0  better  worse  same
      p10_strict      0.3229           0.3123 -0.0106 -0.0204  -0.0008        True      39     57   384
     p10_lenient      0.6892           0.6900  0.0008 -0.0188   0.0206       False      93     73   314
unlabelled_share      0.2554           0.2577  0.0023 -0.0152   0.0206       False      69     83   328
```

**Verdict:**
- Synonyms: reliably worse on strict (-0.0104). The product-only rules are too noisy ("made" -> "area rugs"). Rejected.
- Spell: a wash (only 4 queries change much; "ligth->light" helps, "pedistole->pistol" hurts). Tie goes to the simpler option. Rejected.
- Rewrite (class boosts): strict unchanged, lenient +0.0248 and unlabelled share -0.0200, both reliable. This is the patched baseline.
- The bar for vectors and hybrid: strict 0.3229 (bm25_plain), lenient 0.7140 (bm25_rewrite_v3).

## Item 5: vector search (2026-10-29)

Product text encoded: name, class, category path, description (in that order, cut at the model's input limit). Encoding ran on CPU after MPS stalled twice on this 8 GB machine (see PROGRESS.md). MPNet: 46.1 min. MiniLM: 7.7 min.

Bootstrap comparisons (`eval/compare.py`):

```
== mpnet_hnsw vs mpnet_exact
          metric  mpnet_hnsw  mpnet_exact    diff  ci_low  ci_high  excludes_0  better  worse  same
      p10_strict      0.3315       0.3333  0.0019 -0.0008   0.0046       False      17     11   452
     p10_lenient      0.7627       0.7640  0.0012 -0.0025   0.0054       False      27     25   428
unlabelled_share      0.2115       0.2073 -0.0042 -0.0096   0.0002       False      18     28   434
== mpnet_hnsw vs minilm_hnsw
          metric  mpnet_hnsw  minilm_hnsw    diff  ci_low  ci_high  excludes_0  better  worse  same
      p10_strict      0.3315       0.3475  0.0160  0.0035   0.0281        True     111     80   289
     p10_lenient      0.7627       0.7758  0.0131 -0.0037   0.0298       False     130     95   255
unlabelled_share      0.2115       0.1919 -0.0196 -0.0350  -0.0040        True      87    127   266
== bm25_plain vs minilm_hnsw
          metric  bm25_plain  minilm_hnsw    diff  ci_low  ci_high  excludes_0  better  worse  same
      p10_strict      0.3229       0.3475  0.0246  0.0073   0.0423        True     125     99   256
     p10_lenient      0.6892       0.7758  0.0867  0.0627   0.1119        True     213     88   179
unlabelled_share      0.2554       0.1919 -0.0635 -0.0881  -0.0388        True     103    191   186
```

Latency per query, eval client (includes CPU query encoding): mpnet_hnsw p50 63.5 ms / p99 354.2 ms; mpnet_exact p50 73.6 ms / p99 158.0 ms; minilm_hnsw p50 16.4 ms / p99 152.5 ms.

**What it shows:**
- HNSW loses nothing measurable against exact search at 43k products (every interval includes 0). At this corpus size exact is nearly as fast because query encoding dominates. HNSW is kept for scale.
- Vector search beats plain BM25 reliably on every metric (strict +0.0246, lenient +0.0867, unlabelled -0.0635 for MiniLM).
- MiniLM beats MPNet on strict P@10 (+0.0160, interval 0.0035 to 0.0281) and unlabelled share, with 4x faster query encoding and half the vector size. This contradicts the stack's encoder choice. Build paused for the user's decision, as the plan requires.

## Item 6: feature pooling (2026-10-29)

Each product lists its features as `key : value` strings (128,919 unique across the catalogue, median 55 per product). Each unique feature was encoded once with MiniLM (3.7 min on CPU, 582/s), then each product got three pooled vectors: the mean of its feature vectors, the element-wise max, and the top-3 centroid (mean of the 3 feature vectors closest to the product's own mean). One HNSW index each.

```
run        strict  lenient  unlabelled  p50 per query
pool_mean  0.0738  0.2515   0.7271      21.3 ms
pool_max   0.0469  0.1762   0.8094      29.7 ms
pool_top3  0.0525  0.2108   0.7615      23.6 ms
minilm_hnsw (whole text, for comparison)
           0.3475  0.7758   0.1919      16.4 ms
```

Bootstrap vs `minilm_hnsw`: every pooled variant is reliably worse on every metric. The best one (mean) loses 0.2737 strict P@10 (95% interval -0.3056 to -0.2421) and is worse on 291 of 480 queries. Full tables in `eval/compare.py` output, reproducible with `compare.py minilm_hnsw pool_mean` etc.

**What it shows:** a product is not the average of its features. Feature strings are fragments ("color : black", care instructions, package contents), so pooling them dilutes what the product is. The whole-text vector (name, class, category, description as one passage) keeps that. Unlabelled share around 0.75 also means pooled search mostly retrieves products no annotator ever saw for the query, so it is not even wrong in an interesting way. Mean pooling is the best of the three, max the worst (one feature's extreme value dominates each dimension).

## Item 7: hybrid ranking, RRF vs weighted blending (2026-10-29)

Both hybrids fuse the same two lists per query: the top 100 from patched BM25 (class-boost rewrite, the item 4 winner) and the top 100 from the MiniLM HNSW index. RRF uses k = 60. Blending min-max normalises each list's scores to 0..1 and mixes with vector weight w. `tests/test_rrf.py` checks both against hand-worked examples.

```
run           strict  lenient  unlabelled
hybrid_rrf60  0.3688  0.8069   0.1598
blend_w0.3    0.3492  0.7479   0.2092
blend_w0.5    0.3644  0.7850   0.1763
blend_w0.7    0.3642  0.7954   0.1710
minilm_hnsw   0.3475  0.7758   0.1919   (vector only)
bm25_rewrite_v3 0.3208 0.7140  0.2354   (keyword only)
```

Bootstrap (`eval/compare.py`):
- `hybrid_rrf60` vs `minilm_hnsw`: strict +0.0213 (0.0102 to 0.0325), lenient +0.0310, unlabelled -0.0321. All reliable. The hybrid beats its best single leg.
- `hybrid_rrf60` vs `bm25_rewrite_v3`: strict +0.0479, lenient +0.0929, unlabelled -0.0756. All reliable.
- `hybrid_rrf60` vs `blend_w0.5`: strict tie (interval includes 0), lenient +0.0219 and unlabelled -0.0165 reliable for RRF.
- `hybrid_rrf60` vs `blend_w0.7`: every interval includes 0. A tie.

**What it shows:** fusing keyword and vector results beats either alone, on every metric. RRF is at least as good as the best-tuned blend and needs no weight to tune: blending's result depends on w (0.3 is reliably worse), and the right w had to be found on the eval queries, which is exactly the kind of tuning that leaks. RRF with the paper's k = 60 matches it blind. The stack's choice stands. Latency: a hybrid query runs two top-100 searches; the p50 spread across the four runs (48 to 119 ms) is cache warm-up, not method cost.

## Item 8: fine-tuning on the category tree (2026-10-29)

Three runs, identical data and hyperparameters: LoRA rank 4, LoRA rank 16, full fine-tune. 30,000 product pairs sampled from the category tree (product.csv only), target similarity = shared path depth / deeper path depth, CosineSimilarityLoss, 1 epoch, batch 32, seed 0, 10% of products held out. Trained on a Colab T4 (the Mac killed the CPU run at 96%, see PROGRESS.md); all three times are on the same GPU, logged in MLflow and `results/perf.csv`. Pipeline details and two bugs the run surfaced (torchao version clash, adapter merge) are in PROGRESS.md.

```
run          strict  lenient  unlabelled   train eval_loss  size
minilm_hnsw  0.3475  0.7758   0.1919       (no tuning)
lora_r4      0.2738  0.6910   0.2867       6.8 min  0.0257  0.16 MB adapter
lora_r16     0.1727  0.5479   0.4204       6.8 min  0.0154  0.6 MB adapter
full_ft      0.1087  0.3542   0.6110       8.1 min  0.0035  91.9 MB model

hybrid (RRF k=60 with bm25_rewrite):
hybrid_rrf60    0.3688  0.8069  0.1598    (base MiniLM)
lora_r4_hybrid  0.3477  0.7769  0.1935
lora_r16_hybrid 0.3006  0.7175  0.2460
full_ft_hybrid  0.2517  0.6090  0.3469
```

Every tuned run is reliably worse than its untuned counterpart on every metric (all intervals exclude 0; lora_r4 strict -0.0737, interval -0.0929 to -0.0554; full_ft strict -0.2388). The order is monotone: more capacity to learn the objective, worse retrieval. The training eval loss improves in exactly the same order (0.0257 -> 0.0154 -> 0.0035). The models learned the objective; the objective was wrong for the task.

**The 20 queries that got worse most (lora_r4 vs minilm_hnsw) and the pattern.** The list: amarillo, hillsby oriental rug, delta trinsic, kisner, outdoor privacy wall, e12/candelabra, canadian, home sweet home sign, bistro table and chairs, bohemian, body pillow case, gold, welcome sign, industrial, leather dining chairs, canvas map art, camper, flamingo, ruckus chair, 30 inch bathroom vanity.

The pattern: the category-tree objective teaches "same category = same vector", so the only signal that survives is which category a product sits in. Every query whose signal is NOT a category loses:
- Brand and collection names (amarillo, hillsby, delta trinsic, kisner, ruckus): names do not follow the category tree, so their meaning is erased. For "delta trinsic" the base model's top 5 are all Trinsic-collection fixtures; lora_r4's top 5 are marble coasters.
- Style and theme words that cut across categories (bohemian, industrial, gold, flamingo, camper, canadian): pulling same-category products together collapses the cross-category style axis.
- Specs (e12/candelabra, 30 inch bathroom vanity): finer than the category level the objective rewards.

Unlabelled share doubling to quadrupling is the same story seen from the label side: the tuned models mostly retrieve products no annotator ever saw for the query.

**What it shows:** product-to-product similarity from a taxonomy is the wrong training signal for query-to-product retrieval. A useful fine-tune needs query-product pairs (which for WANDS would mean training on the eval labels, i.e. leakage, or collecting real click data). LoRA vs full fine-tuning: LoRA damaged less at equal epochs and its adapter is 575x smaller than the full model's delta, so if fine-tuning were worth doing, LoRA rank 4 is the form to do it in. Training time on one T4 was roughly equal (6.8 vs 8.1 min at this scale).

## Item 10: rebuilding the live index under load (2026-10-30)

Both scenarios rebuilt the full 42,994-product index from stored vectors while Locust drove /search at 6 requests per second for 300 s (hand-written queries, `loadtest/locustfile.py`; a request fails on non-200 or fewer than 10 results).

```
scenario                         requests  failures
in place (delete + recreate)     1634      30   (12 x http 500, 18 x empty results)
alias swap (rebuild_index.py)    1647      0
```

In place (`loadtest/rebuild_inplace.py`): deleting the index killed searches outright (500s) for a few seconds; once the empty index existed under the same name, searches "worked" again but returned nothing, then partial catalogues. The index was incomplete for 139 s; only the first ~10 s of that showed up as counted failures. The silent window is the worse half: responses look healthy and are quietly missing most of the catalogue.

Alias swap (`src/rebuild_index.py`): the new dated index is built and count-checked off to the side, then `products_live` moves in one atomic aliases call. Every request hit a complete index; zero failures; the old index stays as an instant rollback target.

**What it shows:** never rebuild the index clients are reading. Build beside, verify, swap atomically.
