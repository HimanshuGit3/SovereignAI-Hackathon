import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.router.classifier import TaskRouter

router = TaskRouter()

CASES = [
    ("Write a Python function to compute NPSH for a centrifugal pump", [], None),
    ("```python\nfor i in range(10):\n  print(i)\n```\nwhy does this fail?", [], None),
    ("Summarise this inspection report and draft an approval note as a Word file", [], None),
    ("Extract the key findings from the vendor document", [], None),
    ("What is the flash point of diesel?", [], None),
    ("Describe what you see", ["/data/samples/pid_01.png"], None),
    ("Read this and list defects", ["/data/samples/inspection.pdf"], None),
    ("Review this module", ["/tmp/pump_calc.py"], None),
    ("Tell me about MRPL", [], None),
    ("anything at all", [], "code"),
]

print(f"{'METHOD':<14}{'TASK':<10}{'MODEL':<20}{'ms':>5}  REASON")
print("-" * 100)

for prompt, atts, hint in CASES:
    d = router.route(prompt, attachments=atts, task_hint=hint)
    print(f"{d.method:<14}{d.task_type.value:<10}{d.model_name:<20}{d.latency_ms:>5}  {d.reason}")
    print(f"{'':14}> {prompt[:70]}")

print("\n=== ROUTER TEST COMPLETE ===")
