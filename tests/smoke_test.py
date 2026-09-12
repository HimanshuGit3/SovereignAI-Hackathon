import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.core.llm import OllamaClient
from app.router.registry import ModelRegistry

client = OllamaClient()
reg = ModelRegistry()

print("=" * 60)
print("OLLAMA ENDPOINT :", client.base_url)
print("REACHABLE       :", client.health())
print("=" * 60)

available = set(client.list_models())
print("\n--- REGISTRY vs OLLAMA ---")
for spec in reg.all():
    mark = "OK " if (spec.name in available or f"{spec.name}:latest" in available) else "MISSING"
    print(f"[{mark}] {spec.id:<12} {spec.name:<22} role={spec.role}")

print("\n--- LIVE GENERATION ---")
for role, prompt in [
    ("router", "Reply with exactly one word: PING"),
    ("general", "In one sentence, what is a piping and instrumentation diagram?"),
    ("code", "Write a Python one-liner that sums a list called nums. Code only."),
]:
    spec = reg.by_role(role)
    opts = reg.options_for(spec.id)
    try:
        res = client.chat(
            spec.name,
            [{"role": "user", "content": prompt}],
            options=opts,
            think=False,
        )
        print(f"\n[{role}] {spec.name}  ({res['total_duration_ms']} ms, {res['eval_count']} tok)")
        print("  ->", res["content"].strip().replace("\n", " ")[:180])
    except Exception as e:
        print(f"\n[{role}] {spec.name} FAILED: {e}")

print("\n--- EMBEDDINGS ---")
emb_spec = reg.by_role("embedding")
try:
    vecs = client.embed(emb_spec.name, "pressure relief valve inspection")
    print(f"[embedding] {emb_spec.name} -> dim={len(vecs[0])}")
except Exception as e:
    print(f"[embedding] FAILED: {e}")

client.close()
print("\n=== SMOKE TEST COMPLETE ===")
