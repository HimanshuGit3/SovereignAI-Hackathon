import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.rag.store import VectorStore

store = VectorStore()

# Queries a refinery engineer would actually type. Several reference
# documents and sections by exact identifier, which dense embeddings
# handle poorly: cosine similarity captures meaning, not literal strings.
CASES = [
    ("what does SOP-MECH-014 say about wall thickness", "retirement limit"),
    ("SOP-INSP-007 section 4", "verbatim"),
    ("CORR-2026-0318 lead time", "21 days"),
    ("E-204B", None),
    ("INSP-2026 report numbering format", "INSP-YYYY-NNNN"),
    ("bearing alarm setpoint", "75 degrees"),
    ("who signs off a high criticality shutdown", "Mechanical Maintenance"),
    ("API 579", "fitness-for-service"),
]

print(f"{'QUERY':<48}{'TOP':>7}  HIT  SOURCE")
print("-" * 100)
hits = 0
for q, needle in CASES:
    res = store.search(q, k=3)
    top = res[0].score if res else 0.0
    if needle is None:
        ok = not res
        mark = "n/a" if ok else "!!"
    else:
        norm = lambda t: " ".join(t.lower().split())
        ok = any(norm(needle) in norm(c.text) for c in res)
        mark = "yes" if ok else "NO "
        hits += ok
    src = res[0].citation() if res else "nothing returned"
    print(f"{q[:47]:<48}{top:>7.3f}  {mark}  {src}")

print(f"\n  dense-only: {hits}/{sum(1 for _, n in CASES if n)} answerable queries hit")

print("\n" + "=" * 100)
print("HYBRID: BM25 fused with dense by reciprocal rank")
print("=" * 100)

from app.rag.hybrid import HybridRetriever
hr = HybridRetriever(store)

print(f"{'QUERY':<48}{'FUSED':>8}{'DENSE':>7}{'BM25':>7}  HIT  MATCHED TERMS")
print("-" * 100)
hits2 = 0
for q, needle in CASES:
    res = hr.search(q, k=3)
    if needle is None:
        mark = "n/a"
    else:
        norm = lambda t: " ".join(t.lower().split())
        ok = any(norm(needle) in norm(s.chunk.text) for s in res)
        mark = "yes" if ok else "NO "
        hits2 += ok
    if res:
        t = res[0]
        print(f"{q[:47]:<48}{t.fused:>8.4f}{t.dense:>7.3f}{t.lexical:>7.2f}"
              f"  {mark}  {','.join(t.matched[:4])}")
    else:
        print(f"{q[:47]:<48}{'-':>8}{'-':>7}{'-':>7}  {mark}  nothing")

total = sum(1 for _, n in CASES if n)
print(f"\n  dense-only : {hits}/{total}")
print(f"  hybrid     : {hits2}/{total}")
