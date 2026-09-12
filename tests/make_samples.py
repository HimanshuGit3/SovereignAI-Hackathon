import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

BASE = Path(__file__).resolve().parent.parent
OUT = BASE / "data" / "samples"
OUT.mkdir(parents=True, exist_ok=True)

CANDIDATES = [
    "/usr/share/fonts/dejavu-sans-fonts/DejaVuSans.ttf",
    "/usr/share/fonts/dejavu/DejaVuSans.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
]
FONT_PATH = next((c for c in CANDIDATES if Path(c).exists()), None)
if not FONT_PATH:
    print("ERROR: no DejaVuSans.ttf found. Run: fc-list | grep -i dejavu")
    sys.exit(1)
print("using font:", FONT_PATH)


def font(sz):
    return ImageFont.truetype(FONT_PATH, sz)


REPORT = [
    ("MANGALORE REFINERY - EQUIPMENT INSPECTION REPORT", 26, "bold"),
    ("", 10, ""),
    ("Report No:      INSP-2026-0417", 18, ""),
    ("Equipment Tag:  P-101A  (Crude Feed Pump)", 18, ""),
    ("Unit:           Crude Distillation Unit - 1", 18, ""),
    ("Inspection Date: 03 September 2026", 18, ""),
    ("Inspector:      R. Kamath, Level II NDT", 18, ""),
    ("", 12, ""),
    ("FINDINGS", 22, "bold"),
    ("1. Mechanical seal shows evidence of weeping at the", 17, ""),
    ("   gland area. Estimated leak rate 4 drops/minute.", 17, ""),
    ("2. Casing wall thickness measured at 8.2 mm against", 17, ""),
    ("   a design minimum of 9.0 mm. BELOW RETIREMENT LIMIT.", 17, ""),
    ("3. Outboard bearing temperature recorded at 82 deg C,", 17, ""),
    ("   exceeding the 75 deg C alarm setpoint.", 17, ""),
    ("4. Coupling guard fastener missing at position 3.", 17, ""),
    ("", 12, ""),
    ("RECOMMENDATION", 22, "bold"),
    ("Schedule pump for shutdown within 30 days.", 17, ""),
    ("Casing replacement required. Seal kit to be renewed.", 17, ""),
    ("", 12, ""),
    ("Criticality: HIGH        Next Inspection: 03 Dec 2026", 18, "bold"),
]

img = Image.new("RGB", (1000, 900), "white")
d = ImageDraw.Draw(img)
y = 40
for text, size, style in REPORT:
    if text:
        d.text((50, y), text, fill=(15, 15, 15), font=font(size))
    y += size + 10
d.rectangle([30, 20, 970, y + 10], outline=(80, 80, 80), width=2)
img.save(OUT / "inspection_report.png")
print("wrote", OUT / "inspection_report.png")

# Simple P&ID-style schematic
p = Image.new("RGB", (2400, 1200), "white")
d = ImageDraw.Draw(p)
d.text((700, 50), "P&ID EXTRACT - LINE 6in-CS-1204", fill="black", font=font(48))
d.line([190, 600, 2110, 600], fill="black", width=9)
d.ellipse([480, 516, 648, 684], outline="black", width=9)
d.text((496, 570), "P-101A", fill="black", font=font(34))
d.rectangle([1032, 504, 1272, 696], outline="black", width=9)
d.text((1085, 578), "V-204", fill="black", font=font(36))
d.ellipse([1632, 480, 1824, 672], outline="black", width=7)
d.text((1672, 558), "PI-301", fill="black", font=font(36))
d.text((240, 636), "FROM TK-05", fill="black", font=font(36))
d.text((1920, 636), "TO CDU-1", fill="black", font=font(36))
p.save(OUT / "pid_extract.png")
print("wrote", OUT / "pid_extract.png")

for f in sorted(OUT.iterdir()):
    print(f"  {f.name:<28}{f.stat().st_size:>8} bytes")
