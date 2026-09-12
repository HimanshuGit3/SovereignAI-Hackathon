import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.tools import build_toolbox

box = build_toolbox()

print("=== REGISTERED TOOLS ===")
print(box.describe())

print("\n=== 1. list_files ===")
r = box.call("list_files", {"directory": "data/samples"})
print(r.for_model())

print("\n=== 2. read_document (OCR path) ===")
r = box.call("read_document", {"path": "data/samples/inspection_report.png"})
print(f"ok={r.ok} method={r.meta.get('method')} {r.elapsed_ms} ms")
print(r.output[:400])

print("\n=== 3. create_word_document ===")
r = box.call("create_word_document", {
    "filename": "approval_note_P101A.docx",
    "title": "Approval Note - Shutdown of Pump P-101A",
    "subject": "Casing replacement and seal renewal, Crude Feed Pump P-101A",
    "reference": "INSP-2026-0417",
    "background": ("Routine inspection of P-101A on 03 September 2026 recorded "
                   "casing wall thickness below the design retirement limit."),
    "findings": ["Casing wall thickness 8.2 mm against 9.0 mm design minimum.",
                 "Outboard bearing at 82 deg C, above the 75 deg C alarm setpoint.",
                 "Mechanical seal weeping at approximately 4 drops per minute."],
    "recommendation": "Schedule P-101A for shutdown within 30 days.",
    "approval_sought": "Approval for shutdown, casing replacement and seal kit renewal.",
})
print(r.for_model())

print("\n=== 4. SECURITY: path traversal (must fail) ===")
for bad in ("/etc/passwd", "../../etc/shadow", "data/../../../root/.ssh/id_rsa"):
    r = box.call("read_document", {"path": bad})
    print(f"  {bad:<36} ok={r.ok}  {r.output[:70]}")

print("\n=== 5. bad arguments (must fail gracefully) ===")
print("  " + box.call("read_document", {"wrong_arg": "x"}).output[:90])
print("  " + box.call("nonexistent_tool", {}).output[:90])

print("\n=== OUTPUTS ===")
for f in sorted((Path(__file__).resolve().parent.parent / "outputs").iterdir()):
    if f.name != ".gitkeep":
        print(f"  {f.name:<34}{f.stat().st_size:>8} bytes")

print("\n=== TOOL TEST COMPLETE ===")
