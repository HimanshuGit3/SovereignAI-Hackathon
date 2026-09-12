import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.core.llm import OllamaClient
from app.router.registry import ModelRegistry

client = OllamaClient()
reg = ModelRegistry()

gen = reg.by_role("general").name
cod = reg.by_role("code").name
vis = reg.by_role("vision").name

print("--- COLD LOAD (model not in VRAM) ---")
for name in (gen, cod, vis):
    client.unload(name)
    time.sleep(1)
    ms = client.warm(name, keep_alive="5m")
    print(f"  {name:<22} cold load: {ms:>6} ms")

print("\n--- WARM CALL (model already in VRAM) ---")
ms = client.warm(gen, keep_alive="5m")
print(f"  {gen:<22} warm call: {ms:>6} ms")
ms = client.warm(gen, keep_alive="5m")
print(f"  {gen:<22} warm call: {ms:>6} ms")

print("\n--- CURRENTLY RESIDENT IN VRAM ---")
for m in client.loaded():
    size_gb = m.get("size", 0) / 1e9
    vram_gb = m.get("size_vram", 0) / 1e9
    print(f"  {m['name']:<22} total {size_gb:.2f} GB | on GPU {vram_gb:.2f} GB")

print("\n--- CAN TWO MODELS COEXIST? ---")
client.warm(gen, keep_alive="5m")
client.warm(cod, keep_alive="5m")
resident = client.loaded()
print(f"  models resident after loading both: {len(resident)}")
for m in resident:
    print(f"    {m['name']} -> GPU {m.get('size_vram', 0)/1e9:.2f} GB")

client.close()
print("\n=== BENCHMARK COMPLETE ===")
