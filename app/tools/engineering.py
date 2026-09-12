"""Verified engineering calculations.

Small language models get unit conversions and operator precedence wrong,
then report the result with full confidence. Observed on 2026-09-12:
qwen2.5-coder:3b converted bar to pascal using 101325 (the atmosphere
constant), dropped parentheses in the NPSH formula, and labelled a result
in metres as pascal. The output looked plausible and was unusable.

So the model does not do arithmetic here. It identifies WHICH calculation
applies and extracts the parameters; these functions compute the answer.
Same principle as ingest/tags.py: the LLM reads, deterministic code decides.

Every function returns each intermediate term with its unit so an engineer
can check the working against a handbook.
"""
from dataclasses import dataclass, field

from app.tools.base import ToolResult, ToolSpec

G = 9.80665          # standard gravity, m/s2
BAR_TO_PA = 100_000.0   # exact by definition. NOT 101325 (that is 1 atm)


def _fmt(v: float) -> str:
    """Engineering-readable. Large magnitudes get scientific notation;
    everyday values keep two decimals so 19.69 does not become 19.7."""
    a = abs(v)
    if a >= 1e5 or (a < 1e-3 and a > 0):
        return f"{v:.4e}"
    return f"{v:,.2f}"


@dataclass
class Step:
    label: str
    expression: str
    value: float
    unit: str

    def render(self) -> str:
        return f"  {self.label:<34} {self.expression:<32} = {_fmt(self.value)} {self.unit}"


@dataclass
class CalcResult:
    name: str
    inputs: dict
    steps: list[Step]
    value: float
    unit: str
    interpretation: str = ""
    notes: list[str] = field(default_factory=list)

    def render(self) -> str:
        out = [f"CALCULATION: {self.name}", "", "INPUTS"]
        for k, v in self.inputs.items():
            out.append(f"  {k:<34} {v}")
        out += ["", "WORKING"]
        out += [s.render() for s in self.steps]
        out += ["", f"RESULT: {_fmt(self.value)} {self.unit}"]
        if self.interpretation:
            out += ["", f"INTERPRETATION: {self.interpretation}"]
        if self.notes:
            out += [""] + [f"NOTE: {n}" for n in self.notes]
        out += ["", "Computed by verified deterministic code, not by a language model."]
        return "\n".join(out)


def npsh_available(suction_pressure_bar: float, vapour_pressure_bar: float,
                   density_kg_m3: float, static_head_m: float,
                   friction_loss_m: float) -> CalcResult:
    ps = suction_pressure_bar * BAR_TO_PA
    pv = vapour_pressure_bar * BAR_TO_PA
    dp = ps - pv
    rho_g = density_kg_m3 * G
    pressure_head = dp / rho_g
    value = pressure_head + static_head_m - friction_loss_m

    interp = ("NPSH available is positive; compare against the pump's NPSH "
              "required from its curve. A margin of at least 0.5 to 1.0 m is "
              "normal practice.")
    if value <= 0:
        interp = ("NPSH available is zero or negative. The pump WILL cavitate "
                  "at this condition.")

    return CalcResult(
        name="NPSH available (NPSHa)",
        inputs={
            "suction pressure": f"{suction_pressure_bar} bar absolute",
            "vapour pressure": f"{vapour_pressure_bar} bar absolute",
            "fluid density": f"{density_kg_m3} kg/m3",
            "static suction head": f"{static_head_m} m",
            "friction losses": f"{friction_loss_m} m",
        },
        steps=[
            Step("suction pressure", f"{suction_pressure_bar} x 100000", ps, "Pa"),
            Step("vapour pressure", f"{vapour_pressure_bar} x 100000", pv, "Pa"),
            Step("pressure difference", "Ps - Pv", dp, "Pa"),
            Step("density x gravity", f"{density_kg_m3} x {G}", rho_g, "Pa/m"),
            Step("pressure head", "(Ps - Pv) / (rho x g)", pressure_head, "m"),
            Step("plus static head", f"+ {static_head_m}",
                 pressure_head + static_head_m, "m"),
            Step("minus friction loss", f"- {friction_loss_m}", value, "m"),
        ],
        value=value, unit="m",
        interpretation=interp,
        notes=["1 bar = 100000 Pa exactly. 1 atm = 101325 Pa. Do not confuse them.",
               f"g taken as {G} m/s2 (standard gravity)."],
    )


