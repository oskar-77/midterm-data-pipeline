"""منسق ELT المشترك بين محركي Python Batch وPySpark."""

from __future__ import annotations

from typing import Any
from quality_rules import clean_and_classify
from mongo_setup import insert_quarantine, upsert_validated
from metrics import count_errors

# نعالج كل raw document بعد إدخاله، لذلك لا يمكن للتنظيف أن يمنع وصول السجل إلى Raw.
def process_raw_document(raw_document: dict[str, Any], db, metrics: dict[str, Any], run_id: str) -> None:
    result = clean_and_classify(raw_document["raw_record"])
    result["run_id"] = run_id
    if result["quality_status"] == "quarantined":
        insert_quarantine(db["orders_quarantine"], result)
        metrics["quarantine_count"] += 1
        count_errors(metrics, result["error_codes"])
        return
    result["run_id"] = run_id
    outcome = upsert_validated(db["orders_validated"], result)
    metrics[f"{outcome}_count"] += 1
    if result["quality_status"] == "valid":
        metrics["valid_count"] += 1
    else:
        metrics["corrected_count"] += 1

# نعالج دفعة واحدة مع إبقاء الاستدعاء منفصلًا ليسهل اختبار منطق ELT.
def process_raw_batch(raw_documents: list[dict[str, Any]], db, metrics: dict[str, Any], run_id: str) -> None:
    for raw_document in raw_documents:
        process_raw_document(raw_document, db, metrics, run_id)
