import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.rag.store import VectorStore, split_markdown

BASE = Path(__file__).resolve().parent.parent
store = VectorStore()

print("--- chunker sanity ---")
sample = BASE / "data" / "kb" / "SOP-MECH-014_pump_maintenance.md"
pieces = split_markdown(sample.read_text())
print(f"  {len(pieces)} chunks, sizes: {[len(p) for p in pieces]}")

print("\n--- indexing knowledge base ---")
store.clear()
for f in sorted((BASE / "data" / "kb").glob("*.md")):
    r = store.add_document(str(f.relative_to(BASE)), f.read_text())
    print(f"  {f.name:<44} {r['chunks']} chunks, dim {r['dim']}, {r['embed_ms']} ms")

s = store.stats()
print(f"\n  total chunks: {s['total_chunks']}  model: {s['embed_model']}")

QUERIES = [
    "who approves shutdown of a high criticality pump",
    "what is the bearing temperature alarm setpoint",
    "how long does a mechanical seal take to deliver",
    "can I round off measured values in an approval note",
    "what is the trip setpoint for vibration",
]

print("\n--- retrieval ---")
for q in QUERIES:
    print(f"\n  Q: {q}")
    hits = store.search(q, k=3)
    if not hits:
        print("     no chunk above the similarity threshold")
    for h in hits:
        snippet = " ".join(h.text.split())[:130]
        print(f"     {h.score:.3f} {h.citation():<44} {snippet}")

print("\n--- ANSWER PRESENCE CHECK ---")
EXPECT = [
    ("what is the bearing temperature alarm setpoint", "75 degrees Celsius"),
    ("who approves shutdown of a high criticality pump", "Head of Mechanical Maintenance"),
    ("how long does a mechanical seal take to deliver", "21 days"),
    ("can I round off measured values in an approval note", "not permitted"),
]
for q, needle in EXPECT:
    hits = store.search(q, k=3)
    # Compare with whitespace collapsed: source documents wrap lines, so
    # "Head of Mechanical Maintenance" appears as "Head of\n  Mechanical".
    norm = lambda t: " ".join(t.lower().split())
    found = any(norm(needle) in norm(h.text) for h in hits)
    top = hits[0].citation() if hits else "nothing"
    print(f"  {'PASS' if found else 'FAIL'}  '{needle}' in top-3   (top: {top})")
    print(f"        {q}")

print("\n=== RAG STORE TEST COMPLETE ===")
