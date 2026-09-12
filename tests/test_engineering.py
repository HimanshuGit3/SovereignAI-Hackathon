import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.tools import build_toolbox

box = build_toolbox()

CASES = [
    ("npsh_available",
     {"suction_pressure_bar": 1.8, "vapour_pressure_bar": 0.35,
      "density_kg_m3": 850, "static_head_m": 3.2, "friction_loss_m": 0.9},
     19.69, "m"),
    ("pump_power",
     {"flow_m3_s": 0.028, "density_kg_m3": 850, "head_m": 45,
      "efficiency": 0.72},
     14.59, "kW"),
    ("wall_thickness",
     {"measured_mm": 8.2, "design_minimum_mm": 9.0},
     -0.8, "mm"),
    ("wall_thickness",
     {"measured_mm": 8.2, "design_minimum_mm": 7.0,
      "nominal_mm": 10.0, "years_in_service": 12},
     8.0, "yr"),   # 1.2 mm margin / 0.15 mm-per-yr = 8.0
]

for name, params, expected, unit in CASES:
    print("=" * 72)
    r = box.call("engineering_calculation",
                 {"calculation": name, "parameters": params})
    print(r.output)
    got = r.meta.get("value")
    ok = got is not None and abs(got - expected) < 0.05
    print(f"\n  CHECK: expected ~{expected} {unit}, got {got:.4g} "
          f"{r.meta.get('unit')}  -> {'PASS' if ok else 'FAIL'}")
    print()

print("=" * 72)
print("ERROR HANDLING")
print("=" * 72)
print(box.call("engineering_calculation",
               {"calculation": "nonsense", "parameters": {}}).output)
print(box.call("engineering_calculation",
               {"calculation": "pump_power", "parameters": {"flow_m3_s": 0.028}}).output)

print("\n=== ENGINEERING TEST COMPLETE ===")
