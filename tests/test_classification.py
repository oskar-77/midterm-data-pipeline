"""اختبارات Router والتصنيف النهائي."""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from file_router import choose_engine

# الملف الصغير يذهب إلى Python Batch وفق الحد.
def test_router_selects_python_for_small_file(tmp_path):
    path = tmp_path / "small.csv"
    path.write_text("a,b\n1,2\n", encoding="utf-8")
    engine, reason, size = choose_engine(path, 200)
    assert engine == "python_batch"
    assert "صغير" in reason
    assert size >= 0

# يمكن فرض Spark في العرض لاختبار المسار دون تعديل الملف أو الكود.
def test_router_force_engine():
    path = Path(__file__)
    engine, reason, _ = choose_engine(path, 200, "pyspark")
    assert engine == "pyspark"
    assert "فرض" in reason
