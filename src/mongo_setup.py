"""كل ما يتعلق بإنشاء اتصال MongoDB والمجموعات والفهارس."""

from __future__ import annotations

from typing import Any
from pymongo import MongoClient, ASCENDING, UpdateOne
from pymongo.errors import OperationFailure

from config.settings import MONGO_DATABASE, MONGO_URI, RAW_COLLECTION, VALIDATED_COLLECTION, QUARANTINE_COLLECTION

# ننشئ العميل مرة واحدة لكل تشغيل ونترك الإغلاق للطبقة المستدعية عبر finally.
def create_client() -> MongoClient:
    return MongoClient(MONGO_URI, serverSelectionTimeoutMS=3000)

# نجهز المجموعات: Raw بلا Validator، والنهائية بفهرس أعمال فريد كما تنص الوثيقة.
def setup_database(client: MongoClient):
    db = client[MONGO_DATABASE]
    for collection in (RAW_COLLECTION, VALIDATED_COLLECTION, QUARANTINE_COLLECTION):
        if collection not in db.list_collection_names():
            db.create_collection(collection)
    validated = db[VALIDATED_COLLECTION]
    validated.create_index([("order_id", ASCENDING)], unique=True, name="uniq_business_order_id")
    db[QUARANTINE_COLLECTION].create_index([("run_id", ASCENDING)])
    db[RAW_COLLECTION].create_index([("run_id", ASCENDING)])
    return db

# نستخدم update_one مع upsert بدل check-then-insert لضمان Idempotency ذري على order_id.
def upsert_validated(collection, document: dict[str, Any]) -> str:
    order_id = document["record"]["order_id"]
    payload = {**document["record"], "quality_status": document["quality_status"], "corrections": document.get("corrections", []), "last_run_id": document["run_id"]}
    result = collection.update_one({"order_id": order_id}, {"$set": payload, "$setOnInsert": {"first_run_id": document["run_id"]}}, upsert=True)
    if result.upserted_id is not None:
        return "inserted"
    if result.modified_count:
        return "updated"
    return "unchanged"

# نوثق السجل المعزول كاملًا مع رموز الأخطاء والتفاصيل والسجل الخام.
def insert_quarantine(collection, document: dict[str, Any]) -> None:
    collection.insert_one({"run_id": document["run_id"], "quality_status": "quarantined", "error_codes": document["error_codes"], "error_details": document["error_details"], "raw_record": document["raw_record"], "record_after_attempt": document["record"], "corrections": document.get("corrections", [])})

# نتحقق اختياريًا من توفر MongoDB برسالة واضحة قبل بدء معالجة طويلة.
def ping(client: MongoClient) -> None:
    client.admin.command("ping")
