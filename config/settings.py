"""إعدادات خط البيانات؛ تحفظ القيم التشغيلية خارج منطق التحميل والتنظيف."""

from pathlib import Path
import os

# نحدد جذر المشروع اعتمادًا على موقع هذا الملف حتى يعمل الأمر من أي مجلد.
PROJECT_ROOT = Path(__file__).resolve().parents[1]

# نضع الملفات الافتراضية داخل مجلد data، مع السماح بتغييرها عبر متغيرات البيئة.
DEFAULT_INPUT = PROJECT_ROOT / "data" / "orders_huge_mixed_quality.csv"
INPUT_FILE = Path(os.getenv("INPUT_FILE", str(DEFAULT_INPUT)))

# الحد المطلوب في وثيقة التكليف: ما دونه Python Batch وما فوقه PySpark.
SMALL_FILE_THRESHOLD_MB = float(os.getenv("SMALL_FILE_THRESHOLD_MB", "200"))

# حجم الدفعة قابل للضبط دون تعديل الكود.
BATCH_SIZE = int(os.getenv("BATCH_SIZE", "1000"))

# إعدادات MongoDB قابلة للتغيير حسب بيئة العرض أو الجهاز المحلي.
MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017")
MONGO_DATABASE = os.getenv("MONGO_DATABASE", "midterm_data_pipeline")

# إعدادات Spark، ويُستخدم spark://... عند تنفيذ مسار العنقود.
SPARK_MASTER = os.getenv("SPARK_MASTER", "local[*]")
SPARK_APP_NAME = os.getenv("SPARK_APP_NAME", "MidtermHybridOrderPipeline")
SPARK_PARTITIONS = int(os.getenv("SPARK_PARTITIONS", "8"))

# أسماء المجموعات ثابتة لتطابق متطلبات الوثيقة.
RAW_COLLECTION = "orders_raw"
VALIDATED_COLLECTION = "orders_validated"
QUARANTINE_COLLECTION = "orders_quarantine"

# نستخدم updated_at لاختيار أحدث نسخة عند تشغيل مسار Incremental B.
INCREMENTAL_KEY = os.getenv("INCREMENTAL_KEY", "updated_at")
RESULTS_FILE = PROJECT_ROOT / "reports" / "results.json"
