"""إنشاء عينة CSV قابلة لإعادة الإنتاج دون استخدام Excel أو تحميل المصدر كاملًا."""

from __future__ import annotations

import argparse
import csv
from pathlib import Path

# ننسخ العنوان وأول rows فقط؛ القراءة تبقى Streaming حتى مع مصدر ضخم.
def create_sample(input_path: Path, output_path: Path, rows: int) -> int:
    with input_path.open("r", encoding="utf-8-sig", newline="") as source, output_path.open("w", encoding="utf-8", newline="") as target:
        reader = csv.reader(source)
        writer = csv.writer(target)
        try:
            header = next(reader)
        except StopIteration:
            return 0
        writer.writerow(header)
        copied = 0
        for row in reader:
            if copied >= rows:
                break
            writer.writerow(row)
            copied += 1
    print(f"تم إنشاء العينة: {output_path} بعدد صفوف={copied}")
    return copied

# نوفر أمر CLI مطابقًا للمثال الرسمي في وثيقة التكليف.
def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, default=Path("data/orders_sample.csv"))
    parser.add_argument("--rows", type=int, required=True)
    args = parser.parse_args()
    create_sample(args.input, args.output, args.rows)

if __name__ == "__main__":
    main()
