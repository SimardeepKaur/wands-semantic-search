"""Log the Colab training runs into local MLflow from their metrics.json files.

The three item 8 runs trained on a Colab GPU (see notebooks/02_finetune_colab.ipynb
and PROGRESS.md 2026-10-29). Each saved model carries a metrics.json; this script
copies those numbers into mlruns/ so MLflow holds every training run. Safe to
rerun: it skips a run name that is already logged.

Usage:
    python src/log_colab_runs.py
"""
import json
import os
from pathlib import Path

# The stack keeps MLflow on the local mlruns/ folder; MLflow 3.x asks for this
# flag before it will write to a file store.
os.environ.setdefault("MLFLOW_ALLOW_FILE_STORE", "true")
import mlflow  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
NAMES = ["lora_r4", "lora_r16", "full_ft"]
METRIC_KEYS = ["train_loss", "eval_loss", "train_minutes", "saved_mb", "adapter_mb"]


def main():
    mlflow.set_tracking_uri(f"file://{ROOT / 'mlruns'}")
    exp = mlflow.set_experiment("wands-finetune")
    have = {r.info.run_name
            for r in mlflow.search_runs([exp.experiment_id], output_format="list")}

    for name in NAMES:
        if name in have:
            print(f"{name}: already logged, skipped")
            continue
        metrics = json.loads((ROOT / f"data/models/{name}_merged/metrics.json").read_text())
        with mlflow.start_run(run_name=name):
            mlflow.log_params({k: v for k, v in metrics.items() if k not in METRIC_KEYS})
            mlflow.log_metrics({k: metrics[k] for k in METRIC_KEYS if metrics[k] is not None})
        print(f"{name}: logged ({metrics['train_minutes']:.1f} min, "
              f"eval loss {metrics['eval_loss']:.4f})")


if __name__ == "__main__":
    main()
