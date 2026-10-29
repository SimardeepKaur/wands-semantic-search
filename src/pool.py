"""Build per-product vectors by pooling feature vectors (item 6).

Each product lists features as a `|`-separated string ("key : value"). Every unique
feature string (128,919 of them) is encoded once with the chosen encoder (MiniLM),
then each product's vector is pooled from its own features' vectors:

    mean  - the average of the product's feature vectors.
    max   - the element-wise maximum.
    top3  - the mean of the 3 feature vectors closest (cosine) to the product's
            mean vector: its 3 most typical features.

All pooled vectors are unit-normalised, so cosine works the same as for the
whole-text vectors. Every product has at least one feature (checked: 0 without).

Feature encoding is chunked and resumable like src/encode.py: parts go to
data/vectors/parts/feat_minilm_<offset>.npy, keyed by position in the sorted
unique-feature list, so a killed run resumes. Run with Docker quit (8 GB Mac).

Outputs in data/vectors/:
    features_minilm.npy                       (128919, 384) one vector per unique feature
    products_pool_{mean,max,top3}.npy         (42994, 384)
    product_ids_pool_{mean,max,top3}.npy      copies of the same id order, one per
                                              pool so index_vectors.py finds them

Usage:
    python src/pool.py            # encode (resumes) then pool
    python src/pool.py --pool-only   # features already encoded
"""
import argparse
import time
from pathlib import Path

import numpy as np
import pandas as pd

CHUNK = 2000
MODEL = "sentence-transformers/all-MiniLM-L6-v2"
DIM = 384

ROOT = Path(__file__).resolve().parents[1]
PRODUCTS_CSV = ROOT / "data/WANDS/dataset/product.csv"
VECTORS_DIR = ROOT / "data/vectors"
PARTS_DIR = VECTORS_DIR / "parts"
FEATURES_NPY = VECTORS_DIR / "features_minilm.npy"


def product_features():
    """Per-product feature lists and the sorted unique feature strings."""
    p = pd.read_csv(PRODUCTS_CSV, sep="\t").fillna("")
    per_product = [[f.strip() for f in feats.split("|") if f.strip()]
                   for feats in p.product_features]
    unique = sorted({f for feats in per_product for f in feats})
    return p.product_id.to_numpy(), per_product, unique


def encode_features(unique, batch_size):
    import torch
    from sentence_transformers import SentenceTransformer

    torch.set_num_threads(4)
    model = SentenceTransformer(MODEL, device="cpu")
    PARTS_DIR.mkdir(parents=True, exist_ok=True)
    print(f"encoding {len(unique)} unique features on cpu, batch {batch_size}", flush=True)

    start = time.time()
    chunks = []
    for lo in range(0, len(unique), CHUNK):
        part = PARTS_DIR / f"feat_minilm_{lo:06d}.npy"
        if part.exists():
            chunks.append(np.load(part))
            continue
        vecs = model.encode(unique[lo:lo + CHUNK], batch_size=batch_size,
                            normalize_embeddings=True, show_progress_bar=False)
        np.save(part, vecs.astype(np.float32))
        chunks.append(vecs.astype(np.float32))
        done = min(lo + CHUNK, len(unique))
        rate = done / (time.time() - start)
        print(f"  {done}/{len(unique)} ({rate:.0f}/s, "
              f"~{(len(unique) - done) / rate / 60:.0f} min left)", flush=True)
    vectors = np.vstack(chunks).astype(np.float32)

    assert vectors.shape == (len(unique), DIM), vectors.shape
    assert not np.isnan(vectors).any(), "NaN in feature vectors"
    np.save(FEATURES_NPY, vectors)
    print(f"saved {vectors.shape} to {FEATURES_NPY.relative_to(ROOT)} "
          f"in {(time.time() - start) / 60:.1f} min", flush=True)
    return vectors


def normalise(m):
    norms = np.linalg.norm(m, axis=1, keepdims=True)
    return m / np.clip(norms, 1e-12, None)


def pool(ids, per_product, unique, feat_vecs):
    row = {f: i for i, f in enumerate(unique)}
    mean = np.empty((len(ids), DIM), dtype=np.float32)
    mx = np.empty((len(ids), DIM), dtype=np.float32)
    top3 = np.empty((len(ids), DIM), dtype=np.float32)

    for i, feats in enumerate(per_product):
        vecs = feat_vecs[[row[f] for f in feats]]
        m = vecs.mean(axis=0)
        mean[i] = m
        mx[i] = vecs.max(axis=0)
        # cosine to the mean = dot product, feature vectors are unit length
        nearest = np.argsort(vecs @ m)[-3:]
        top3[i] = vecs[nearest].mean(axis=0)

    for name, mat in [("mean", mean), ("max", mx), ("top3", top3)]:
        mat = normalise(mat)
        assert not np.isnan(mat).any(), f"NaN in pool_{name}"
        np.save(VECTORS_DIR / f"products_pool_{name}.npy", mat.astype(np.float32))
        np.save(VECTORS_DIR / f"product_ids_pool_{name}.npy", ids)
        print(f"saved products_pool_{name}.npy {mat.shape}", flush=True)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--batch-size", type=int, default=16)
    parser.add_argument("--pool-only", action="store_true",
                        help="skip encoding, load features_minilm.npy")
    args = parser.parse_args()

    ids, per_product, unique = product_features()
    if args.pool_only:
        feat_vecs = np.load(FEATURES_NPY)
        assert feat_vecs.shape == (len(unique), DIM), feat_vecs.shape
    else:
        feat_vecs = encode_features(unique, args.batch_size)
    pool(ids, per_product, unique, feat_vecs)


if __name__ == "__main__":
    main()