def pump_power(flow_m3_s: float, density_kg_m3: float, head_m: float,
               efficiency: float) -> CalcResult:
    if not 0 < efficiency <= 1:
        if 1 < efficiency <= 100:
            efficiency = efficiency / 100.0
        else:
            raise ValueError("efficiency must be a fraction 0-1 or a percentage 1-100")

    mass_flow = flow_m3_s * density_kg_m3
    hydraulic_w = density_kg_m3 * G * flow_m3_s * head_m
    shaft_w = hydraulic_w / efficiency

    return CalcResult(
        name="Pump shaft power",
        inputs={
            "volumetric flow": f"{flow_m3_s} m3/s",
            "fluid density": f"{density_kg_m3} kg/m3",
            "total head": f"{head_m} m",
            "efficiency": f"{efficiency:.1%}",
        },
        steps=[
            Step("mass flow rate", "Q x rho", mass_flow, "kg/s"),
            Step("hydraulic power", "rho x g x Q x H", hydraulic_w, "W"),
            Step("hydraulic power", "/ 1000", hydraulic_w / 1000, "kW"),
            Step("shaft power", "P_hyd / eta", shaft_w, "W"),
            Step("shaft power", "/ 1000", shaft_w / 1000, "kW"),
        ],
        value=shaft_w / 1000, unit="kW",
        interpretation=(f"Motor should be rated above {shaft_w/1000:,.2f} kW. "
                        "Apply the site margin, commonly 10 to 15 percent."),
        notes=["Result is in KILOWATTS. rho x g x Q x H yields WATTS; "
               "divide by 1000."],
    )


def wall_thickness_assessment(measured_mm: float, design_minimum_mm: float,
                              nominal_mm: float = 0.0,
                              years_in_service: float = 0.0) -> CalcResult:
    margin = measured_mm - design_minimum_mm
    steps = [
        Step("measured thickness", "t_meas", measured_mm, "mm"),
        Step("design minimum", "t_min", design_minimum_mm, "mm"),
        Step("margin above minimum", "t_meas - t_min", margin, "mm"),
    ]
    notes = []
    value, unit = margin, "mm"

    if nominal_mm and years_in_service:
        loss = nominal_mm - measured_mm
        rate = loss / years_in_service
        steps.append(Step("metal loss", "t_nom - t_meas", loss, "mm"))
        steps.append(Step("corrosion rate", f"loss / {years_in_service} yr",
                          rate, "mm/yr"))
        if rate > 0:
            life = margin / rate
            steps.append(Step("remaining life", "margin / rate", life, "yr"))
            value, unit = life, "yr"
        else:
            notes.append("No measurable metal loss; remaining life not computed.")

    if margin < 0:
        interp = (f"BELOW RETIREMENT LIMIT by {abs(margin):.2f} mm. "
                  "Equipment is not fit for continued service at design "
                  "conditions. Escalate for immediate assessment.")
    elif margin < 0.5:
        interp = f"Only {margin:.2f} mm above the retirement limit. Monitor closely."
    else:
        interp = f"{margin:.2f} mm of margin remains above the design minimum."

    return CalcResult(
        name="Wall thickness assessment",
        inputs={"measured": f"{measured_mm} mm",
                "design minimum": f"{design_minimum_mm} mm",
                "nominal": f"{nominal_mm} mm" if nominal_mm else "not supplied",
                "years in service": years_in_service or "not supplied"},
        steps=steps, value=value, unit=unit,
        interpretation=interp,
        notes=notes or ["Screening calculation. Formal fitness-for-service "
                        "assessment per API 579 remains required."],
    )


CALCULATIONS = {
    "npsh_available": npsh_available,
    "pump_power": pump_power,
    "wall_thickness": wall_thickness_assessment,
}


def engineering_calculation(calculation: str, parameters: dict | str) -> ToolResult:
    import json

    if isinstance(parameters, str):
        try:
            parameters = json.loads(parameters)
        except json.JSONDecodeError:
            return ToolResult(False,
                              f"parameters must be a JSON object, got: {parameters[:120]}",
                              "engineering_calculation")

    fn = CALCULATIONS.get(calculation)
    if fn is None:
        return ToolResult(
            False,
            f"unknown calculation '{calculation}'. Available: "
            f"{', '.join(CALCULATIONS)}",
            "engineering_calculation")

    try:
        result = fn(**{k: float(v) if isinstance(v, (int, float, str)) and
                       str(v).replace(".", "").replace("-", "").isdigit()
                       else v for k, v in parameters.items()})
    except TypeError as e:
        import inspect
        sig = ", ".join(inspect.signature(fn).parameters)
        return ToolResult(False, f"wrong parameters for {calculation}: {e}\n"
                          f"expected: {sig}", "engineering_calculation")
    except ValueError as e:
        return ToolResult(False, str(e), "engineering_calculation")

    return ToolResult(True, result.render(), "engineering_calculation",
                      meta={"value": result.value, "unit": result.unit,
                            "verified": True})


SPECS = [
    ToolSpec(
        name="engineering_calculation",
        description=(
            "Perform a standard refinery engineering calculation using verified "
            "code. ALWAYS use this instead of run_python for these calculations, "
            "because it handles units correctly and shows every step.\n"
            "Available: 'npsh_available' (suction_pressure_bar, vapour_pressure_bar, "
            "density_kg_m3, static_head_m, friction_loss_m); "
            "'pump_power' (flow_m3_s, density_kg_m3, head_m, efficiency); "
            "'wall_thickness' (measured_mm, design_minimum_mm, nominal_mm, "
            "years_in_service)."
        ),
        parameters={
            "type": "object",
            "properties": {
                "calculation": {"type": "string",
                                "description": "npsh_available, pump_power or wall_thickness"},
                "parameters": {"type": "object",
                               "description": "Named numeric parameters for that calculation"},
            },
            "required": ["calculation", "parameters"],
        },
        fn=engineering_calculation,
    ),
]
