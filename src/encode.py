"""Encode every product into one vector and save it as .npy in data/vectors/.

Product text: name, class, category path, then description, in that order. The model
reads at most its sequence limit (384 word pieces for MPNet, 256 for MiniLM), so the
fields most likely to identify the product come first and a long description is cut,
not the name.

Vectors are unit-normalised, so cosine similarity is a dot product. The script checks
shape, NaN and norms before saving, and saves product ids next to the vectors.

Runs on the Mac's GPU (MPS) when available. Stop Elasticsearch first: 8 GB of RAM
does not fit both.

Usage:
    python src/encode.py --model mpnet    # all-mpnet-base-v2 -> data/vectors/products_mpnet.npy
    python src/encode.py --model minilm   # all-MiniLM-L6-v2  -> data/vectors/products_minilm.npy
"""
import argparse
import time
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
PRODUCTS_CSV = ROOT / "data/WANDS/dataset/product.csv"
VECTORS_DIR = ROOT / "data/vectors"

MODELS = {
    "mpnet": "sentence-transformers/all-mpnet-base-v2",
    "minilm": "sentence-transformers/all-MiniLM-L6-v2",
}


def product_texts():
    p = pd.read_csv(PRODUCTS_CSV, sep="\t").fillna("")
    p = p.rename(columns={"category hierarchy": "category_hierarchy"})
    texts = (p.product_name + ". " + p.product_class.str.replace("|", ", ", regex=False)
             + ". " + p.category_hierarchy.str.replace("/", ", ", regex=False)
             + ". " + p.product_description)
    return p.product_id.to_numpy(), texts.tolist()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", choices=MODELS, required=True)
    parser.add_argument("--batch-size", type=int, default=64)
    args = parser.parse_args()

    import torch
    from sentence_transformers import SentenceTransformer

    device = "mps" if torch.backends.mps.is_available() else "cpu"
    model = SentenceTransformer(MODELS[args.model], device=device)
    ids, texts = product_texts()
    print(f"{args.model} on {device}: {len(texts)} products, batch {args.batch_size}")

    start = time.time()
    vectors = model.encode(texts, batch_size=args.batch_size, normalize_embeddings=True,
                           show_progress_bar=False)
    took = time.time() - start

    assert vectors.shape[0] == len(ids), vectors.shape
    assert not np.isnan(vectors).any(), "NaN in vectors"
    norms = np.linalg.norm(vectors, axis=1)
    assert np.abs(norms - 1).max() < 1e-3, "vectors are not unit length"

    VECTORS_DIR.mkdir(parents=True, exist_ok=True)
    np.save(VECTORS_DIR / f"products_{args.model}.npy", vectors.astype(np.float32))
    np.save(VECTORS_DIR / f"product_ids_{args.model}.npy", ids)
    print(f"saved {vectors.shape} to data/vectors/products_{args.model}.npy "
          f"in {took / 60:.1f} min ({len(texts) / took:.0f} products/s)")


if __name__ == "__main__":
    main()
