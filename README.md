# مشروع منتصف الفصل: Hybrid Order Data Pipeline

## بيانات الطالب

| البيان | المعلومات |
|---|---|
| عمل الطالب | عبدالرزاق محمد الصرابي |
| التخصص | ذكاء اصطناعي |
| السنة الدراسية | السنة الرابعة |
| المشرف | م. عمار أبو سند |

هذا المشروع ينفذ خط بيانات هجينًا لمعالجة ملف طلبات CSV غير نظيف وفق وثيقة التكليف الرسمية. يبدأ التنفيذ باكتشاف الملف وقياس حجمه، ثم يختار تلقائيًا **Python Batch** للملف الصغير و**PySpark** للملف الكبير. بعد ذلك يطبق نمط **ELT**: يصل كل سجل إلى `orders_raw` أولًا دون تنظيف، ثم يُصنف إلى `orders_validated` أو `orders_quarantine` مع أثر تصحيح واضح أو سبب عزل مفصل.

> المبدأ التشغيلي: لا يجوز إسقاط أي سجل سيئ أثناء التحميل الأولي؛ كل سجل خام يجب أن ينتهي إلى Valid/Corrected أو Quarantine.

## المتطلبات

يحتاج التشغيل إلى Python 3.10 أو أحدث، MongoDB محلي أو بعيد، وJava 8/11/17 عند تشغيل PySpark. ثبّت مكتبات Python بالأمر التالي:

```bash
cd midterm-data-pipeline
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

ثم شغّل MongoDB، أو اضبط `MONGO_URI` إلى عنوان الخادم. جميع الإعدادات المهمة موجودة في `config/settings.py` ويمكن تغييرها بمتغيرات البيئة.

## التشغيل الأساسي

ضع الملف المقدم في `data/orders_huge_mixed_quality.csv`، أو مرر مسارًا صريحًا. لإنشاء عينة قابلة لإعادة الإنتاج دون Excel:

```bash
python src/create_small_sample.py --input data/orders_huge_mixed_quality.csv --output data/orders_sample.csv --rows 100000
```

لتشغيل العينة واختبار مسار Python Batch:

```bash
python src/main.py --input data/orders_sample.csv --batch-size 1000
```

لتشغيل الملف الكبير، يجب أن يكون حجمه أكبر من `SMALL_FILE_THRESHOLD_MB=200`، وعندها يختار Router مسار PySpark تلقائيًا. ويمكن اختبار المسار صراحة أثناء العرض:

```bash
SPARK_MASTER='local[*]' python src/main.py --input data/orders_sample.csv --force-engine pyspark
```

أما مسار Spark Standalone المتقدم فيُشغّل بإعداد `SPARK_MASTER='spark://MASTER_IP:7077'` بعد تشغيل Master وWorker وتوحيد الإصدارات بين العقد.

## مسار B التقدمي

يستخدم `src/incremental_loader.py` ملف Delta يحوي `order_id` و`updated_at`. تُقبل النسخة الجديدة فقط إذا كان إصدارها أحدث من النسخة الموجودة؛ وإعادة تشغيل نفس Delta تنتج `unchanged_count` دون تكرار أو إعادة تطبيق تحديث قديم. مثال الاستخدام البرمجي موثق داخل الوحدة، ويمكن استدعاؤه من جلسة MongoDB بعد تنفيذ Initial Load.

## المجموعات والاتساق

| المجموعة | الوظيفة | الفهرس أو القاعدة |
|---|---|---|
| `orders_raw` | نسخة المصدر كما وصلت مع `run_id` و`source_file` و`source_row_number` | لا Validator ولا Unique Index لمنع فقدان المحاولات |
| `orders_validated` | السجلات السليمة والمصححة | Unique Index على `order_id` وUpsert |
| `orders_quarantine` | السجلات غير القابلة للتصحيح | `error_codes` و`error_details` و`raw_record` |

يتحقق ملف `reports/results.json` من المعادلة `raw_loaded = valid_count + corrected_count + quarantine_count`، ويسجل الزمن، ومعدل المعالجة، وعدد الدفعات أو التقسيمات، وأنواع الأخطاء، وعدادات `inserted/updated/unchanged`.

## الاختبارات

```bash
pytest -q
```

تغطي الاختبارات إصلاح الأرقام العربية والعملة وفواصل الآلاف والتاريخ والهاتف والبريد، وإعادة حساب الإجمالي، وأثر التصحيح، وعزل التاريخ المستحيل وJSON الفارغ والمعرف المفقود، واختيار Router للمحرك.

## البنية

| المسار | المسؤولية |
|---|---|
| `config/settings.py` | الإعدادات والمسارات والاتصالات |
| `src/main.py` | نقطة التشغيل الوحيدة وإدارة الموارد |
| `src/file_router.py` | اختيار المحرك حسب الحجم |
| `src/create_small_sample.py` | إنشاء عينة Streaming قابلة لإعادة الإنتاج |
| `src/batch_loader.py` | Streaming CSV و`insert_many` بالدفعات |
| `src/spark_loader.py` | Spark DataFrame وSchema ثابت والكتابة المتوازية |
| `src/quality_rules.py` | قواعد التنظيف والتصنيف وAudit Trail |
| `src/elt_pipeline.py` | ربط Raw ثم Transform ثم Final Load |
| `src/mongo_setup.py` | MongoDB وUnique Index وUpsert |
| `src/incremental_loader.py` | المسار B للـDelta والإصدارات |
| `src/metrics.py` | القياسات ونتائج JSON |
| `tests/` | اختبارات الجودة والتوجيه |

جميع الوحدات تحتوي على تعليق فوق كل وظيفة أو قاعدة يوضح الغرض منها وعلاقتها بمتطلبات التكليف.
