"""Fine-tune the encoder on product pairs from the category tree (item 8).

No query or label data is used. Training pairs are pairs of products, and the
target similarity is how much of their category paths they share:

    target = shared path depth / max(depth a, depth b)

"Sofas / Living Room / Furniture" vs another product under the same full path
gets 1.0; same root only gets a low score; different roots get 0. The loss is
CosineSimilarityLoss, so the model is pulled to give category-close products
cosine-close vectors using only their text (the same text src/encode.py indexes).

Products are split 90/10 by id hash first. Training pairs come only from the
90%, the eval pairs only from the 10%, so the eval loss is on unseen products.
Pairs are sampled with seed 0 in three strata: same full path, same root
(partial overlap), different roots.

Modes:
    --mode lora --rank 4|16   LoRA adapters (peft) on query and value matrices.
                              Adapter saved to data/models/<name>_adapter,
                              merged model to data/models/<name>_merged.
    --mode full               full fine-tune, saved to data/models/full_ft_merged.

Everything is logged to MLflow in mlruns/ (params, final losses, time, size).
Run with Docker quit: training and Elasticsearch do not fit in 8 GB together.

Usage:
    python src/train_lora.py --mode lora --rank 4
    python src/train_lora.py --mode full
    python src/train_lora.py --mode lora --rank 4 --smoke   # 500 pairs, no save
"""
import argparse
import hashlib
import random
import time
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
PRODUCTS_CSV = ROOT / "data/WANDS/dataset/product.csv"
MODELS_DIR = ROOT / "data/models"
BASE_MODEL = "sentence-transformers/all-MiniLM-L6-v2"
SEED = 0

N_SAME_PATH = 15000
N_SAME_ROOT = 15000
N_CROSS = 15000
N_EVAL = 3000


def product_rows():
    p = pd.read_csv(PRODUCTS_CSV, sep="\t").fillna("")
    p = p.rename(columns={"category hierarchy": "category_hierarchy"})
    text = (p.product_name + ". " + p.product_class.str.replace("|", ", ", regex=False)
            + ". " + p.category_hierarchy.str.replace("/", ", ", regex=False)
            + ". " + p.product_description)
    path = [tuple(s.strip() for s in h.split("/") if s.strip())
            for h in p.category_hierarchy]
    return list(p.product_id), text.tolist(), path


def similarity(a, b):
    """Shared category depth over the deeper path's depth."""
    if not a or not b:
        return 0.0
    shared = 0
    for x, y in zip(a, b):
        if x != y:
            break
        shared += 1
    return shared / max(len(a), len(b))


def holdout(pid):
    """Stable 90/10 split by product id."""
    return int(hashlib.md5(str(pid).encode()).hexdigest(), 16) % 10 == 0


def sample_pairs(idx, texts, paths, n_same_path, n_same_root, n_cross, rng):
    """Pairs within one side of the split. idx: positions usable here."""
    by_path, by_root = {}, {}
    for i in idx:
        if paths[i]:
            by_path.setdefault(paths[i], []).append(i)
            by_root.setdefault(paths[i][0], []).append(i)
    multi_path = [g for g in by_path.values() if len(g) > 1]
    multi_root = [g for g in by_root.values() if len(g) > 1]

    pairs = []
    for _ in range(n_same_path):
        g = rng.choice(multi_path)
        a, b = rng.sample(g, 2)
        pairs.append((a, b))
    for _ in range(n_same_root):
        g = rng.choice(multi_root)
        a, b = rng.sample(g, 2)
        pairs.append((a, b))
    for _ in range(n_cross):
        a, b = rng.sample(idx, 2)
        pairs.append((a, b))

    return {
        "sentence1": [texts[a] for a, _ in pairs],
        "sentence2": [texts[b] for _, b in pairs],
        "score": [similarity(paths[a], paths[b]) for a, b in pairs],
    }


