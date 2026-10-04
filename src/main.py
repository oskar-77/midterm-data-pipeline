"""نقطة التشغيل الوحيدة للمشروع؛ تكتشف الملف وتختار المحرك ثم تنفذ ELT."""

from __future__ import annotations

import argparse
import time
import uuid
from pathlib import Path
import sys

# نضيف src وconfig إلى المسار عند التشغيل المباشر من README.
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT))

from config import settings
from batch_loader import load_batches
from elt_pipeline import process_raw_batch
from metrics import finalize_metrics, new_metrics, write_results
from mongo_setup import create_client, ping, setup_database
from file_router import choose_engine

# نحلل وسائط التشغيل دون توزيع نقطة الدخول بين برنامجين منفصلين.
def parse_args():
    parser = argparse.ArgumentParser(description="Hybrid ELT pipeline for dirty order CSV")
    parser.add_argument("--input", type=Path, default=settings.INPUT_FILE)
    parser.add_argument("--force-engine", choices=["python_batch", "pyspark"], default=None)
    parser.add_argument("--batch-size", type=int, default=settings.BATCH_SIZE)
    parser.add_argument("--dry-run", action="store_true", help="تشغيل Router والتحقق من الملف دون MongoDB")
    return parser.parse_args()

# ننفذ التشغيل كاملًا مع finally لإغلاق MongoDB حتى عند حدوث خطأ.
def run(args) -> dict:
    path = args.input.resolve()
    if not path.exists():
        raise FileNotFoundError(f"ملف الإدخال غير موجود: {path}")
    engine, reason, size_mb = choose_engine(path, settings.SMALL_FILE_THRESHOLD_MB, args.force_engine)
    run_id = uuid.uuid4().hex
    print(f"[Router] file={path.name} size_mb={size_mb:.3f} engine={engine} reason={reason} run_id={run_id}")
    metrics = new_metrics(run_id=run_id, file_name=path.name, file_size_mb=size_mb, engine_used=engine, batch_size=args.batch_size, partitions=settings.SPARK_PARTITIONS)
    if args.dry_run:
        metrics["dry_run"] = True
        write_results(metrics, settings.RESULTS_FILE)
        return metrics
    client = create_client()
    started = time.perf_counter()
    try:
        ping(client)
        db = setup_database(client)
        if engine == "python_batch":
            def process(batch):
                process_raw_batch(batch, db, metrics, run_id)
            stats = load_batches(path, args.batch_size, db[settings.RAW_COLLECTION], run_id, engine, process)
            metrics.update({"rows_read": stats["rows_read"], "raw_loaded": stats["raw_loaded"], "batch_timings": stats["batch_timings"], "batches": stats["batches"]})
        else:
            from spark_loader import run_spark_loader
            stats = run_spark_loader(path, settings, db[settings.RAW_COLLECTION], run_id)
            metrics.update(stats)
            # Spark يضمن Raw بالتوازي؛ نطبق قواعد الجودة بعد اكتمال Raw من MongoDB.
            for raw in db[settings.RAW_COLLECTION].find({"run_id": run_id}):
                process_raw_batch([raw], db, metrics, run_id)
        finalize_metrics(metrics, time.perf_counter() - started)
        write_results(metrics, settings.RESULTS_FILE)
        print(f"[Complete] consistency={metrics['consistency_check']} throughput={metrics['throughput']}")
        return metrics
    finally:
        client.close()

# نحول الاستثناء إلى رسالة تشغيل مفهومة ونحافظ على exit code غير صفري للفشل.
def main():
    try:
        run(parse_args())
    except Exception as exc:
        print(f"[ERROR] {exc}", file=sys.stderr)
        raise SystemExit(1) from exc

if __name__ == "__main__":
    main()
