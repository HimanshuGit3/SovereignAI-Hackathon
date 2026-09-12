"""Delegate code generation to the specialist coder model.

The orchestrator (qwen3.5:2b-q4_K_M) selects tools. It is not the best
code writer available. qwen2.5-coder:3b writes better code but cannot
emit native tool calls, so it cannot drive the loop.

This tool bridges the two: the orchestrator calls it with a plain-English
spec, the coder model writes the code, and the orchestrator then runs it
through run_python. Two models, each doing what it is good at.

Cost: a model swap. With OLLAMA_MAX_LOADED_MODELS=1 the coder must be
loaded and the orchestrator evicted, then reloaded afterwards. Measured
at roughly 12-20s per swap on a 4GB card. Worth it for real code; not
worth it for one-line arithmetic.
"""
import re

from app.core.llm import OllamaClient
from app.router.registry import ModelRegistry
from app.tools.base import ToolResult, ToolSpec

_client: OllamaClient | None = None
_registry: ModelRegistry | None = None

CODER_PROMPT = """Write Python 3 code for this specification.

Rules:
- Output ONLY code. No explanation, no markdown fences.
- numpy, pandas, scipy and sympy are available.
- No network access, no file I/O.

MANDATORY structure for any engineering calculation:
1. Print every input with its unit.
2. Print the formula being applied, as a comment AND as a printed string.
3. Print EVERY intermediate term separately with its unit.
4. Print the final result last, clearly labelled with its unit.
5. Convert units explicitly and print the conversion. Never mix bar with
   pascal or kPa with Pa silently.

An engineer must be able to check each line against a handbook. A single
final number is not acceptable output.

Specification: {spec}"""


def _lazy():
    global _client, _registry
    if _client is None:
        _client = OllamaClient()
    if _registry is None:
        _registry = ModelRegistry()
    return _client, _registry


def _strip_fences(text: str) -> str:
    m = re.search(r"```(?:python)?\s*\n(.*?)```", text, re.DOTALL)
    if m:
        return m.group(1).strip()
    return text.strip()


def generate_code(specification: str) -> ToolResult:
    client, registry = _lazy()
    spec = registry.by_role("code")

    res = client.chat(
        spec.name,
        [{"role": "user", "content": CODER_PROMPT.format(spec=specification)}],
        options={**registry.options_for(spec.id), "num_predict": 600},
        think=False,
        keep_alive="5m",
    )
    code = _strip_fences(res["content"])

    if not code:
        return ToolResult(False, f"{spec.name} returned no code.",
                          "generate_code")

    return ToolResult(
        True,
        f"Code written by {spec.name} ({res['eval_count']} tokens).\n"
        f"Pass this to run_python to execute it:\n\n{code}",
        "generate_code",
        meta={"delegate_model": spec.name, "code": code},
    )


SPECS = [
    ToolSpec(
        name="generate_code",
        description=(
            "Ask the specialist coding model to write Python for a described "
            "task. Use for non-trivial programs, algorithms or multi-step "
            "engineering calculations. For simple arithmetic, write the code "
            "yourself and call run_python directly. After calling this, you "
            "must call run_python to actually execute the code."
        ),
        parameters={
            "type": "object",
            "properties": {
                "specification": {
                    "type": "string",
                    "description": "Plain English description of what the code must do.",
                },
            },
            "required": ["specification"],
        },
        fn=generate_code,
    ),
]
