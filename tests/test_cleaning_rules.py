"""اختبارات قواعد الجودة الأساسية المطلوبة في التكليف."""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from quality_rules import clean_and_classify

# نتأكد من إصلاح الأرقام العربية والعملة وفواصل الآلاف والتاريخ والهاتف والبريد.
def test_correctable_record_has_audit_trail():
    raw = {"order_id": "O-1", "customer_id": "C-1", "customer_email": "user@@mail..com", "customer_phone": "+967 777 123 456", "order_date": "31/01/2025", "items": '[{"sku":"A","qty":2}]', "unit_price": "125,000 ريال", "quantity": "٢", "shipping_cost": "0", "total": "1"}
    result = clean_and_classify(raw)
    assert result["quality_status"] == "corrected"
    assert result["record"]["customer_email"] == "user@mail.com"
    assert result["record"]["order_date"] == "2025-01-31"
    assert result["record"]["quantity"] == 2.0
    assert result["corrections"]

# التاريخ المستحيل يجب أن يعزل السجل ولا يسمح للتنظيف بالتخمين.
def test_impossible_date_is_quarantined():
    raw = {"order_id": "O-2", "customer_id": "C-2", "order_date": "31/02/2025", "items": "[]"}
    result = clean_and_classify(raw)
    assert result["quality_status"] == "quarantined"
    assert "INVALID_IMPOSSIBLE_DATE" in result["error_codes"]
    assert "EMPTY_ITEMS" in result["error_codes"]

# السجل ذو المعرف المفقود يبقى موجودًا في نتيجة العزل مع raw_record كامل.
def test_missing_business_keys_are_not_dropped():
    raw = {"customer_id": "C-3", "items": "[]"}
    result = clean_and_classify(raw)
    assert "MISSING_ORDER_ID" in result["error_codes"]
    assert result["raw_record"] == raw
