"""
Generate submission.jsonl from test_pairs.json as specified in challenge-brief.md §7.2.
Produces exactly 30 lines corresponding to the 30 canonical challenge test pairs.
"""

from __future__ import annotations
import json
from pathlib import Path
from composer import compose

BASE_DIR = Path(__file__).resolve().parent
DATASET_DIR = BASE_DIR / "dataset" / "expanded"
OUTPUT_FILE = BASE_DIR / "submission.jsonl"


def generate_submission():
    print("Loading test pairs and dataset...")
    test_pairs_path = DATASET_DIR / "test_pairs.json"
    if not test_pairs_path.exists():
        raise FileNotFoundError(f"Missing {test_pairs_path}. Run generate_dataset.py first.")

    with open(test_pairs_path, encoding="utf-8") as f:
        test_pairs = json.load(f)["pairs"]

    # Preload categories
    categories = {}
    for f in (DATASET_DIR / "categories").glob("*.json"):
        cat = json.loads(f.read_text(encoding="utf-8"))
        categories[cat["slug"]] = cat

    # Preload merchants
    merchants = {}
    for f in (DATASET_DIR / "merchants").glob("*.json"):
        m = json.loads(f.read_text(encoding="utf-8"))
        merchants[m["merchant_id"]] = m

    # Preload customers
    customers = {}
    for f in (DATASET_DIR / "customers").glob("*.json"):
        c = json.loads(f.read_text(encoding="utf-8"))
        customers[c["customer_id"]] = c

    # Preload triggers
    triggers = {}
    for f in (DATASET_DIR / "triggers").glob("*.json"):
        t = json.loads(f.read_text(encoding="utf-8"))
        triggers[t["id"]] = t

    print(f"Generating compositions for {len(test_pairs)} test pairs...")
    lines = []
    for pair in test_pairs:
        test_id = pair["test_id"]
        tid = pair["trigger_id"]
        mid = pair["merchant_id"]
        cid = pair.get("customer_id")

        trg = triggers.get(tid)
        m = merchants.get(mid)
        cust = customers.get(cid) if cid else None

        if not trg or not m:
            print(f"Warning: missing trigger or merchant for {test_id} (tid={tid}, mid={mid})")
            continue

        cat_slug = m.get("category_slug", "generic")
        cat = categories.get(cat_slug, {"slug": cat_slug})

        res = compose(cat, m, trg, cust)

        entry = {
            "test_id": test_id,
            "body": res["body"],
            "cta": res["cta"],
            "send_as": res["send_as"],
            "suppression_key": res["suppression_key"],
            "rationale": res["rationale"],
        }
        lines.append(json.dumps(entry, ensure_ascii=False))

    OUTPUT_FILE.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"Successfully generated {len(lines)} lines in {OUTPUT_FILE}")


if __name__ == "__main__":
    generate_submission()
