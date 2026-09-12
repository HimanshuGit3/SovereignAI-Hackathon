"""Tool contract for the agent loop.

Every tool returns a ToolResult, never raises. A 2B model cannot recover
from a Python traceback, but it can read "error: file not found" and try
a different path. Failures must be data, not exceptions.
"""
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

from app.config import BASE_DIR

# The agent may only touch paths under these roots.
ALLOWED_ROOTS = [
    (BASE_DIR / "data").resolve(),
    (BASE_DIR / "outputs").resolve(),
]


@dataclass
class ToolResult:
    ok: bool
    output: str
    tool: str
    elapsed_ms: int = 0
    artifacts: list[str] = field(default_factory=list)
    meta: dict = field(default_factory=dict)

    def as_dict(self) -> dict:
        return {
            "ok": self.ok,
            "tool": self.tool,
            "output": self.output,
            "elapsed_ms": self.elapsed_ms,
            "artifacts": self.artifacts,
        }

    def for_model(self, limit: int = 4000) -> str:
        """Rendered back into the conversation as an observation."""
        status = "SUCCESS" if self.ok else "ERROR"
        body = self.output[:limit]
        if len(self.output) > limit:
            body += f"\n...[truncated, {len(self.output)} chars total]"
        extra = ""
        if self.artifacts:
            extra = f"\nFILES CREATED: {', '.join(self.artifacts)}"
        return f"[{self.tool} -> {status}]\n{body}{extra}"


class ToolError(Exception):
    pass


def safe_path(raw: str, must_exist: bool = False) -> Path:
    """Resolve a path and refuse anything outside ALLOWED_ROOTS.

    Blocks directory traversal. An agent that can be talked into reading
    /etc/shadow is not a sovereign workbench.
    """
    p = Path(raw)
    if not p.is_absolute():
        p = (BASE_DIR / p)
    p = p.resolve()

    if not any(p == root or root in p.parents for root in ALLOWED_ROOTS):
        allowed = ", ".join(str(r) for r in ALLOWED_ROOTS)
        raise ToolError(f"path '{raw}' is outside permitted roots ({allowed})")

    if must_exist and not p.exists():
        raise ToolError(f"path does not exist: {p}")
    return p


@dataclass
class ToolSpec:
    name: str
    description: str
    parameters: dict
    fn: Callable[..., ToolResult]

    def to_ollama_schema(self) -> dict:
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters,
            },
        }


class ToolBox:
    def __init__(self) -> None:
        self._tools: dict[str, ToolSpec] = {}

    def register(self, spec: ToolSpec) -> None:
        self._tools[spec.name] = spec

    def get(self, name: str) -> ToolSpec | None:
        return self._tools.get(name)

    def names(self) -> list[str]:
        return list(self._tools)

    def schemas(self) -> list[dict]:
        return [t.to_ollama_schema() for t in self._tools.values()]

    def describe(self) -> str:
        lines = []
        for t in self._tools.values():
            props = t.parameters.get("properties", {})
            args = ", ".join(f"{k}: {v.get('type','any')}" for k, v in props.items())
            lines.append(f"- {t.name}({args})\n    {t.description}")
        return "\n".join(lines)

    def call(self, name: str, arguments: dict[str, Any]) -> ToolResult:
        import time
        spec = self.get(name)
        if spec is None:
            return ToolResult(
                False,
                f"unknown tool '{name}'. Available: {', '.join(self.names())}",
                name or "unknown",
            )
        t0 = time.perf_counter()
        try:
            res = spec.fn(**arguments)
        except ToolError as e:
            res = ToolResult(False, str(e), name)
        except TypeError as e:
            res = ToolResult(False, f"bad arguments for {name}: {e}", name)
        except Exception as e:
            res = ToolResult(False, f"{type(e).__name__}: {e}", name)
        res.elapsed_ms = round((time.perf_counter() - t0) * 1000)
        return res
