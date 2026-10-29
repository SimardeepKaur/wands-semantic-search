"""Encode every product into one vector and save it as .npy in data/vectors/.

Product text: name, class, category path, then description, in that order. The model
reads at most its sequence limit (384 word pieces for MPNet, 256 for MiniLM), so the
fields most likely to identify the product come first and a long description is cut,
not the name.

Vectors are unit-normalised, so cosine similarity is a dot product. The script checks
shape, NaN and norms before saving, and saves product ids next to the vectors.

Encodes in chunks of 2,000 and saves each chunk to data/vectors/parts/, so a killed
run resumes where it stopped. The merged .npy is written at the end.

Device: --device cpu or mps. On this 8 GB Mac, MPS stalled twice with the whole
system swapped out (see PROGRESS.md 2026-10-29), so cpu is the default.

Usage:
    python src/encode.py --model mpnet    # all-mpnet-base-v2 -> data/vectors/products_mpnet.npy
    python src/encode.py --model minilm   # all-MiniLM-L6-v2  -> data/vectors/products_minilm.npy
"""
import argparse
import time
from pathlib import Path

import numpy as np
import pandas as pd

CHUNK = 2000

ROOT = Path(__file__).resolve().parents[1]
PRODUCTS_CSV = ROOT / "data/WANDS/dataset/product.csv"
VECTORS_DIR = ROOT / "data/vectors"

MODELS = {
    "mpnet": "sentence-transformers/all-mpnet-base-v2",
    "minilm": "sentence-transformers/all-MiniLM-L6-v2",
    # fine-tuned MiniLM variants saved by src/train_lora.py
    "lora_r4": str(ROOT / "data/models/lora_r4_merged"),
    "lora_r16": str(ROOT / "data/models/lora_r16_merged"),
    "full_ft": str(ROOT / "data/models/full_ft_merged"),
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
    parser.add_argument("--batch-size", type=int, default=16)
    parser.add_argument("--device", choices=["cpu", "mps"], default="cpu")
    args = parser.parse_args()

    import torch
    from sentence_transformers import SentenceTransformer

    torch.set_num_threads(4)  # the M2's performance cores; leave the rest to the OS
    model = SentenceTransformer(MODELS[args.model], device=args.device)
    ids, texts = product_texts()
    parts_dir = VECTORS_DIR / "parts"
    parts_dir.mkdir(parents=True, exist_ok=True)
    print(f"{args.model} on {args.device}: {len(texts)} products, batch {args.batch_size}",
          flush=True)

    start = time.time()
    chunks = []
    for lo in range(0, len(texts), CHUNK):
        part = parts_dir / f"{args.model}_{lo:06d}.npy"
        if part.exists():
            chunks.append(np.load(part))
            continue
        vecs = model.encode(texts[lo:lo + CHUNK], batch_size=args.batch_size,
                            normalize_embeddings=True, show_progress_bar=False)
        np.save(part, vecs.astype(np.float32))
        chunks.append(vecs.astype(np.float32))
        done = min(lo + CHUNK, len(texts))
        rate = done / (time.time() - start)
        print(f"  {done}/{len(texts)} ({rate:.0f}/s, ~{(len(texts) - done) / rate / 60:.0f} min left)",
              flush=True)
    vectors = np.vstack(chunks)
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
