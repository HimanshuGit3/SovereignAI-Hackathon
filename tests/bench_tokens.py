import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.core.llm import OllamaClient
from app.router.registry import ModelRegistry

client = OllamaClient()
reg = ModelRegistry()

PROMPT = (
    "List five common failure modes of a centrifugal pump in a refinery. "
    "One short line each, no preamble."
)

print(f"{'MODEL':<24}{'load_ms':>9}{'gen_ms':>9}{'tokens':>8}{'tok/s':>9}")
print("-" * 60)

for role in ("router", "general", "code"):
    spec = reg.by_role(role)
    opts = dict(reg.options_for(spec.id))
    opts["num_predict"] = 120

    client.unload(spec.name)
    time.sleep(2)

    t0 = time.perf_counter()
    client.chat(spec.name, [{"role": "user", "content": "hi"}],
                options={"num_predict": 1}, think=False, keep_alive="10m")
    load_ms = round((time.perf_counter() - t0) * 1000)

    t1 = time.perf_counter()
    res = client.chat(spec.name, [{"role": "user", "content": PROMPT}],
                      options=opts, think=False, keep_alive="10m")
    gen_ms = round((time.perf_counter() - t1) * 1000)

    toks = res["eval_count"]
    rate = round(toks / (gen_ms / 1000), 1) if gen_ms else 0
    print(f"{spec.name:<24}{load_ms:>9}{gen_ms:>9}{toks:>8}{rate:>9}")

print("\n--- SAMPLE OUTPUT (general) ---")
g = reg.by_role("general")
r = client.chat(g.name, [{"role": "user", "content": PROMPT}],
                options={**reg.options_for(g.id), "num_predict": 200},
                think=False, keep_alive="10m")
print(r["content"].strip()[:600])

client.close()
print("\n=== DONE ===")
