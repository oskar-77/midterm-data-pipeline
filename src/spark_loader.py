"""محرك الملفات الكبيرة باستخدام PySpark وSchema ثابت."""

from __future__ import annotations

import time
from pathlib import Path
from typing import Any

# نضع الاستيراد داخل الدالة حتى تعمل اختبارات Python حتى لو لم تُثبت Spark بعد.
def run_spark_loader(path: Path, settings, raw_collection=None, run_id: str | None = None) -> dict[str, Any]:
    try:
        from pyspark.sql import SparkSession
        from pyspark.sql.types import StringType, StructField, StructType
    except ImportError as exc:
        raise RuntimeError("محرك PySpark مطلوب لمسار الملف الكبير: pip install -r requirements.txt") from exc

    # نستخدم StringType للحقول الحساسة حتى لا نفقد القيم غير النظيفة في طبقة Raw.
    schema = StructType([StructField("order_id", StringType(), True), StructField("customer_id", StringType(), True), StructField("customer_email", StringType(), True), StructField("customer_phone", StringType(), True), StructField("order_date", StringType(), True), StructField("items", StringType(), True), StructField("unit_price", StringType(), True), StructField("quantity", StringType(), True), StructField("shipping_cost", StringType(), True), StructField("total", StringType(), True), StructField("status", StringType(), True), StructField("updated_at", StringType(), True)])
    started = time.perf_counter()
    spark = SparkSession.builder.appName(settings.SPARK_APP_NAME).master(settings.SPARK_MASTER).getOrCreate()
    try:
        # القراءة تتم عبر Spark DataFrame API لا عبر Pandas، وبـSchema ثابت لا inferSchema.
        frame = spark.read.option("header", True).option("mode", "PERMISSIVE").schema(schema).csv(str(path))
        input_partitions = frame.rdd.getNumPartitions()
        rows = frame.count()
        print(f"[PySpark] input_partitions={input_partitions} rows={rows} master={settings.SPARK_MASTER}")
        if raw_collection is not None and run_id:
            # الكتابة هنا موزعة على partitions؛ لا نستخدم repartition بلا تبرير.
            def write_partition(iterator):
                from pymongo import MongoClient
                client = MongoClient(settings.MONGO_URI)
                collection = client[settings.MONGO_DATABASE][settings.RAW_COLLECTION]
                docs = []
                for index, row in enumerate(iterator):
                    docs.append({"run_id": run_id, "source_file": str(path), "source_row_number": index, "ingested_at": time.time(), "engine_used": "pyspark", "raw_record": row.asDict(recursive=True)})
                if docs:
                    collection.insert_many(docs, ordered=False)
                client.close()
            frame.rdd.mapPartitions(write_partition).count()
        elapsed = time.perf_counter() - started
        return {"rows_read": rows, "raw_loaded": rows, "partitions": input_partitions, "elapsed_seconds": elapsed, "throughput": rows / elapsed if elapsed else 0.0, "explain": frame._jdf.queryExecution().simpleString()}
    finally:
        # الإغلاق المنظم إلزامي حتى لا تبقى SparkContext بعد انتهاء التشغيل.
        spark.stop()
