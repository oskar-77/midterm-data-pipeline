"""تشغيل تجريبي محلي باستخدام mongomock دون الحاجة إلى خادم MongoDB."""
from __future__ import annotations

import json
import sys
import time
import uuid
from pathlib import Path

import mongomock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT))

from batch_loader import load_batches
from elt_pipeline import process_raw_batch
from metrics import finalize_metrics, new_metrics
from mongo_setup import insert_quarantine, upsert_validated


def main() -> None:
    input_path = ROOT / "data" / "demo_orders.csv"
    report_path = ROOT / "reports" / "demo_run_results.json"
    client = mongomock.MongoClient()
    db = client["midterm_data_pipeline_demo"]
    db.create_collection("orders_raw")
    db.create_collection("orders_validated")
    db.create_collection("orders_quarantine")
    db.orders_validated.create_index("order_id", unique=True)
    db.orders_quarantine.create_index("run_id")
    db.orders_raw.create_index("run_id")

    run_id = "demo-" + uuid.uuid4().hex[:12]
    metrics = new_metrics(
        run_id=run_id,
        file_name=input_path.name,
        engine_used="python_batch",
        batch_size=3,
        partitions=None,
    )
    started = time.perf_counter()

    def process(batch):
        process_raw_batch(batch, db, metrics, run_id)

    stats = load_batches(input_path, 3, db["orders_raw"], run_id, "python_batch", process)
    metrics.update(stats)
    finalize_metrics(metrics, time.perf_counter() - started)
    metrics["demo_database"] = "mongomock"
    metrics["collections"] = {
        "orders_raw": db.orders_raw.count_documents({}),
        "orders_validated": db.orders_validated.count_documents({}),
        "orders_quarantine": db.orders_quarantine.count_documents({}),
    }
    metrics["quarantine_codes"] = sorted({
        code
        for doc in db.orders_quarantine.find({}, {"error_codes": 1})
        for code in doc.get("error_codes", [])
    })
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(metrics, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    print(json.dumps(metrics, ensure_ascii=False, indent=2, default=str))


if __name__ == "__main__":
    main()
