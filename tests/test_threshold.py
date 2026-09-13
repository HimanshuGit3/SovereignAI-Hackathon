"""Sweep the RAG confidence floor against known-covered and
known-uncovered questions.

The floor decides whether the model is called at all. Too high and the
system falsely refuses questions the corpus answers; too low and it
starts answering from chunks that merely look relevant.

This is fitted to a small corpus. Re-run it after adding documents.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.rag.answer import CONFIDENCE_FLOOR
from app.rag.hybrid import HybridRetriever

COVERED = [
    "what is the bearing temperature alarm setpoint",
    "who must approve shutdown of a HIGH criticality pump",
    "what is the lead time for a standard mechanical seal",
    "is rounding of measured values allowed in an approval note",
    "how many days do I have to schedule a HIGH criticality shutdown",
    "what is the trip setpoint for bearings",
    "how much seal weepage is acceptable",
    "when is the next inspection due for high criticality equipment",
    "what must an approval note contain",
    "how is corrosion rate calculated",
    "what does SOP-MECH-014 say about wall thickness",
    "API 579",
]

NOT_COVERED = [
    "what is the vibration trip setpoint in mm per second",
    "what is the maximum allowable flare header pressure",
    "who is the current managing director of MRPL",
    "what is the design pressure of V-9901",
    "what is the crude throughput of the refinery",
    "what PPE is required in the tank farm",
    "what is the flash point of diesel",
    "how many operators are on each shift",
]

hr = HybridRetriever()
cov = sorted(hr.confidence(hr.search(q, k=4), q) for q in COVERED)
non = sorted(hr.confidence(hr.search(q, k=4), q) for q in NOT_COVERED)

print("covered     :", " ".join(f"{c:.3f}" for c in cov))
print("not covered :", " ".join(f"{c:.3f}" for c in non))
print(f"\n  lowest covered    {cov[0]:.3f}")
print(f"  highest uncovered {non[-1]:.3f}")
print(f"  {'separable' if cov[0] > non[-1] else 'OVERLAPPING - no clean threshold exists'}")

print(f"\n{'floor':>7}{'answered':>10}{'refused':>9}{'false ref':>11}{'false ans':>11}")
for i in range(52, 80, 2):
    t = i / 100
    tp = sum(c >= t for c in cov)
    tn = sum(c < t for c in non)
    mark = "  <- current" if abs(t - CONFIDENCE_FLOOR) < 0.005 else ""
    print(f"{t:>7.2f}{tp:>6}/{len(cov)}{tn:>6}/{len(non)}"
          f"{len(cov)-tp:>11}{len(non)-tn:>11}{mark}")
