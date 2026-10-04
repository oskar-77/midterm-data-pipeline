# المعمارية

```text
Dirty CSV
   |
   v
File Router (size <= threshold?)
   |--------------------|
   v                    v
Python Batch         PySpark
   |                    |
   +---------+----------+
             v
        orders_raw
             |
   Transform + Quality
       |             |
       v             v
orders_validated  orders_quarantine
       |
Idempotent Upsert by order_id
       |
reports/results.json
```

## القرارات

يُستخدم `order_id` كمفتاح أعمال ثابت. لا يحتوي `orders_raw` على Validator أو فهرس فريد، لأن الغرض منه حفظ كل محاولة تحميل تاريخيًا حسب `run_id`. أما `orders_validated` فيحتوي فهرسًا فريدًا على `order_id` وتتم الكتابة إليه بواسطة `update_one(..., upsert=True)`، ولذلك لا تعتمد العملية على نمط `check-then-insert` القابل للتسابق.

تتم مرحلة Raw قبل أي استدعاء لقواعد الجودة. في مسار Python، يُقرأ CSV عبر `csv.DictReader` وتُرسل دفعة إلى `insert_many` ثم تُعالج. في مسار Spark، يقرأ DataFrame الملف بـSchema ثابت وبـStringType للحقول الحساسة، ويكتب كل partition إلى MongoDB عبر `mapPartitions`، ثم تبدأ مرحلة Transform بعد اكتمال Raw.

تطبق الجودة قواعد آمنة فقط: Trim، تحويل الأرقام العربية، إزالة العملة، إزالة فواصل الآلاف، تحويل الكلمات السعرية المحددة، توحيد الهاتف، إصلاح رموز البريد المكررة، توحيد التاريخ، تحليل JSON، توحيد المرادفات، وإعادة حساب الإجمالي. كل تغيير يُسجل في `corrections`، وأي خطأ جوهري يُحفظ في Quarantine مع `raw_record` و`error_codes` و`error_details`.

## مسار العرض

يبدأ العرض بعينة صغيرة لإظهار اختيار Python Batch، ثم تُفحص `orders_raw` لإثبات وصول السجلات قبل التنظيف، ثم تُعرض حالة Valid وCorrected وQuarantined. بعد ذلك يُشغل ملف كبير أو مسار Spark صراحة لإظهار partitions وJobs وStages في Spark UI. وأخيرًا تُعرض `results.json` ويُعاد تشغيل نفس الإدخال لإثبات عدم زيادة Business Records، ثم تُشغّل Delta لإثبات Insert وUpdate وUnchanged في المسار B.
