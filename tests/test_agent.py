import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.agent.loop import Agent

agent = Agent()

TASKS = [
    ("SIMPLE", "What files are available in data/samples?", []),
    ("CALCULATION",
     "A pump moves 0.028 m3/s of crude at density 850 kg/m3 against a head "
     "of 45 m. Efficiency is 72 percent. Calculate the shaft power in kW. "
     "Verify it with Python and show the numbers.", []),
    ("DELEGATED CODE",
     "Write a Python program that calculates NPSH available for a pump with "
     "suction pressure 1.8 bar absolute, vapour pressure 0.35 bar, fluid "
     "density 850 kg/m3, static suction head 3.2 m and friction losses "
     "0.9 m. Use the specialist coding model, then run it.", []),
    ("FLAGSHIP",
     "Read the inspection report at data/samples/inspection_report.png. "
     "Extract the key findings and draft a formal approval note as a Word "
     "document called approval_P101A.docx.", []),
]

for label, task, atts in TASKS:
    print("#" * 74)
    print(f"# {label}")
    print("#" * 74)
    print(f"TASK: {task}\n")

    def show(step):
        if step.kind == "tool":
            flag = "ok " if step.ok else "ERR"
            print(f"  [{step.n}] {flag} {step.tool}({str(step.arguments)[:80]})"
                  f"  {step.elapsed_ms} ms")
            print(f"       obs: {step.observation[:150].replace(chr(10), ' ')}")
        else:
            print(f"  [{step.n}] FINAL  {step.elapsed_ms} ms")

    run = agent.run(task, attachments=atts, on_step=show)

    print(f"\n  router picked:  {run.routing.model_name} "
          f"({run.routing.task_type.value} via {run.routing.method})")
    print(f"  orchestrator:   {run.orchestrator_model}")
    print(f"  delegates:      {run.delegate_models or 'none'}")
    print(f"  steps:     {len(run.steps)}  ({run.stopped_reason})")
    print(f"  total:     {run.total_ms} ms")
    print(f"  artifacts: {run.artifacts or 'none'}")
    print(f"\n  ANSWER:\n    {run.answer[:700].replace(chr(10), chr(10)+'    ')}")
    print()

print("=== AGENT TEST COMPLETE ===")
