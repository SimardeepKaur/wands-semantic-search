---
title: WANDS Semantic Search
emoji: 🛋️
colorFrom: indigo
colorTo: gray
sdk: docker
app_port: 7860
pinned: false
---

# WANDS semantic search

A production-style hybrid product search built end to end on Wayfair's public
WANDS dataset: BM25 and MiniLM vectors in Elasticsearch, fused with hand-written
Reciprocal Rank Fusion, behind a FastAPI service with a Redis cache.

Type one of the 480 WANDS evaluation queries (try "smart coffee table") to see
each result's human relevance label next to the ranking. Every number and
design choice is measured and logged in the main repository:
https://github.com/SimardeepKaur/wands-semantic-search

This Space wakes from sleep by rebuilding its search index from baked vectors,
which takes a few minutes; after that, searches are fast.
