import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.rag.answer import KnowledgeBase

kb = KnowledgeBase()
print(f"chunks indexed: {kb.store.stats()['total_chunks']}\n")

ANSWERABLE = [
    ("what is the bearing temperature alarm setpoint", "75"),
    ("who must approve shutdown of a HIGH criticality pump", "Mechanical Maintenance"),
    ("what is the lead time for a standard mechanical seal", "21"),
    ("is rounding of measured values allowed in an approval note", "not permitted"),
    ("how many days do I have to schedule a HIGH criticality shutdown", "30"),
]

UNANSWERABLE = [
    "what is the vibration trip setpoint in mm per second",
    "what is the maximum allowable flare header pressure",
    "who is the current managing director of MRPL",
]

print("#" * 74)
print("# ANSWERABLE - must answer correctly WITH citations")
print("#" * 74)
for q, needle in ANSWERABLE:
    a = kb.ask(q)
    hit = needle.lower() in a.answer.lower()
    cited = "[" in a.answer
    print(f"\nQ: {q}")
    print(f"   fact '{needle}': {'PASS' if hit else 'FAIL'} | "
          f"cited: {'yes' if cited else 'NO'} | top {a.top_score:.3f} | {a.elapsed_ms} ms")
    print("   " + a.answer.replace("\n", "\n   ")[:420])

print("\n" + "#" * 74)
print("# UNANSWERABLE - must REFUSE, not invent")
print("#" * 74)
for q in UNANSWERABLE:
    a = kb.ask(q)
    refused = (not a.confident) or any(
        p in a.answer.lower()
        for p in ("do not specify", "does not specify", "do not appear",
                  "not stated", "not contain", "no information", "not covered"))
    print(f"\nQ: {q}")
    print(f"   refused: {'PASS' if refused else 'FAIL - HALLUCINATED'} | "
          f"confident={a.confident} | top {a.top_score:.3f}")
    print("   " + a.answer.replace("\n", "\n   ")[:340])

print("\n=== KNOWLEDGE BASE TEST COMPLETE ===")
