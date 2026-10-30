"""Export WANDS labels for the demo page overlay.

The serving code never reads the eval files (the leakage check enforces that).
The demo page still wants to mark results Exact / Partial / unlabelled when the
typed query is one of the 480 WANDS queries. This script, which lives on the
eval side where reading the label data is allowed, writes a display-only export
to data/demo_labels.json: {query text: {product_id: label}}. Labels are
deduplicated the same way the scorer does it (majority vote, tie to the better
label). The API loads the JSON if it exists and only uses it to colour badges,
never to rank.

Usage:
    python eval/export_demo_labels.py
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "eval"))

from run_eval import load_labels, load_queries

OUT = ROOT / "data/demo_labels.json"


def main():
    queries = load_queries()
    labels = load_labels()
    export = {}
    for qid, text in zip(queries.query_id, queries["query"]):
        lab = labels.get(int(qid), {})
        export[text.strip().lower()] = {str(pid): label for pid, label in lab.items()}
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(export))
    print(f"wrote {OUT.relative_to(ROOT)}: {len(export)} queries, "
          f"{sum(len(v) for v in export.values())} labels")


if __name__ == "__main__":
    main()