def dir_size_mb(path):
    return sum(f.stat().st_size for f in Path(path).rglob("*") if f.is_file()) / 1e6


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=["lora", "full"], required=True)
    parser.add_argument("--rank", type=int, default=4)
    parser.add_argument("--epochs", type=int, default=1)
    parser.add_argument("--batch-size", type=int, default=32)
    parser.add_argument("--smoke", action="store_true", help="500 pairs, no save, no MLflow")
    args = parser.parse_args()
    name = f"lora_r{args.rank}" if args.mode == "lora" else "full_ft"

    import mlflow
    import torch
    from datasets import Dataset
    from sentence_transformers import (SentenceTransformer, SentenceTransformerTrainer,
                                       SentenceTransformerTrainingArguments)
    from sentence_transformers.losses import CosineSimilarityLoss

    torch.set_num_threads(4)
    torch.manual_seed(SEED)
    rng = random.Random(SEED)

    ids, texts, paths = product_rows()
    train_idx = [i for i, pid in enumerate(ids) if not holdout(pid)]
    eval_idx = [i for i, pid in enumerate(ids) if holdout(pid)]
    scale = 0.01 if args.smoke else 1.0
    train_data = sample_pairs(train_idx, texts, paths,
                              int(N_SAME_PATH * scale), int(N_SAME_ROOT * scale),
                              int(N_CROSS * scale), rng)
    k = max(int(N_EVAL * scale) // 3, 10)
    eval_data = sample_pairs(eval_idx, texts, paths, k, k, k, rng)
    print(f"{name}: {len(train_data['score'])} train pairs "
          f"({len(train_idx)} products), {len(eval_data['score'])} eval pairs "
          f"({len(eval_idx)} held-out products)", flush=True)

    model = SentenceTransformer(BASE_MODEL, device="cpu")
    if args.mode == "lora":
        from peft import LoraConfig, TaskType
        model.add_adapter(LoraConfig(task_type=TaskType.FEATURE_EXTRACTION,
                                     r=args.rank, lora_alpha=2 * args.rank,
                                     lora_dropout=0.1,
                                     target_modules=["query", "value"]))

    out = MODELS_DIR / f"{name}_trainer"
    train_args = SentenceTransformerTrainingArguments(
        output_dir=str(out), num_train_epochs=args.epochs,
        per_device_train_batch_size=args.batch_size,
        per_device_eval_batch_size=args.batch_size,
        eval_strategy="no", save_strategy="no", logging_steps=100,
        seed=SEED, use_cpu=True, report_to=[],
    )
    trainer = SentenceTransformerTrainer(
        model=model, args=train_args,
        train_dataset=Dataset.from_dict(train_data),
        eval_dataset=Dataset.from_dict(eval_data),
        loss=CosineSimilarityLoss(model),
    )

    start = time.time()
    result = trainer.train()
    minutes = (time.time() - start) / 60
    eval_loss = trainer.evaluate()["eval_loss"]
    print(f"{name}: trained in {minutes:.1f} min, "
          f"train loss {result.training_loss:.4f}, eval loss {eval_loss:.4f}", flush=True)

    if args.smoke:
        print("smoke run, nothing saved")
        return

    MODELS_DIR.mkdir(parents=True, exist_ok=True)
    adapter_mb = None
    if args.mode == "lora":
        adapter_dir = MODELS_DIR / f"{name}_adapter"
        model[0].auto_model.save_pretrained(adapter_dir)  # adapter weights only
        adapter_mb = dir_size_mb(adapter_dir)
        model[0].auto_model = model[0].auto_model.merge_and_unload()
    merged_dir = MODELS_DIR / f"{name}_merged"
    model.save(str(merged_dir))
    merged_mb = dir_size_mb(merged_dir)

    mlflow.set_tracking_uri(f"file://{ROOT / 'mlruns'}")
    mlflow.set_experiment("wands-finetune")
    with mlflow.start_run(run_name=name):
        mlflow.log_params({"mode": args.mode, "rank": args.rank if args.mode == "lora" else None,
                           "base_model": BASE_MODEL, "epochs": args.epochs,
                           "batch_size": args.batch_size, "seed": SEED,
                           "train_pairs": len(train_data["score"]),
                           "eval_pairs": len(eval_data["score"]),
                           "loss": "CosineSimilarityLoss",
                           "pair_source": "category tree, product.csv only"})
        mlflow.log_metrics({"train_loss": result.training_loss, "eval_loss": eval_loss,
                            "train_minutes": minutes, "saved_mb": merged_mb,
                            **({"adapter_mb": adapter_mb} if adapter_mb else {})})
    print(f"saved {merged_dir.relative_to(ROOT)} ({merged_mb:.0f} MB"
          + (f", adapter {adapter_mb:.1f} MB" if adapter_mb else "") + ")", flush=True)


if __name__ == "__main__":
    main()
