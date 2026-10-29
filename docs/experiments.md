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
