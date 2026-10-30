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
- Item 3 done: eval/run_eval.py (refuses to log on a dirty tree, above a ceiling or on fewer than 480 queries), eval/compare.py (paired bootstrap). Runs: oracle, bm25_plain, bm25_fuzzy.
- Things that broke: PRs 1 and 2 were squash-merged, so commit 210bbd3 (logged for oracle, bm25_plain, bm25_fuzzy) is only in PR 2's history, not on main. From item 4 on, PRs use merge commits.
- Item 4 done: patched BM25. Only class-boost rewriting survives (lenient +0.0248, strict unchanged); synonyms and spell rejected by the numbers. Bar for vectors: strict 0.3229, lenient 0.7140.
- Things that broke: (1) spell v1 corrected real words because its vocabulary was names-only; (2) the patch tokenizer dropped digits from queries (e12, 48, 4.5). Both caught by per-query diffs, both fixed; v1/v2 runs kept in runs.csv.
- Things that broke: first encoding attempt thrashed. Docker Desktop's 6 GB VM stayed resident after `docker compose stop`, so the MPNet encoder was swapped out (3 MB resident, 12 GB swap used, 52 minutes with no progress). Fix: quit Docker Desktop itself before encoding, restart it after. Memory rule updated in PLAN.md.
- Things that broke (again): MPS encoding stalled a second time with Docker fully quit; the whole system was swapped out, the encoder at 0.2% CPU. Verdict: MPS plus 8 GB plus the apps that are open does not fit. Switched encode.py to CPU (4 threads, batch 16) with resumable 2,000-product chunks.
- Item 5 done. Vectors beat BM25 (minilm_hnsw strict 0.3475 vs 0.3229). HNSW = exact quality. MiniLM beats MPNet reliably (+0.0160 strict), which contradicts the stack's encoder choice: build paused for the user, per the plan's stop rule. Items 6-8 depend on the answer.
- 2026-10-29: User decided the encoder: switch the stack to all-MiniLM-L6-v2 (it measured better than MPNet, strict P@10 0.3475 vs 0.3315). Recorded in DECISIONS.md and CLAUDE.md. Loop restarted at item 6.
- 2026-10-29: Indexing script failed on first try: I ran index_vectors.py from inside src/, but it opens data/vectors/ relative to the repo root. Reran from the root.
- 2026-10-29: LoRA smoke test crashed: the trainer moved batches to MPS despite use_cpu=True, so model and data sat on different devices. Fixed by hiding MPS from torch inside train_lora.py.
- 2026-10-29: The local training job was killed by the OS at 96% of the first LoRA run (memory pressure: Chrome with Colab open plus training exceeded 8 GB, no checkpoint saved). Moved all three training runs to one Colab GPU notebook; that also puts all three training times on the same hardware.
- 2026-10-29: LoRA save step crashed on Colab: sentence-transformers add_adapter injects adapters into the transformer, which has no merge_and_unload. Switched to peft get_peft_model, which wraps the model and supports both adapter saving and merging. Same latent bug fixed in src/train_lora.py (its smoke test skipped saving).
- 2026-10-30: Item 8 verdict: all three fine-tunes (LoRA r4/r16, full) made retrieval reliably worse, in proportion to capacity. Decision recorded: no fine-tuning; base MiniLM stays.
- 2026-10-30: The API consistency test caught tie reordering: products with equal scores come back in index-internal order, so moving the alias to a different physical index reordered deep ranks and swapped near-ties in the fused top 10. Logic unchanged; re-ran the hybrid eval against the serving state as hybrid_rrf60_served and the test compares to that. Also fixed eval building index names from today's date, which broke the day after indexing.
- 2026-10-30: Even two back-to-back identical searches returned tied products in different orders (Elasticsearch searches index segments in parallel and interleaves equal scores arbitrarily). Added an explicit tie-break sort (score, then product id) to every search, logged hybrid_rrf60_det as the canonical deterministic serving run.
- 2026-10-30: Item 9 done: FastAPI service with demo page, JSON logs, class filter. products_live now points at the MiniLM index. Canonical serving run hybrid_rrf60_det (strict 0.3677).
- 2026-10-30: The item 10 experiment script died between scenarios: Locust exits nonzero when any request failed, and the script treated that as a crash. Scenario A's failures were the measurement. Handled the exit code and reran scenario B.
- 2026-10-30: Deleted the stale experiment indexes (mpnet, pool_*, lora_*, full_ft, old bm25); all reproducible from scripts and stored vectors. Live: products_minilm_20261030, rollback: products_minilm_20261029.
- 2026-10-30: After the item 10 rebuild, the API consistency test failed against the stored eval run: HNSW graph building is random, so a rebuilt index returns a slightly different approximate top 100 even from identical vectors. The test now compares the API to the eval code path run live on the current index; stored per-query files are exact only for the index build they were measured on.
- 2026-10-30: Item 14 done. The eval gate went red on the deliberate regression (PR 16, strict 0.3219 vs floor 0.3638) and green on real code. HF_TOKEN secret added by the user; Space deploy comes in item 17.
- 2026-10-30: Item 15 done: kind cluster with Elasticsearch, Redis and 3 API replicas; load tested at 6 and 50 users; kill-replica experiment logged (70 of 536 requests failed at 1 replica, 0 of 836 at 3).
- Things that broke: (1) `kind load docker-image` with several images at once hit a containerd-store bug ("content digest not found"); the local API image loads alone and the node pulls the public ES and Redis images itself. (2) The ES manifest had copied `node.store.allow_mmap: false` from the Space image; without mmap, searches ran seconds-slow. kind's VM allows mmap, so the line is gone. (3) The API connected to Redis once at startup; in Kubernetes, Redis came up 24 minutes later (image pull), so every pod silently ran cacheless. The cache is now connected lazily and a failed connection is retried every 30 s. (4) The first reindex raced the Recreate strategy: `kubectl wait` matched the dying old ES pod, so the port-forward reached a terminating container; reran against the new pod.
