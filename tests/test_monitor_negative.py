"""Negative control: the monitor MUST detect a deliberate violation.

Proving 'no external traffic' is only meaningful if the instrument can
detect external traffic when it exists. This test makes a real outbound
attempt and fails if either layer stays silent.
"""
import sys
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.monitor.capture import capture_during
from app.monitor.egress import install_monitor

monitor = install_monitor()
monitor.reset()


def violate():
    results = []
    for url in ("http://10.0.2.2:11434/api/tags", "http://8.8.8.8/", ):
        try:
            r = httpx.get(url, timeout=5)
            results.append(f"{url} -> {r.status_code}")
        except Exception as e:
            results.append(f"{url} -> {type(e).__name__}")
    return results


print("making one LOCAL call and one deliberate EXTERNAL call...\n")
results, report = capture_during(violate)
for r in results:
    print("  " + r)

print()
print(report.render())
print()
print(monitor.render(limit=10))

es = monitor.summary()
ks = report.summary()

print("\n" + "=" * 74)
print("  NEGATIVE CONTROL")
print("=" * 74)
print(f"  app audit flagged external : {es['external_count']} (expect >= 1)")
print(f"  kernel parsed packets      : {ks['parsed_lines']} (expect > 0)")
print(f"  kernel flagged external    : {ks['external']} (expect >= 1)")

app_ok = es["external_count"] >= 1
ker_ok = ks["parsed_lines"] > 0
print(f"\n  app layer detects violation    : {'PASS' if app_ok else 'FAIL'}")
print(f"  kernel layer is not blind      : {'PASS' if ker_ok else 'FAIL'}")
print(f"  kernel detects external packet : "
      f"{'PASS' if ks['external'] >= 1 else 'FAIL (or egress blocked upstream)'}")
