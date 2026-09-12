"""File access tools, scoped to data/ and outputs/."""
from pathlib import Path

from app.config import BASE_DIR
from app.ingest.extractor import DocumentExtractor
from app.tools.base import ToolResult, ToolSpec, safe_path

_extractor: DocumentExtractor | None = None


def _get_extractor() -> DocumentExtractor:
    global _extractor
    if _extractor is None:
        _extractor = DocumentExtractor()
    return _extractor


def read_document(path: str) -> ToolResult:
    p = safe_path(path, must_exist=True)
    doc = _get_extractor().extract(p)
    body = doc.text
    if doc.tag_summary and "No ISA tags" not in doc.tag_summary:
        body += f"\n\n--- EQUIPMENT TAGS (decoded deterministically) ---\n{doc.tag_summary}"
    return ToolResult(
        True, body, "read_document",
        meta={"method": doc.method, "pages": doc.pages,
              "yield_score": doc.yield_score, "notes": doc.notes},
    )


def list_files(directory: str = "data/samples") -> ToolResult:
    p = safe_path(directory, must_exist=True)
    if not p.is_dir():
        return ToolResult(False, f"not a directory: {p}", "list_files")
    rows = []
    for f in sorted(p.iterdir()):
        kind = "dir " if f.is_dir() else "file"
        size = f.stat().st_size if f.is_file() else 0
        rel = f.relative_to(BASE_DIR)
        rows.append(f"  {kind}  {size:>9}  {rel}")
    listing = "\n".join(rows) if rows else "  (empty)"
    return ToolResult(True, f"Contents of {p.relative_to(BASE_DIR)}:\n{listing}",
                      "list_files")


def write_text_file(filename: str, content: str) -> ToolResult:
    name = Path(filename).name
    p = safe_path(f"outputs/{name}")
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content, encoding="utf-8")
    return ToolResult(
        True, f"Wrote {len(content)} characters to {p.name}",
        "write_text_file", artifacts=[str(p.relative_to(BASE_DIR))],
    )


SPECS = [
    ToolSpec(
        name="read_document",
        description=(
            "Read any document: image, scanned PDF, native PDF, or text file. "
            "Automatically applies OCR or a vision model as needed and decodes "
            "equipment tags. Use this before answering questions about a file."
        ),
        parameters={
            "type": "object",
            "properties": {
                "path": {"type": "string",
                         "description": "Path such as data/samples/inspection_report.png"},
            },
            "required": ["path"],
        },
        fn=read_document,
    ),
    ToolSpec(
        name="list_files",
        description="List files in a directory under data/ or outputs/.",
        parameters={
            "type": "object",
            "properties": {
                "directory": {"type": "string",
                              "description": "Directory, e.g. data/samples"},
            },
            "required": [],
        },
        fn=list_files,
    ),
    ToolSpec(
        name="write_text_file",
        description="Save plain text to a file in outputs/. For Word documents use create_word_document instead.",
        parameters={
            "type": "object",
            "properties": {
                "filename": {"type": "string", "description": "e.g. notes.txt"},
                "content": {"type": "string", "description": "Text to write"},
            },
            "required": ["filename", "content"],
        },
        fn=write_text_file,
    ),
]
