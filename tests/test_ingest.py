import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.ingest.extractor import DocumentExtractor

BASE = Path(__file__).resolve().parent.parent
ex = DocumentExtractor()

for name in ("inspection_report.png", "pid_extract.png"):
    p = BASE / "data" / "samples" / name
    print("#" * 72)
    print(f"# {name}")
    print("#" * 72)
    doc = ex.extract(p)
    for k, v in doc.as_dict().items():
        print(f"  {k:<14} {v}")
    print("\n  --- TEXT (first 500 chars) ---")
    print("  " + doc.text[:500].replace("\n", "\n  "))
    print("\n  --- DECODED TAGS ---")
    print("  " + doc.tag_summary.replace("\n", "\n  "))
    print()

print("=== INGEST TEST COMPLETE ===")
