import sys
import time
from pathlib import Path

import pytesseract
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

SAMPLES = Path(__file__).resolve().parent.parent / "data" / "samples"

for img_path in (SAMPLES / "inspection_report.png", SAMPLES / "pid_extract.png"):
    print("=" * 72)
    print(img_path.name)
    print("=" * 72)
    t0 = time.perf_counter()
    text = pytesseract.image_to_string(Image.open(img_path))
    ms = round((time.perf_counter() - t0) * 1000)
    print(f"[{ms} ms | {len(text)} chars]\n")
    print(text.strip()[:1200])
    print()

print("=== OCR BASELINE COMPLETE ===")
