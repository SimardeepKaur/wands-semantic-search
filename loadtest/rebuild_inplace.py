"""The deliberately broken alternative for item 10: rebuild the live index IN
PLACE, under one name, while traffic runs.

It deletes the index products_live points at, recreates it under the same name
with the alias attached from birth, and bulk-loads all 42,994 products back.
Searches during the delete-to-create gap get index-missing errors; searches
during the fill see a half-full index and come back short. The experiment
counts both through Locust. Never use this on a real system: that is the
point. The fixed version is src/rebuild_index.py.

Usage:
    python loadtest/rebuild_inplace.py --model minilm
"""
import argparse
import sys
import time
from pathlib import Path

from elasticsearch import Elasticsearch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from index_vectors import DIMS, build_index  # noqa: E402
from search import ALIAS, ES_URL  # noqa: E402


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", choices=DIMS, default="minilm")
    args = parser.parse_args()
    es = Elasticsearch(ES_URL, request_timeout=120)

    targets = list(es.indices.get_alias(name=ALIAS).keys())
    assert len(targets) == 1, targets
    name = targets[0]
    print(f"rebuilding {name} in place (the alias dies with the delete)")

    start = time.time()
    es.indices.delete(index=name)
    # recreate under the same name with the alias attached from the first moment,
    # as an alias-free system would effectively behave (clients query the name)
    build_index(es, args.model, index=name, recreate=False, aliases=[ALIAS])
    print(f"in-place rebuild took {time.time() - start:.0f}s")


if __name__ == "__main__":
    main()
