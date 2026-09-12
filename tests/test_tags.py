import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.ingest.tags import extract_tags, extract_lines

SHOULD_FIND = """
P&ID EXTRACT - LINE 6in-CS-1204
P-101A  V-204  PI-301  FIC-205  LT-110  TV-402  TK-05
"""

SHOULD_IGNORE = """
Outboard bearing temperature recorded at 82 deg C,
exceeding the 75 deg C alarm setpoint.
Report No: INSP-2026-0417
Next Inspection: 03 Dec 2026
Casing wall thickness measured at 8.2 mm against
a design minimum of 9.0 mm.
Inspector: R. Kamath, Level II NDT
"""

print("--- POSITIVE CASES ---")
for t in extract_tags(SHOULD_FIND):
    print(f"  {t}")
for l in extract_lines(SHOULD_FIND):
    print(f"  LINE {l['raw']}: {l['size_inches']}in {l['material']}")

print("\n--- FALSE POSITIVE CHECK (should be empty) ---")
bogus = extract_tags(SHOULD_IGNORE)
if bogus:
    for t in bogus:
        print(f"  LEAKED: {t}")
else:
    print("  clean - no false positives")

print("\n--- ASSERTIONS ---")
found = {t.raw for t in extract_tags(SHOULD_FIND)}
expected = {"P-101A", "V-204", "PI-301", "FIC-205", "LT-110", "TV-402", "TK-05"}
print(f"  missing: {expected - found or 'none'}")
print(f"  extra:   {found - expected or 'none'}")
print(f"  CS-1204 excluded: {'CS-1204' not in found}")

print("\n--- LOOSE MODE (diagram transcription) ---")
DIAGRAM = "FROM TK-05\nP-101A\nV 204\nPI 301\nTO CDU-1"
for t in extract_tags(DIAGRAM, loose=True):
    print(f"  {t}")

print("\n--- LOOSE MODE MUST NOT BE USED ON PROSE ---")
leaked = extract_tags(SHOULD_IGNORE, loose=True)
print(f"  false positives if misapplied: {[t.raw for t in leaked] or 'none'}")
print("  (this is why extractor.py gates loose= on method)")
