"""Deterministic ISA-5.1 style tag decoding.

Vision models read tag STRINGS. This module decides what they MEAN.
No LLM involved, so no hallucination is possible.

Matching is deliberately strict: tags must be UPPERCASE and hyphenated.
An earlier permissive version turned "at 82 deg C" into instrument
AT-82, which is worse than extracting nothing at all.
"""
import re
from dataclasses import dataclass

EQUIPMENT = {
    "P": "Pump", "C": "Compressor", "K": "Compressor",
    "E": "Heat Exchanger", "V": "Vessel or Valve", "D": "Drum",
    "T": "Tower or Column", "TK": "Storage Tank", "R": "Reactor",
    "F": "Fired Heater or Furnace", "H": "Heater",
    "M": "Motor", "AG": "Agitator", "FL": "Filter",
}

VARIABLE = {
    "A": "Analysis", "B": "Burner", "D": "Density", "E": "Voltage",
    "F": "Flow", "H": "Hand (manual)", "I": "Current", "J": "Power",
    "L": "Level", "M": "Moisture", "P": "Pressure", "Q": "Quantity",
    "S": "Speed", "T": "Temperature", "V": "Vibration",
    "W": "Weight or Force", "Z": "Position",
}

FUNCTION = {
    "A": "Alarm", "C": "Controller", "E": "Element or Sensor",
    "G": "Glass or Gauge", "I": "Indicator", "R": "Recorder",
    "S": "Switch", "T": "Transmitter", "V": "Valve",
    "Y": "Relay or Compute", "Z": "Final Control Element",
}

# Uppercase sequences that precede numbers but are never equipment tags.
STOPWORDS = {
    "JAN", "FEB", "MAR", "APR", "MAY", "JUN",
    "JUL", "AUG", "SEP", "OCT", "NOV", "DEC",
    "NO", "REV", "DOC", "ISO", "IEC", "API", "BS", "EN", "DIN",
    "PO", "WO", "SR", "QTY", "PG", "FIG", "TEL", "FAX",
}

# Strict: uppercase prefix, mandatory hyphen. Safe for prose.
TAG_RE = re.compile(r"\b([A-Z]{1,3})-(\d{2,5}[A-Z]?)\b")

# Loose: allows a single space instead of a hyphen. ONLY for diagram
# transcriptions, where OCR and VLMs routinely drop the hyphen and the
# surrounding text is not prose. Never use this on report bodies.
TAG_RE_LOOSE = re.compile(r"\b([A-Z]{1,3})[-\s](\d{2,5}[A-Z]?)\b")

# Piping line numbers: 6in-CS-1204
LINE_RE = re.compile(
    r"\b(\d{1,2})\s*(?:[iI][nN]|\")\s*-\s*([A-Z]{2,3})\s*-\s*(\d{3,5})\b")

MATERIAL = {"CS": "Carbon Steel", "SS": "Stainless Steel",
            "AS": "Alloy Steel", "GI": "Galvanised Iron",
            "PP": "Polypropylene", "HC": "Hastelloy"}


@dataclass
class DecodedTag:
    raw: str
    prefix: str
    number: str
    kind: str
    meaning: str
    confidence: str

    def __str__(self) -> str:
        return f"{self.raw}: {self.meaning} [{self.kind}, {self.confidence}]"


def decode_tag(prefix: str, number: str) -> DecodedTag:
    raw = f"{prefix}-{number}"
    p = prefix.upper()

    if len(p) >= 2 and p[0] in VARIABLE and all(c in FUNCTION for c in p[1:]):
        parts = [VARIABLE[p[0]]] + [FUNCTION[c] for c in p[1:]]
        return DecodedTag(raw, p, number, "instrument", " ".join(parts), "high")

    if p in EQUIPMENT:
        return DecodedTag(raw, p, number, "equipment", EQUIPMENT[p], "high")

    if p[0] in EQUIPMENT:
        return DecodedTag(raw, p, number, "equipment", EQUIPMENT[p[0]], "medium")

    return DecodedTag(raw, p, number, "unknown", "Unrecognised prefix", "low")


def extract_lines(text: str) -> list[dict]:
    seen, out = set(), []
    for size, mat, num in LINE_RE.findall(text):
        raw = f"{size}in-{mat.upper()}-{num}"
        if raw in seen:
            continue
        seen.add(raw)
        out.append({
            "raw": raw,
            "size_inches": int(size),
            "material": MATERIAL.get(mat.upper(), f"Unknown ({mat})"),
            "line_number": num,
        })
    return out


def extract_tags(text: str, loose: bool = False) -> list[DecodedTag]:
    """Decode ISA tags.

    loose=False (default): hyphen required. Use on prose.
    loose=True: a space may stand in for the hyphen. Use ONLY on
    diagram transcriptions, where 'V 204' means 'V-204'.
    """
    # Blank out line numbers first so CS-1204 isn't read as a Compressor.
    masked = LINE_RE.sub(lambda m: " " * len(m.group(0)), text)

    pattern = TAG_RE_LOOSE if loose else TAG_RE
    seen, out = set(), []
    for m in pattern.finditer(masked):
        prefix, number = m.group(1), m.group(2)
        if prefix in STOPWORDS:
            continue
        key = f"{prefix}-{number}"
        if key in seen:
            continue
        seen.add(key)
        out.append(decode_tag(prefix, number))
    return out


def summarise(text: str, loose: bool = False) -> str:
    tags = extract_tags(text, loose=loose)
    lines = extract_lines(text)
    if not tags and not lines:
        return "No ISA tags or line numbers identified."
    parts = []
    if tags:
        parts.append("Tags identified (decoded by ISA-5.1 convention):")
        parts += [f"  - {t}" for t in tags]
    if lines:
        parts.append("Piping lines identified:")
        parts += [f"  - {l['raw']}: {l['size_inches']}\" {l['material']}, "
                  f"line {l['line_number']}" for l in lines]
    return "\n".join(parts)
