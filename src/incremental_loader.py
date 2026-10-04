"""المسار المتقدم B: تحميل Delta موثوق وقابل لإعادة التشغيل."""

from __future__ import annotations

import csv
from datetime import datetime
from pathlib import Path
from typing import Any

# نحول updated_at إلى قيمة قابلة للمقارنة؛ النسخة الأحدث فقط تستبدل الأقدم.
def version_value(value: Any) -> datetime:
    return datetime.fromisoformat(str(value).replace("Z", "+00:00"))

# نقرأ Delta Streaming ثم نطبق Upsert مشروطًا بإصدار أحدث، ولذلك لا نعيد أثر Delta نفسها.
def apply_delta(delta_path: Path, validated_collection, run_id: str) -> dict[str, int]:
    counts = {"inserted_count": 0, "updated_count": 0, "unchanged_count": 0}
    with delta_path.open("r", encoding="utf-8-sig", newline="") as handle:
        for row in csv.DictReader(handle):
            order_id = row.get("order_id")
            if not order_id:
                continue
            current = validated_collection.find_one({"order_id": order_id}, {"updated_at": 1})
            if current and current.get("updated_at") and row.get("updated_at"):
                if version_value(row["updated_at"]) <= version_value(current["updated_at"]):
                    counts["unchanged_count"] += 1
                    continue
            result = validated_collection.update_one({"order_id": order_id}, {"$set": {**row, "last_run_id": run_id}}, upsert=True)
            if result.upserted_id:
                counts["inserted_count"] += 1
            elif result.modified_count:
                counts["updated_count"] += 1
            else:
                counts["unchanged_count"] += 1
    return counts
