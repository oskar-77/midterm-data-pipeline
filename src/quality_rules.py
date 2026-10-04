"""قواعد جودة مستقلة عن التحميل وقاعدة البيانات.

كل دالة هنا تشرح القاعدة فوقها، وتعيد نتيجة قابلة للتتبع بدل إسقاط السجل.
"""

from __future__ import annotations

import json
import re
from datetime import datetime
from decimal import Decimal, InvalidOperation
from typing import Any

# نحول الأرقام العربية/الفارسية إلى أرقام لاتينية قبل التحويل النوعي.
_DIGIT_TRANSLATION = str.maketrans("٠١٢٣٤٥٦٧٨٩۰۱۲۳۴۵۶۷۸۹", "01234567890123456789")

# قاموس الكلمات السعرية المحددة فقط؛ عدم وجود كلمة يمنع التخمين ويؤدي للعزل.
_WORD_PRICES = {"ألفان": 2000, "الفان": 2000, "ألفين": 2000, "خمسة آلاف": 5000, "خمسه الاف": 5000}

# نطبع أسماء الحقول البديلة المحتملة في ملفات الطلبات التعليمية.
def _first(record: dict[str, Any], *names: str) -> Any:
    for name in names:
        if name in record:
            return record[name]
    return None

# نسجل كل تغيير بقيمته الأصلية والجديدة ورمز القاعدة لإثبات Audit Trail.
def _change(corrections: list[dict[str, Any]], field: str, old: Any, new: Any, code: str) -> None:
    if old != new:
        corrections.append({"field": field, "original_value": old, "corrected_value": new, "rule_code": code})

# نزيل الفراغات ونحوّل القيمة الفارغة إلى None لتطبيق قواعد الحقول الإلزامية.
def _clean_text(value: Any) -> Any:
    return value.strip() if isinstance(value, str) else value

# نطبع الأرقام العربية ونزيل فواصل الآلاف والرموز الواضحة من الأرقام.
def _parse_number(value: Any) -> float | None:
    if value is None or value == "":
        return None
    text = str(value).translate(_DIGIT_TRANSLATION).strip()
    for word, number in _WORD_PRICES.items():
        if text == word:
            return float(number)
    text = re.sub(r"(?:ر\.س|ريال سعودي|ريال يمني|لاير|ريال|YER|\$)", "", text, flags=re.I)
    text = text.replace(",", "").replace(" ", "")
    try:
        return float(Decimal(text))
    except (InvalidOperation, ValueError):
        return None

# نحلل التاريخ بصيغ شائعة ونرفض التواريخ المستحيلة أو المستقبلية البعيدة.
def _parse_date(value: Any) -> str | None:
    if value is None or str(value).strip() == "":
        return None
    text = str(value).strip()
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%Y/%m/%d", "%d-%m-%Y"):
        try:
            parsed = datetime.strptime(text, fmt)
            if 2000 <= parsed.year <= datetime.now().year + 1:
                return parsed.strftime("%Y-%m-%d")
            return None
        except ValueError:
            continue
    return None

# نصلح البريد عند وجود أخطاء تكرار رموز واضحة فقط، وإلا يبقى غير قابل للإصلاح.
def _repair_email(value: Any) -> tuple[Any, str | None]:
    if value is None:
        return None, None
    text = str(value).strip()
    repaired = text.replace("@@", "@").replace("..", ".")
    if repaired != text and re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", repaired):
        return repaired, "EMAIL_REPEATED_SYMBOLS"
    return text, None

# نزيل المسافات الداخلية من الهاتف ونحتفظ بالأرقام وعلامة + عند وضوح الشكل.
def _repair_phone(value: Any) -> tuple[Any, str | None]:
    if value is None:
        return None, None
    text = str(value).translate(_DIGIT_TRANSLATION).strip()
    repaired = re.sub(r"(?<=\d)\s+(?=\d)", "", text)
    repaired = re.sub(r"[^+\d]", "", repaired)
    if repaired != text and re.fullmatch(r"\+?\d{7,15}", repaired):
        return repaired, "PHONE_SPACES_NORMALIZED"
    return text, None

# نوحد المرادفات المحددة لحالة الدفع، مع إبقاء القيم غير المعروفة للمراجعة.
def _repair_status(value: Any) -> tuple[Any, str | None]:
    if value is None:
        return None, None
    original = str(value).strip().lower()
    mapping = {"مؤكد": "confirmed", "مدفوع": "paid", "confirmed": "confirmed", "paid": "paid", "pending": "pending"}
    if original in mapping:
        result = mapping[original]
        return result, "STATUS_CANONICALIZED" if result != value else None
    return str(value).strip(), None

# نحسب الإجمالي من سعر وكمية وتوصيل عندما تكون هذه المكونات كلها صالحة.
def _recalculate_total(record: dict[str, Any], corrections: list[dict[str, Any]]) -> None:
    price = _parse_number(_first(record, "unit_price", "price", "original_price"))
    quantity = _parse_number(_first(record, "quantity", "qty"))
    shipping = _parse_number(_first(record, "shipping_cost", "shipping", "delivery_fee")) or 0
    if price is not None and quantity is not None and price >= 0 and quantity >= 0:
        computed = round(price * quantity + shipping, 2)
        old = _first(record, "total", "total_amount", "order_total")
        if _parse_number(old) != computed:
            record["total"] = computed
            _change(corrections, "total", old, computed, "TOTAL_RECALCULATED")

