"""توجيه الملف إلى المحرك المناسب بناءً على حجمه."""

from pathlib import Path

# نحسب الحجم بالميجابايت ونطبق الحد من الإعدادات، مع دعم force للاختبار والعرض.
def choose_engine(path: Path, threshold_mb: float, force_engine: str | None = None):
    size_mb = path.stat().st_size / (1024 * 1024)
    if force_engine:
        return force_engine, f"تم فرض المحرك لأغراض الاختبار: {force_engine}", size_mb
    if size_mb <= threshold_mb:
        return "python_batch", f"الحجم {size_mb:.3f} MB <= الحد {threshold_mb:.3f} MB؛ الملف صغير", size_mb
    return "pyspark", f"الحجم {size_mb:.3f} MB > الحد {threshold_mb:.3f} MB؛ الملف كبير", size_mb
