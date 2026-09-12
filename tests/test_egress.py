import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.monitor.egress import install_monitor

monitor = install_monitor()          # must be installed BEFORE any client
print("egress monitor installed\n")

from app.agent.loop import Agent     # noqa: E402

agent = Agent()

print("--- classification unit check ---")
for host in ("127.0.0.1", "10.0.2.2", "192.168.59.1", "172.17.0.2",
             "8.8.8.8", "ollama.com", "140.82.121.4"):
    c, why = monitor.classify(host)
    print(f"  {host:<16} {c:<9} {why}")

print("\n--- running a real agent task under audit ---")
run = agent.run("Read data/samples/inspection_report.png and tell me the "
                "casing wall thickness.")
print(f"  steps={len(run.steps)}  {run.total_ms} ms")
print(f"  answer: {run.answer[:160]}")

print()
print(monitor.render())

s = monitor.summary()
print(f"\nEXIT: {'PASS - sovereign' if s['sovereign'] else 'FAIL - external egress'}")
