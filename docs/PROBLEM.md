# Problem statement

Written before any search code, the way a team would write it before a project starts. Every number here comes from the WANDS files in `data/WANDS/dataset/`, computed on 2026-10-27.

## 1. User and task

A shopper types a short query (3.4 words on average, 480 queries) into a furniture and home goods store. The system shows 10 products out of a catalogue of 42,994. The shopper wants the thing they asked for, with the details they asked for.

## 2. What "good" means

Each query is split into:

- **The thing** (target entity): the type of product wanted.
- **The details** (modifiers): brand, colour, material, size, style.

Human annotators labelled (query, product) pairs with one of three labels:

| Label | Rule | Share of all labels |
|---|---|---|
| Exact | Right thing, every detail met | 11.0% |
| Partial | Right thing, at least one detail missed | 62.8% |
| Irrelevant | Wrong thing | 26.2% |

Worked example, query 49 "moen matte black hooks". Thing: hooks. Details: brand Moen, finish matte black.

- 0 Exact. No labelled product is a Moen matte black hook.
- 116 Partial. Almost all are towel and robe hooks that are not Moen or not matte black.
- 19 Irrelevant. Towel bars, tub spouts, a black rug: they share words with the query but are not hooks.

## 3. Metric

**Precision@10:** of the 10 products shown, the fraction that are relevant. We compute it two ways, which differ only in what counts as relevant.

- **Strict:** only Exact counts. Asks "did we show what the shopper asked for?"
- **Lenient:** Exact and Partial both count. Asks "did we at least show the right kind of product?"
- **Unlabelled share:** fraction of the 10 that have no label for that query. Counted as not relevant in both scores.

### Best possible scores (ceilings)

If a system put every Exact product first, then every Partial, it would score:

| Metric | Ceiling |
|---|---|
| Strict P@10 | 0.5975 |
| Lenient P@10 | 0.9858 |

These come from run `oracle` in `results/runs.csv`. An earlier version of this file said 0.599 for strict: that figure counted repeated label rows as separate products.

Strict is capped because 101 queries have 0 Exact labels and 136 have between 1 and 9. Only 243 queries have 10 or more.

### Recommendation

Headline metric: strict P@10. Lenient P@10 is reported next to it as a check that results are at least in the right category. Unlabelled share is a warning light: when it rises, the scores are less trustworthy.

Reason: lenient is near its ceiling for any system that finds the right category, so it will barely move between methods (expected, not yet measured). Strict measures whether details like brand and colour are respected, which is where keyword and vector search differ.

Rejected alternative: nDCG@10 with graded credit (for example Exact 1, Partial 0.5). It rewards ranking order and partial credit in one number, but the credit weights are a judgement call, and the plan fixes P@10.

**My decision:**

## 4. Baseline

**The baseline is BM25 plus linguistic patching.** This is where most large retailers' keyword search sits, so beating it is the claim that matters. Plain BM25 is kept as a floor, not as the baseline.

| Piece | What it does | Example |
|---|---|---|
| Stemming | Reduces words to a root | "beds" -> "bed" |
| Synonym dictionary | Expands a query word to words with the same meaning | "kitty" -> "cat", "couch" -> "sofa" |
| Spell correction | Fixes misspelled query words against the catalogue's vocabulary | "blak" -> "black" |
| Query rewriting | Rule-based clean-up and intent detection before search | "w/" -> "with"; "dresser" detected as a product class and boosted |

Rule for building it: synonyms, spelling vocabulary and rewrite rules come from the catalogue only, never from the 480 eval queries or their labels. Otherwise the baseline has seen the exam.

## 5. Known limits

- **Labels are incomplete.** A median of 216 labelled products per query, out of 42,994. A good product with no label counts as a miss. For query 49, 15 of the 120 towel and robe hooks in the catalogue have no label.
- **Some labels are repeated.** 1,467 query-product pairs appear more than once in `label.csv`, and 14 of them disagree (for example Exact and Partial). The eval keeps one label per pair: majority vote, a tie goes to the better label.
- **This biases against new methods.** The labelled products were the ones some earlier search systems returned. A new method (for example vector search) may find good products nobody labelled, and its score will be too low. Check unlabelled share on every run before trusting a drop.
- **Some labels look wrong.** Product 26575 "align wall mounted robe hook" may be a Moen product (Align is a Moen line in this catalogue) but is labelled Partial. We do not fix labels; we note them.

## 6. Out of scope

Personalisation, product images, click or purchase data (WANDS has none), and ranking by price or popularity.

## 7. Constraints (not measured yet)

- Latency budget (p50, p99): filled in on Day 5.
- Cost and hardware: filled in on Day 6.

## 8. Open ideas (not agreed, not in the plan)

- **LLM-as-judge labels** for products in our top 10 that have no human label. Would need: an agreement check against existing human labels first, LLM labels kept in a separate file from human labels, and a new eval version (all old runs re-scored) if the labels change. Proposed 2026-10-27, decide after Day 2 once we see real unlabelled shares.
