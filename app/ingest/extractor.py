"""Hybrid document ingestion.

Routing is measured, not guessed: run cheap OCR first, score the text
yield, and escalate to the vision model only when OCR comes back thin.
Thresholds derive from benchmarks on this hardware (see docs/).
"""
import time
from dataclasses import dataclass, field
from pathlib import Path

import fitz  # PyMuPDF
import pytesseract
from PIL import Image

from app.core.llm import OllamaClient
from app.ingest.tags import summarise
from app.router.registry import ModelRegistry

IMAGE_EXT = {".png", ".jpg", ".jpeg", ".bmp", ".tif", ".tiff", ".webp"}
TEXT_EXT = {".txt", ".md", ".csv", ".log"}

# Measured on synthetic samples: typed report 821 chars/MP, schematic 106.
OCR_YIELD_THRESHOLD = 300.0
PDF_NATIVE_CHARS_PER_PAGE = 200

VISION_PROMPT = (
    "Transcribe this image as plain text. Do NOT use JSON, markdown or code "
    "blocks.\n\n"
    "1. TEXT: list every piece of text you can read, one per line, exactly "
    "as printed. Copy tag numbers character by character.\n"
    "2. LAYOUT: describe in one or two sentences how the components are "
    "arranged left to right.\n\n"
    "Do not explain what any tag means. Do not infer equipment types. "
    "If a character is unclear, write [?] instead of guessing."
)


@dataclass
class ExtractedDoc:
    source: str
    method: str
    text: str
    elapsed_ms: int
    pages: int = 1
    yield_score: float | None = None
    tag_summary: str = ""
    notes: list[str] = field(default_factory=list)

    def as_dict(self) -> dict:
        return {
            "source": self.source,
            "method": self.method,
            "pages": self.pages,
            "chars": len(self.text),
            "yield_score": self.yield_score,
            "elapsed_ms": self.elapsed_ms,
            "notes": self.notes,
        }


class DocumentExtractor:
    def __init__(self, client: OllamaClient | None = None,
                 registry: ModelRegistry | None = None):
        self.client = client or OllamaClient()
        self.registry = registry or ModelRegistry()

    def extract(self, path: str | Path) -> ExtractedDoc:
        p = Path(path)
        if not p.exists():
            raise FileNotFoundError(p)
        ext = p.suffix.lower()
        t0 = time.perf_counter()

        if ext in TEXT_EXT:
            doc = self._plain(p)
        elif ext in IMAGE_EXT:
            doc = self._image(p)
        elif ext == ".pdf":
            doc = self._pdf(p)
        else:
            raise ValueError(f"unsupported file type: {ext}")

        doc.elapsed_ms = round((time.perf_counter() - t0) * 1000)
        # Diagram transcriptions tolerate "V 204"; prose must not.
        loose = doc.method in ("vision", "scanned_pdf")
        doc.tag_summary = summarise(doc.text, loose=loose)
        return doc

    def _plain(self, p: Path) -> ExtractedDoc:
        return ExtractedDoc(str(p), "plain_text",
                            p.read_text(errors="replace"), 0,
                            notes=["read directly, no OCR needed"])

    def _image(self, p: Path) -> ExtractedDoc:
        img = Image.open(p)
        megapixels = (img.width * img.height) / 1_000_000
        ocr_text = pytesseract.image_to_string(img).strip()
        score = len(ocr_text) / megapixels if megapixels else 0.0

        if score >= OCR_YIELD_THRESHOLD:
            return ExtractedDoc(
                str(p), "ocr", ocr_text, 0, yield_score=round(score, 1),
                notes=[f"OCR yield {score:.0f} chars/MP >= "
                       f"{OCR_YIELD_THRESHOLD:.0f}, vision model not needed"])

        spec = self.registry.by_role("vision")
        res = self.client.chat_with_image(
            spec.name, VISION_PROMPT, p,
            options={**self.registry.options_for(spec.id), "num_predict": 600},
            think=False, keep_alive="5m")
        combined = res["content"].strip()
        if ocr_text:
            combined += f"\n\n[OCR fragments]\n{ocr_text}"
        return ExtractedDoc(
            str(p), "vision", combined, 0, yield_score=round(score, 1),
            notes=[f"OCR yield {score:.0f} chars/MP below threshold",
                   f"escalated to {spec.name}"])

    def _pdf(self, p: Path) -> ExtractedDoc:
        pdf = fitz.open(p)
        pages = pdf.page_count
        native = "\n\n".join(pg.get_text() for pg in pdf)

        if pages and len(native.strip()) / pages >= PDF_NATIVE_CHARS_PER_PAGE:
            pdf.close()
            return ExtractedDoc(
                str(p), "native_pdf", native.strip(), 0, pages=pages,
                notes=["embedded text layer present, no OCR needed"])

        chunks, escalated = [], 0
        for i, page in enumerate(pdf):
            pix = page.get_pixmap(dpi=200)
            tmp = p.parent / f".__pg{i}.png"
            pix.save(tmp)
            try:
                sub = self._image(tmp)
                if sub.method == "vision":
                    escalated += 1
                chunks.append(f"--- page {i+1} ---\n{sub.text}")
            finally:
                tmp.unlink(missing_ok=True)
        pdf.close()

        return ExtractedDoc(
            str(p), "scanned_pdf", "\n\n".join(chunks), 0, pages=pages,
            notes=[f"no usable text layer; rasterised {pages} page(s) at 200 dpi",
                   f"{escalated} page(s) escalated to the vision model"])
