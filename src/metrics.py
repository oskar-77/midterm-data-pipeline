"""تجميع وكتابة قياسات التشغيل بصورة قابلة للمراجعة."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

# ننشئ عدادات موحدة لجميع المحركات حتى يمكن مقارنة Python وSpark.
def new_metrics(**kwargs: Any) -> dict[str, Any]:
    return {"run_id": kwargs.get("run_id"), "file_name": kwargs.get("file_name"), "file_size_mb": kwargs.get("file_size_mb", 0.0), "engine_used": kwargs.get("engine_used"), "rows_read": 0, "raw_loaded": 0, "valid_count": 0, "corrected_count": 0, "quarantine_count": 0, "elapsed_seconds": 0.0, "throughput": 0.0, "batch_size": kwargs.get("batch_size"), "partitions": kwargs.get("partitions"), "error_case_counts": {}, "inserted_count": 0, "updated_count": 0, "unchanged_count": 0, "consistency_check": False}

# نضيف رموز أخطاء العزل إلى عدادها لتفسير أسباب الفشل بدل الاكتفاء بعدد عام.
def count_errors(metrics: dict[str, Any], codes: list[str]) -> None:
    for code in codes:
        metrics["error_case_counts"][code] = metrics["error_case_counts"].get(code, 0) + 1

# نتحقق من معادلة الوثيقة: كل raw ينتهي إلى Valid أو Corrected أو Quarantine.
def finalize_metrics(metrics: dict[str, Any], elapsed: float) -> dict[str, Any]:
    metrics["elapsed_seconds"] = round(elapsed, 6)
    metrics["throughput"] = round(metrics["rows_read"] / elapsed, 3) if elapsed > 0 else 0.0
    metrics["consistency_check"] = metrics["raw_loaded"] == metrics["valid_count"] + metrics["corrected_count"] + metrics["quarantine_count"]
    return metrics

# نحفظ سجل التشغيل الأخير وقائمة التاريخ السابق حتى تبقى النتائج قابلة للتتبع.
def write_results(metrics: dict[str, Any], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    history = []
    if path.exists():
        try:
            previous = json.loads(path.read_text(encoding="utf-8"))
            history = previous.get("runs", []) if isinstance(previous, dict) else []
        except json.JSONDecodeError:
            history = []
    history.append(metrics)
    path.write_text(json.dumps({"latest": metrics, "runs": history}, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
