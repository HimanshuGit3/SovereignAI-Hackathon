import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.core.llm import OllamaClient
from app.router.registry import ModelRegistry
from app.tools import build_toolbox

client = OllamaClient()
reg = ModelRegistry()
box = build_toolbox()
schemas = box.schemas()

print(f"{len(schemas)} tool schemas offered\n")

PROMPTS = [
    "List the files in data/samples",
    "Read the document at data/samples/inspection_report.png",
    "Calculate 847 * 1293 using Python and tell me the result",
    "What is the capital of France?",
]

for model_role in ("general", "code"):
    spec = reg.by_role(model_role)
    print("#" * 70)
    print(f"# {spec.name}  (role={model_role})")
    print("#" * 70)
    for prompt in PROMPTS:
        try:
            res = client.chat(
                spec.name,
                [{"role": "user", "content": prompt}],
                options={**reg.options_for(spec.id), "num_predict": 300},
                think=False, keep_alive="10m", tools=schemas,
            )
            calls = res["tool_calls"]
            print(f"\n  PROMPT: {prompt}")
            if calls:
                for c in calls:
                    print(f"    -> CALL {c['name']}({json.dumps(c['arguments'])[:110]})")
            else:
                print(f"    -> NO CALL, text: {res['content'].strip()[:110]}")
        except Exception as e:
            print(f"\n  PROMPT: {prompt}\n    FAILED: {type(e).__name__}: {str(e)[:150]}")
    print()

client.close()
print("=== TOOL CALL TEST COMPLETE ===")
