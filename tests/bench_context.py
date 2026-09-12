import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.core.llm import OllamaClient

client = OllamaClient()

MODELS = ["qwen3.5:0.8b", "qwen3.5:2b-q4_K_M", "qwen2.5-coder:3b", "gemma3:4b"]
CONTEXTS = [2048, 4096, 8192, 16384]
PROMPT = ("List five common failure modes of a centrifugal pump. "
          "One short line each, no preamble.")


def gpu_fraction(name):
    for m in client.loaded():
        if m["name"].startswith(name.split(":")[0]):
            total = m.get("size", 0)
            vram = m.get("size_vram", 0)
            if total:
                return round(100 * vram / total), round(vram / 1e9, 2)
    return None, None


print(f"{'MODEL':<22}{'ctx':>7}{'tok/s':>9}{'GPU%':>7}{'VRAM_GB':>9}")
print("-" * 56)

for name in MODELS:
    for ctx in CONTEXTS:
        try:
            client.unload(name)
            time.sleep(2)
            client.chat(name, [{"role": "user", "content": "hi"}],
                        options={"num_ctx": ctx, "num_predict": 1},
                        think=False, keep_alive="5m")
            time.sleep(1)
            pct, vram = gpu_fraction(name)

            t0 = time.perf_counter()
            res = client.chat(name, [{"role": "user", "content": PROMPT}],
                              options={"num_ctx": ctx, "num_predict": 100},
                              think=False, keep_alive="5m")
            ms = (time.perf_counter() - t0) * 1000
            toks = res["eval_count"]
            rate = round(toks / (ms / 1000), 1) if ms else 0

            print(f"{name:<22}{ctx:>7}{rate:>9}{str(pct):>7}{str(vram):>9}")
        except Exception as e:
            print(f"{name:<22}{ctx:>7}   FAILED: {type(e).__name__}")
    print()

client.unload("gemma3:4b")
client.close()
print("=== CONTEXT SWEEP COMPLETE ===")
