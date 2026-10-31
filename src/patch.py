"""BM25 plus linguistic patching: synonyms, spell correction, query rewriting with class boosts.

Every resource here is built from product.csv only. Nothing reads the eval queries or
labels (the leakage check in eval/check_leakage.sh enforces that for all of src/).

How each patch works:
- Synonyms: a word that lives mostly in one product class (at least 55% of the products
  whose name contains it) is expanded with that class's name words. So "sectional" adds
  "sofas", "hammock" adds "hammocks swings". Share and counts come from product names.
- Spell correction: a query word that never appears in any product name is sent to
  Elasticsearch's term suggester over product_name, and the best suggestion replaces it.
- Rewriting with class boosts: when a query word points at a product class (same 55% rule),
  the query gets a boost for products of that class. At most two classes per query.
- Per-word fuzzy fallback: a query word the catalogue has never seen (the same trigger as
  spell correction) is matched with fuzziness AUTO; every other word stays exact. A query
  with no such word runs exactly the query it ran before.
"""
import json
import re
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PRODUCTS_CSV = ROOT / "data/WANDS/dataset/product.csv"
RESOURCES = ROOT / "data/patch/resources.json"

FIELDS = ["product_name", "product_description", "product_features"]
STOP = {"the", "a", "an", "and", "or", "with", "for", "of", "in", "on", "to", "s"}
MIN_DF = 15          # a word must be in at least this many product names to get a rule
MIN_SHARE = 0.55     # and at least this share of them must sit in one class


def words(text):
    """Lowercase tokens, keeping digits and decimals: "E12/Candelabra 4.5" -> e12, candelabra, 4.5.

    v2 kept letters only, which silently dropped "e12", "7", "48" and "4.5" from
    queries before search. That alone cost strict P@10 on queries with sizes in them.
    """
    return re.findall(r"[a-z0-9]+(?:\.[0-9]+)?", text.lower())


def build_resources(force=False):
    """Word document frequencies, synonym expansions and class boosts, from product.csv."""
    if RESOURCES.exists() and not force:
        return json.loads(RESOURCES.read_text())
    import pandas as pd
    p = pd.read_csv(PRODUCTS_CSV, sep="\t").fillna("")
    df = Counter()
    by_class = defaultdict(Counter)
    for name, classes in zip(p.product_name, p.product_class):
        seen = set(words(name))
        class_list = [c for c in classes.split("|") if c]
        for w in seen:
            df[w] += 1
            for c in class_list:
                by_class[w][c] += 1
    # Spell correction must only touch words the catalogue has never seen anywhere.
    # v1 checked product names only and "corrected" real words like "wishbone" (it is
    # in descriptions, not names), which cost 0.7 strict P@10 on that query.
    vocab = set(df)
    for col in ("product_description", "product_features", "product_class",
                "category hierarchy"):
        for text in p[col]:
            vocab.update(words(text))
    synonyms, boosts = {}, {}
    for w, n in df.items():
        if n < MIN_DF or len(w) < 3 or not by_class[w]:
            continue  # too rare, or only in products with no class
        top_class, top_n = by_class[w].most_common(1)[0]
        if top_n / n < MIN_SHARE:
            continue
        boosts[w] = top_class
        expansion = [t for t in words(top_class)
                     if t not in STOP and t[:4] != w[:4]]
        if expansion:
            synonyms[w] = " ".join(dict.fromkeys(expansion))
    out = {"df": dict(df), "vocab": sorted(vocab), "synonyms": synonyms, "boosts": boosts}
    RESOURCES.parent.mkdir(parents=True, exist_ok=True)
    RESOURCES.write_text(json.dumps(out))
    return out


def unseen(res, w):
    """True for a query word the catalogue has never seen. Words under 3 letters never count."""
    if not isinstance(res["vocab"], set):
        res["vocab"] = set(res["vocab"])
    return w not in res["vocab"] and len(w) >= 3


def correct(es, res, query_words):
    """Replace words the catalogue has never seen with the term suggester's best guess."""
    out = []
    for w in query_words:
        if not unseen(res, w):
            out.append(w)
            continue
        resp = es.search(index="products_live", size=0, suggest={
            "fix": {"text": w, "term": {"field": "product_name", "suggest_mode": "missing",
                                        "max_edits": 2}}})
        options = resp["suggest"]["fix"][0]["options"]
        out.append(options[0]["text"] if options else w)
    return out


def bm25_patched(es, query, k=10, synonyms=True, spell=True, rewrite=True, resources=None,
                 es_filter=None, fuzzy_unseen=False):
    """Top k product dicts for a query, with the chosen patches applied.

    es_filter: optional Elasticsearch filter clause (scores unchanged), for
    example {"term": {"product_class.raw": "Sofas"}}.
    """
    res = resources or build_resources()
    qw = words(query)
    if spell:
        qw = correct(es, res, qw)
    fuzzy_words = [w for w in qw if unseen(res, w)] if fuzzy_unseen else []
    if fuzzy_words:
        exact = [w for w in qw if w not in fuzzy_words]
        clauses = [{"multi_match": {"query": w, "fields": FIELDS, "fuzziness": "AUTO"}}
                   for w in fuzzy_words]
        if exact:
            clauses.insert(0, {"multi_match": {"query": " ".join(exact), "fields": FIELDS}})
        must = {"bool": {"should": clauses, "minimum_should_match": 1}}
    else:
        must = {"multi_match": {"query": " ".join(qw), "fields": FIELDS}}
    should = []
    if synonyms:
        expansion = " ".join(dict.fromkeys(
            t for w in qw for t in res["synonyms"].get(w, "").split() if t))
        if expansion:
            should.append({"multi_match": {"query": expansion, "fields": FIELDS,
                                           "boost": 0.5}})
    if rewrite:
        classes = list(dict.fromkeys(res["boosts"][w] for w in qw if w in res["boosts"]))[:2]
        for c in classes:
            should.append({"match": {"product_class": {"query": c, "boost": 1.0}}})
    bool_q = {"must": [must], "should": should}
    if es_filter:
        bool_q["filter"] = [es_filter]
    from search import TIEBREAK_SORT
    resp = es.search(index="products_live", size=k, sort=TIEBREAK_SORT,
                     query={"bool": bool_q},
                     source=["product_id", "product_name", "product_class"])
    return [
        {"product_id": int(h["_id"]), "score": h["_score"],
         "product_name": h["_source"]["product_name"],
         "product_class": h["_source"].get("product_class")}
        for h in resp["hits"]["hits"]
    ]
