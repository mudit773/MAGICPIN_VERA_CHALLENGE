from __future__ import annotations
import json
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional, Tuple


class ContextStore:
    def __init__(self, dataset_dir: Optional[Path] = None):
        self._lock = threading.RLock()
        self._contexts: Dict[Tuple[str, str], Dict[str, Any]] = {}
        if dataset_dir:
            self.load_from_disk(dataset_dir)

    def push(
        self, scope: str, context_id: str, version: int, payload: Dict[str, Any]
    ) -> Tuple[bool, int, Dict[str, Any]]:
        valid_scopes = {"category", "merchant", "customer", "trigger"}
        if scope not in valid_scopes:
            return False, 400, {
                "accepted": False,
                "reason": "invalid_scope",
                "details": f"Scope '{scope}' is not one of {valid_scopes}",
            }

        key = (scope, context_id)
        now_iso = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

        with self._lock:
            cur = self._contexts.get(key)
            if cur:
                cur_ver = cur["version"]
                if cur_ver > version:
                    return False, 409, {
                        "accepted": False,
                        "reason": "stale_version",
                        "current_version": cur_ver,
                    }
                elif cur_ver == version:
                    return True, 200, {
                        "accepted": True,
                        "ack_id": f"ack_{context_id}_v{version}",
                        "stored_at": cur["stored_at"],
                    }

            self._contexts[key] = {
                "version": version,
                "payload": payload,
                "stored_at": now_iso,
            }
            return True, 200, {
                "accepted": True,
                "ack_id": f"ack_{context_id}_v{version}",
                "stored_at": now_iso,
            }

    def get(self, scope: str, context_id: str) -> Optional[Dict[str, Any]]:
        with self._lock:
            entry = self._contexts.get((scope, context_id))
            return entry["payload"] if entry else None

    def get_version(self, scope: str, context_id: str) -> Optional[int]:
        with self._lock:
            entry = self._contexts.get((scope, context_id))
            return entry["version"] if entry else None

    def get_counts(self) -> Dict[str, int]:
        counts = {"category": 0, "merchant": 0, "customer": 0, "trigger": 0}
        with self._lock:
            for (scope, _), _ in self._contexts.items():
                if scope in counts:
                    counts[scope] += 1
                else:
                    counts[scope] = 1
        return counts

    def get_merchant_with_category(self, merchant_id: str) -> Tuple[Optional[Dict[str, Any]], Optional[Dict[str, Any]]]:
        with self._lock:
            merchant = self.get("merchant", merchant_id)
            if not merchant:
                return None, None
            category_slug = merchant.get("category_slug", "")
            category = self.get("category", category_slug)
            return merchant, category

    def clear(self):
        with self._lock:
            self._contexts.clear()

    def load_from_disk(self, dataset_dir: Path):
        dataset_dir = Path(dataset_dir)
        with self._lock:
            cat_dir = dataset_dir / "categories"
            if cat_dir.exists():
                for f in cat_dir.glob("*.json"):
                    try:
                        data = json.loads(f.read_text(encoding="utf-8"))
                        slug = data.get("slug", f.stem)
                        self.push("category", slug, 1, data)
                    except Exception:
                        pass

            merchants_dir = dataset_dir / "merchants"
            if merchants_dir.exists():
                for f in merchants_dir.glob("*.json"):
                    try:
                        data = json.loads(f.read_text(encoding="utf-8"))
                        mid = data.get("merchant_id", f.stem)
                        self.push("merchant", mid, 1, data)
                    except Exception:
                        pass
            elif (dataset_dir / "merchants_seed.json").exists():
                try:
                    data = json.loads((dataset_dir / "merchants_seed.json").read_text(encoding="utf-8"))
                    items = data.get("merchants", [])
                    for item in items:
                        if "merchant_id" in item:
                            self.push("merchant", item["merchant_id"], 1, item)
                except Exception:
                    pass

            customers_dir = dataset_dir / "customers"
            if customers_dir.exists():
                for f in customers_dir.glob("*.json"):
                    try:
                        data = json.loads(f.read_text(encoding="utf-8"))
                        cid = data.get("customer_id", f.stem)
                        self.push("customer", cid, 1, data)
                    except Exception:
                        pass
            elif (dataset_dir / "customers_seed.json").exists():
                try:
                    data = json.loads((dataset_dir / "customers_seed.json").read_text(encoding="utf-8"))
                    items = data.get("customers", [])
                    for item in items:
                        if "customer_id" in item:
                            self.push("customer", item["customer_id"], 1, item)
                except Exception:
                    pass

            triggers_dir = dataset_dir / "triggers"
            if triggers_dir.exists():
                for f in triggers_dir.glob("*.json"):
                    try:
                        data = json.loads(f.read_text(encoding="utf-8"))
                        tid = data.get("id", f.stem)
                        self.push("trigger", tid, 1, data)
                    except Exception:
                        pass
            elif (dataset_dir / "triggers_seed.json").exists():
                try:
                    data = json.loads((dataset_dir / "triggers_seed.json").read_text(encoding="utf-8"))
                    items = data.get("triggers", [])
                    for item in items:
                        if "id" in item:
                            self.push("trigger", item["id"], 1, item)
                except Exception:
                    pass