# نطبق جميع القواعد ونفصل الأخطاء الجوهرية عن الأخطاء القابلة للتصحيح.
def clean_and_classify(raw: dict[str, Any]) -> dict[str, Any]:
    record = dict(raw)
    corrections: list[dict[str, Any]] = []
    errors: list[dict[str, str]] = []

    # القاعدة 1: Trim للحقول النصية، وهي عملية آمنة لا تعتمد على التخمين.
    for field, value in list(record.items()):
        if isinstance(value, str):
            cleaned = value.strip()
            _change(corrections, field, value, cleaned, "TRIM_WHITESPACE")
            record[field] = cleaned

    # القاعدة 2: Stable Business Key؛ لا يمكن استنتاج order_id المفقود بأمان.
    order_id = _first(record, "order_id", "id")
    if not order_id:
        errors.append({"code": "MISSING_ORDER_ID", "message": "معرف الطلب مفقود ولا يمكن استنتاجه."})
    else:
        record["order_id"] = str(order_id)

    # القاعدة 3: معرف العميل إلزامي لأنه قيمة جوهرية في الطلب.
    customer_id = _first(record, "customer_id", "customerId")
    if not customer_id:
        errors.append({"code": "MISSING_CUSTOMER_ID", "message": "معرف العميل مفقود."})
    else:
        record["customer_id"] = str(customer_id)

    # القاعدة 4: تطبيع السعر والأرقام العربية وفواصل الآلاف والعملة والكلمات المعروفة.
    for field in ("unit_price", "price", "original_price", "total", "total_amount", "quantity", "qty", "shipping_cost"):
        if field in record and record[field] not in (None, ""):
            parsed = _parse_number(record[field])
            if parsed is not None:
                _change(corrections, field, record[field], parsed, "NUMBER_CURRENCY_NORMALIZED")
                record[field] = parsed

    # القاعدة 5: القيم السالبة الغامضة لا تُعدّل تلقائيًا.
    for field in ("unit_price", "price", "original_price", "total", "quantity", "qty", "shipping_cost"):
        if field in record and isinstance(record[field], (int, float)) and record[field] < 0:
            errors.append({"code": "AMBIGUOUS_NEGATIVE_VALUE", "message": f"القيمة السالبة في {field} غامضة."})

    # القاعدة 6: إصلاح الهاتف عند وجود مسافات أو رموز يمكن توحيدها بوضوح.
    if "customer_phone" in record or "phone" in record:
        field = "customer_phone" if "customer_phone" in record else "phone"
        new, code = _repair_phone(record[field])
        _change(corrections, field, record[field], new, code or "PHONE_NO_CHANGE")
        record[field] = new

    # القاعدة 7: إصلاح البريد ذي الرموز المكررة إن نتج بريد صالح بعد الإصلاح.
    if "customer_email" in record or "email" in record:
        field = "customer_email" if "customer_email" in record else "email"
        new, code = _repair_email(record[field])
        if code:
            _change(corrections, field, record[field], new, code)
            record[field] = new
        elif new and not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", str(new)):
            errors.append({"code": "INVALID_EMAIL", "message": "البريد الإلكتروني غير قابل للإصلاح الآمن."})

    # القاعدة 8: تطبيع التاريخ والتحقق من التاريخ المستحيل.
    date_field = next((f for f in ("order_date", "date", "created_at") if f in record), None)
    if date_field:
        parsed_date = _parse_date(record[date_field])
        if parsed_date is None:
            errors.append({"code": "INVALID_IMPOSSIBLE_DATE", "message": "تاريخ غير منطقي أو مستحيل."})
        else:
            _change(corrections, date_field, record[date_field], parsed_date, "DATE_STANDARDIZED")
            record[date_field] = parsed_date

    # القاعدة 9: تحليل items JSON؛ السجل الخام محفوظ مهما كانت نتيجة التحليل.
    items_value = _first(record, "items", "items_json", "order_items")
    if items_value is None:
        errors.append({"code": "CORRUPTED_ITEMS_JSON", "message": "حقل items مفقود."})
    else:
        try:
            items = json.loads(items_value) if isinstance(items_value, str) else items_value
            if not isinstance(items, list):
                raise ValueError("items is not a list")
            if not items:
                errors.append({"code": "EMPTY_ITEMS", "message": "لا توجد عناصر للطلب."})
            else:
                record["items"] = items
        except (json.JSONDecodeError, TypeError, ValueError):
            errors.append({"code": "CORRUPTED_ITEMS_JSON", "message": "JSON ناقص أو غير قابل للتحليل."})

    # القاعدة 10: توحيد حالة الدفع وفق قاموس معروف فقط.
    if "status" in record:
        new_status, code = _repair_status(record["status"])
        if code:
            _change(corrections, "status", record["status"], new_status, code)
            record["status"] = new_status

    # القاعدة 11: إعادة حساب الإجمالي من المكونات الصحيحة مع توثيق التغيير.
    _recalculate_total(record, corrections)

    # نحدد التصنيف النهائي؛ أي خطأ جوهري يجعل السجل Quarantined ولا نحذف raw_record.
    if errors:
        return {"quality_status": "quarantined", "error_codes": [e["code"] for e in errors], "error_details": errors, "raw_record": raw, "record": record, "corrections": corrections}
    status = "corrected" if corrections else "valid"
    return {"quality_status": status, "record": record, "corrections": corrections, "error_codes": [], "error_details": [], "raw_record": raw}
