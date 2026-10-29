# Progress

Claude reads this at the start of every session and appends an entry at the end. Newest at the bottom.

## Entry template

```
Date:
Built:
Not finished (carry over):
Numbers recorded: (run names in results/runs.csv)
Things that broke, and why:
Next session starts with:
```

---

<!-- Entries start below. -->

Date: 2026-10-28
Built: Project folder set up from the teaching copy. Copied the Elasticsearch compose file, BM25 indexing and search scripts, problem statement, exploration notebook, DECISIONS.md and the WANDS dataset.
Not finished (carry over): everything in "What is left to build" in CLAUDE.md, starting with item 1.
Numbers recorded: none.
Things that broke, and why: none.
Next session starts with: ask the user for the four setup steps in CLAUDE.md, then build item 1.

Date: 2026-10-28 (build loop)
Built: item 1 (gh 2.103.3 and kind 0.33.0 in ~/.local/bin, checksums checked; .venv; public repo SimardeepKaur/wands-semantic-search). Docker memory set to 6 GB. Item 2 (fuzzy experiment, eval/fuzzy_experiment.py, docs/experiments.md).
Things that broke, and why: the container name `es` was taken by a stopped container from the teaching copy. Renamed this project's container to `wands-es` and left the other one alone.
- Things that broke: the documented strict ceiling 0.599 was slightly high. It counted the 1,467 repeated label rows as separate products. With one label per query-product pair the ceilings are strict 0.5975, lenient 0.9858. Fixed in CLAUDE.md, PROBLEM.md, DECISIONS.md and PLAN.md.
