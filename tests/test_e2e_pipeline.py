"""اختبار تكاملي سريع يحاكي MongoDB لإثبات مسار ELT وIdempotency."""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import mongomock
from elt_pipeline import process_raw_batch
from metrics import new_metrics

# نثبت أن Raw يُكتب أولًا، ثم ينتقل كل سجل إلى نتيجة نهائية واحدة.
def test_elt_and_upsert_are_idempotent():
    client = mongomock.MongoClient()
    db = client["test_db"]
    db.create_collection("orders_raw")
    db.create_collection("orders_validated")
    db.create_collection("orders_quarantine")
    db.orders_validated.create_index("order_id", unique=True)
    raw = [{"run_id": "run-1", "source_file": "sample.csv", "source_row_number": 1, "raw_record": {"order_id": "O-1", "customer_id": "C-1", "order_date": "2025-01-01", "items": "[{\"sku\":\"A\"}]", "unit_price": "10", "quantity": "1"}}, {"run_id": "run-1", "source_file": "sample.csv", "source_row_number": 2, "raw_record": {"order_id": "O-2", "customer_id": "C-2", "order_date": "31/02/2025", "items": "[]"}}]
    db.orders_raw.insert_many(raw)
    metrics = new_metrics(run_id="run-1", file_name="sample.csv", engine_used="python_batch")
    metrics["raw_loaded"] = 2
    process_raw_batch(raw, db, metrics, "run-1")
    assert db.orders_validated.count_documents({}) == 1
    assert db.orders_quarantine.count_documents({}) == 1
    process_raw_batch(raw[:1], db, metrics, "run-1")
    assert db.orders_validated.count_documents({}) == 1
