"""محرك الملفات الصغيرة: CSV Streaming ودفعات MongoDB."""

from __future__ import annotations

import csv
import time
from pathlib import Path
from typing import Any, Callable

# نقرأ الملف سطرًا بسطر ونرسل كل دفعة مباشرة إلى callback حتى لا تتراكم البيانات في الذاكرة.
def stream_batches(path: Path, batch_size: int):
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        batch: list[dict[str, Any]] = []
        row_number = 1
        for raw in reader:
            raw["_source_row_number"] = row_number
            batch.append(raw)
            row_number += 1
            if len(batch) == batch_size:
                yield batch
                batch = []
        if batch:
            yield batch

# ننفذ الإدخال الخام باستخدام insert_many؛ أي فشل في دفعة يرفع رسالة واضحة ولا يخفي السبب.
def load_batches(path: Path, batch_size: int, raw_collection, run_id: str, engine: str, process_batch: Callable[[list[dict[str, Any]]], None] | None = None) -> dict[str, Any]:
    stats = {"rows_read": 0, "raw_loaded": 0, "batches": 0, "batch_timings": []}
    for batch_number, batch in enumerate(stream_batches(path, batch_size), start=1):
        started = time.perf_counter()
        raw_documents = [{"run_id": run_id, "source_file": str(path), "source_row_number": row.pop("_source_row_number"), "ingested_at": time.time(), "engine_used": engine, "raw_record": dict(row)} for row in batch]
        try:
            raw_collection.insert_many(raw_documents, ordered=False)
        except Exception as exc:
            raise RuntimeError(f"فشل إدخال الدفعة رقم {batch_number}: {exc}") from exc
        if process_batch:
            process_batch(raw_documents)
        elapsed = time.perf_counter() - started
        stats["rows_read"] += len(batch)
        stats["raw_loaded"] += len(raw_documents)
        stats["batches"] += 1
        stats["batch_timings"].append({"batch_number": batch_number, "rows": len(batch), "elapsed_seconds": round(elapsed, 6), "throughput": round(len(batch) / elapsed, 3) if elapsed else 0.0})
        print(f"[Python Batch] الدفعة={batch_number} السجلات={len(batch)} الزمن={elapsed:.4f}s المعدل={len(batch)/elapsed:.2f}/s")
    return stats
