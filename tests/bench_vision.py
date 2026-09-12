import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.core.llm import OllamaClient

client = OllamaClient()
BASE = Path(__file__).resolve().parent.parent
SAMPLES = BASE / "data" / "samples"

TASKS = [
    (SAMPLES / "inspection_report.png",
     "Read this inspection report. State the equipment tag, the measured "
     "casing wall thickness, and the bearing temperature. Be brief.",
     "expect: P-101A | 8.2 mm | 82 deg C"),
    (SAMPLES / "pid_extract.png",
     "This is a P&ID extract. List every tag number you can see and what "
     "each represents. Be brief.",
     "expect: P-101A pump | V-204 valve | PI-301 indicator"),
]

CANDIDATES = ["qwen3.5:2b-q4_K_M", "gemma3:4b"]

for img, question, expected in TASKS:
    print("#" * 72)
    print(f"IMAGE: {img.name}   ({expected})")
    print("#" * 72)
    for name in CANDIDATES:
        try:
            client.unload(name)
            time.sleep(2)
            t0 = time.perf_counter()
            res = client.chat_with_image(
                name, question, img,
                options={"num_ctx": 8192, "num_predict": 300, "temperature": 0.1},
                think=False,
                keep_alive="5m",
            )
            ms = round((time.perf_counter() - t0) * 1000)
            gpu = "?"
            for m in client.loaded():
                if m["name"].startswith(name.split(":")[0]):
                    tot, vr = m.get("size", 1), m.get("size_vram", 0)
                    gpu = f"{round(100*vr/tot)}% GPU"
            body = res["content"].strip()
            print(f"\n--- {name}  [{ms} ms | {res['eval_count']} tok | {gpu}]")
            print("    " + (body[:500].replace("\n", "\n    ") if body else "(EMPTY)"))
        except Exception as e:
            print(f"\n--- {name}  FAILED: {type(e).__name__}: {str(e)[:200]}")
    print()

client.close()
print("=== VISION SHOOTOUT v2 COMPLETE ===")
