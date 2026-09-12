import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.monitor.capture import PacketCapture, capture_during
from app.monitor.egress import install_monitor

print(f"tcpdump available: {PacketCapture.available()}\n")

monitor = install_monitor()
from app.agent.loop import Agent   # noqa: E402

agent = Agent()

TASK = ("Read data/samples/inspection_report.png, then assess the casing "
        "wall thickness of 8.2 mm against a design minimum of 9.0 mm.")

print(f"TASK: {TASK}\n")
print("starting packet capture, then running the agent...\n")

run, report = capture_during(lambda: agent.run(TASK))

print(f"  agent steps : {len(run.steps)}")
print(f"  tools used  : {[s.tool for s in run.steps if s.kind == 'tool']}")
print(f"  duration    : {run.total_ms} ms")
print(f"\n  ANSWER:\n    {run.answer[:400]}")

print()
print(report.render())
print()
print(monitor.render(limit=12))

ks = report.summary()
es = monitor.summary()
print("\n" + "=" * 74)
print("  COMBINED VERDICT")
print("=" * 74)
print(f"  application audit : {es['external_count']} external calls")
print(f"  kernel capture    : {ks['external']} external packets")
verdict = ks["sovereign"] and es["sovereign"]
print(f"\n  {'PASS - both layers agree: sovereign' if verdict else 'FAIL - egress detected'}")
