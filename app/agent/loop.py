"""Plan / act / observe agent loop.

Design constraints, all derived from measurements on this hardware:

1. Model is pinned for the whole task. Cold loads cost 12-20s with
   OLLAMA_MAX_LOADED_MODELS=1, so swapping mid-loop is unaffordable.
2. Only models with the 'orchestrator' capability may drive the loop.
   qwen2.5-coder:3b emits tool calls as plain text and was excluded
   after testing.
3. Every step is recorded. The trace is the product: judges need to
   SEE the plan/act/observe cycle, not be told it happened.
"""
import time
from dataclasses import dataclass, field
from typing import Callable

from app.core.llm import OllamaClient
from app.core.schemas import RoutingDecision
from app.router.classifier import TaskRouter
from app.router.registry import ModelRegistry
from app.tools import ToolBox, build_toolbox

MAX_STEPS = 8

SYSTEM_PROMPT = """You are an on-premise engineering assistant for a refinery.
You run entirely on local hardware. No data ever leaves the premises.

You have tools. Use them instead of guessing.

RULES
- To answer anything about a file, call read_document first. Never invent
  its contents.
- Never invent a file path. If unsure what exists, call list_files.
- For NPSH, pump power or wall thickness, call engineering_calculation.
  Those use verified code with correct unit handling. Never compute them
  with run_python or in your head.
- For other arithmetic, call run_python and print the result.
- engineering_calculation parameter names are EXACT. Copy them from the
  tool description. Do not rename or expand them.
- generate_code is for multi-step programs only, never for a formula that
  engineering_calculation already covers.
- Report units EXACTLY as the tool returns them. Never relabel a result.
- When asked for a Word file, approval note or office note, call
  create_word_document. Populate it from data you actually retrieved.
- Quote figures exactly as they appear in the source. Do not round or
  paraphrase measurements.
- When the task is complete, reply with a plain summary and no tool call.

Work in small steps. One tool call at a time."""


@dataclass
class AgentStep:
    n: int
    kind: str           # "tool" | "final"
    tool: str = ""
    arguments: dict = field(default_factory=dict)
    ok: bool = True
    observation: str = ""
    content: str = ""
    elapsed_ms: int = 0
    tokens: int = 0
    model: str = ""


@dataclass
class AgentRun:
    task: str
    routing: RoutingDecision
    orchestrator_model: str = ""
    delegate_models: list[str] = field(default_factory=list)
    tools_offered: list[str] = field(default_factory=list)
    steps: list[AgentStep] = field(default_factory=list)
    answer: str = ""
    artifacts: list[str] = field(default_factory=list)
    total_ms: int = 0
    stopped_reason: str = ""

    def as_dict(self) -> dict:
        return {
            "task": self.task,
            "routing": self.routing.as_dict(),
            "orchestrator_model": self.orchestrator_model,
            "tools_offered": self.tools_offered,
            "delegate_models": self.delegate_models,
            "models_used": sorted({s.model for s in self.steps if s.model}),
            "steps": len(self.steps),
            "tool_calls": [s.tool for s in self.steps if s.kind == "tool"],
            "artifacts": self.artifacts,
            "total_ms": self.total_ms,
            "stopped_reason": self.stopped_reason,
            "answer": self.answer,
        }


class Agent:
    def __init__(
        self,
        client: OllamaClient | None = None,
        registry: ModelRegistry | None = None,
        toolbox: ToolBox | None = None,
        router: TaskRouter | None = None,
        max_steps: int = MAX_STEPS,
    ):
        self.client = client or OllamaClient()
        self.registry = registry or ModelRegistry()
        self.toolbox = toolbox or build_toolbox()
        self.router = router or TaskRouter(self.registry, self.client)
        self.max_steps = max_steps

    def _orchestrator(self):
        """Pick a tool-capable model, never a text-only one."""
        for spec in self.registry.all():
            if spec.supports("orchestrator"):
                return spec
        return self.registry.by_role("general")

    TOOLS_BY_TASK = {
        "chat": ["list_files", "read_document"],
        "document": ["list_files", "read_document", "engineering_calculation",
                     "create_word_document", "write_text_file"],
        "code": ["engineering_calculation", "run_python", "generate_code",
                 "write_text_file"],
        "vision": ["list_files", "read_document", "create_word_document"],
    }

    def _tools_for(self, task_type: str) -> list[dict]:
        allowed = self.TOOLS_BY_TASK.get(task_type)
        if not allowed:
            return self.toolbox.schemas()
        out = []
        for schema in self.toolbox.schemas():
            if schema["function"]["name"] in allowed:
                out.append(schema)
        return out or self.toolbox.schemas()

    def run(self, task: str, attachments: list[str] | None = None,
            on_step: Callable[[AgentStep], None] | None = None) -> AgentRun:
        t_start = time.perf_counter()

        routing = self.router.route(task, attachments=attachments)
        spec = self._orchestrator()
        options = self.registry.options_for(spec.id)

        # The router decides which tools are OFFERED. A document task does
        # not need generate_code; a chat task needs no tools at all. This
        # makes the routing decision materially change execution instead of
        # being a label, and it shortens the prompt the model must reason over.
        schemas = self._tools_for(routing.task_type.value)

        user_msg = task
        if attachments:
            user_msg += "\n\nAttached files:\n" + "\n".join(
                f"- {a}" for a in attachments)

        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_msg},
        ]

        run = AgentRun(task=task, routing=routing,
                       orchestrator_model=spec.name)
        run.tools_offered = [s["function"]["name"] for s in schemas]

        for n in range(1, self.max_steps + 1):
            t0 = time.perf_counter()
            try:
                res = self.client.chat(
                    spec.name, messages,
                    options={**options, "num_predict": 700},
                    think=False, keep_alive="15m", tools=schemas,
                )
            except Exception as e:
                run.stopped_reason = f"model error: {type(e).__name__}: {e}"
                break

            ms = round((time.perf_counter() - t0) * 1000)
            calls = res["tool_calls"]

            if not calls:
                step = AgentStep(n=n, kind="final", content=res["content"].strip(),
                                 elapsed_ms=ms, tokens=res["eval_count"],
                                 model=spec.name)
                run.steps.append(step)
                if on_step:
                    on_step(step)
                run.answer = step.content
                run.stopped_reason = "model returned a final answer"
                break

            messages.append(res["raw_message"])

            for call in calls:
                name, args = call["name"], call["arguments"]
                result = self.toolbox.call(name, args)

                step = AgentStep(
                    n=n, kind="tool", tool=name, arguments=args,
                    ok=result.ok, observation=result.output,
                    elapsed_ms=ms + result.elapsed_ms,
                    tokens=res["eval_count"],
                    model=spec.name,
                )
                if result.meta.get("delegate_model"):
                    dm = result.meta["delegate_model"]
                    if dm not in run.delegate_models:
                        run.delegate_models.append(dm)
                run.steps.append(step)
                if on_step:
                    on_step(step)

                for a in result.artifacts:
                    if a not in run.artifacts:
                        run.artifacts.append(a)

                messages.append({
                    "role": "tool",
                    "content": result.for_model(limit=3500),
                })
        else:
            run.stopped_reason = f"hit the {self.max_steps}-step limit"

        if not run.answer and run.steps:
            last = run.steps[-1]
            run.answer = last.content or (
                f"Stopped after {len(run.steps)} steps "
                f"({run.stopped_reason}). Last tool: {last.tool}.")

        run.total_ms = round((time.perf_counter() - t_start) * 1000)
        return run
