import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.tools import build_toolbox

box = build_toolbox()

SPEC = ("Calculate NPSH available for a pump. Suction pressure 1.8 bar "
        "absolute, vapour pressure 0.35 bar absolute, fluid density "
        "850 kg/m3, static suction head 3.2 m, friction losses 0.9 m. "
        "NPSHa = (Ps - Pv)/(rho*g) + Hs - Hf, with pressures in pascal.")

print("EXPECTED: (1.8-0.35)*1e5 / (850*9.81) = 17.39 m")
print("          17.39 + 3.2 - 0.9 = 19.69 m\n")

gen = box.call("generate_code", {"specification": SPEC})
print("=" * 70)
print("GENERATED CODE")
print("=" * 70)
code = gen.meta.get("code", "")
print(code)

print("\n" + "=" * 70)
print("EXECUTION")
print("=" * 70)
run = box.call("run_python", {"code": code})
print(run.output)

print("\n--- VERDICT ---")
print(f"  contains 19.6 or 19.7 : {'19.6' in run.output or '19.7' in run.output}")
print(f"  contains 17.3 or 17.4 : {'17.3' in run.output or '17.4' in run.output}")
