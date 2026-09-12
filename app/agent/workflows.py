"""Scripted workflows for known task shapes.

Measured behaviour on this hardware: the open-ended agent completes a
3-step task reliably and degrades at 6+ steps, where it invents file
paths, mixes up tool signatures, and on one run fabricated pump
parameters (0.8 m3/s, 120 m head) that appeared in no source document.

So for task shapes we know in advance, the PIPELINE owns the sequence and
the MODEL owns the content. The model still extracts findings, writes the
background, and phrases the recommendation - it simply does not choose
what step comes next. The open-ended agent remains available for
everything else.

This mirrors production practice: constrain the plan where the plan is
known, and let the model do the language work it is actually good at.
"""
import json
import re
import time
from dataclasses import dataclass, field
from pathlib import Path

from app.core.llm import OllamaClient
from app.rag.answer import KnowledgeBase
from app.router.registry import ModelRegistry
from app.tools import ToolBox, build_toolbox


@dataclass
class Stage:
    n: int
    name: str
    detail: str = ""
    ok: bool = True
    elapsed_ms: int = 0
    output: str = ""


@dataclass
class WorkflowRun:
    workflow: str
    stages: list[Stage] = field(default_factory=list)
    artifacts: list[str] = field(default_factory=list)
    summary: str = ""
    total_ms: int = 0
    failed: str = ""

    def as_dict(self) -> dict:
        return {
            "workflow": self.workflow,
            "stages": [{"n": s.n, "name": s.name, "detail": s.detail,
                        "ok": s.ok, "elapsed_ms": s.elapsed_ms}
                       for s in self.stages],
            "artifacts": self.artifacts,
            "summary": self.summary,
            "total_ms": self.total_ms,
            "failed": self.failed,
        }


EXTRACT_PROMPT = """Extract structured data from this inspection report.

Return ONLY a JSON object. No markdown fences, no commentary.

{{
  "equipment_tag": "the equipment tag exactly as printed",
  "unit": "the process unit",
  "report_number": "the report reference number",
  "inspection_date": "the inspection date",
  "criticality": "HIGH, MEDIUM or LOW exactly as stated",
  "findings": ["each finding, copied word for word from the report"],
  "recommendation": "the recommendation, copied word for word"
}}

Copy every value exactly as it appears. Do not round numbers, do not
reword, do not summarise. If a field is absent, use "not stated".

REPORT TEXT:
{text}"""

NOTE_PROMPT = """Write the BACKGROUND paragraph for a formal approval note.

Source inspection report: {report_number}
Equipment: {tag} in {unit}
Inspected: {date}
Criticality: {criticality}

Organisational requirement retrieved from our SOPs:
{sop_answer}

What is being approved: the SHUTDOWN of this equipment and the corrective
work in the recommendation below. Not the inspection, which is complete.

Recommendation from the report: {recommendation}

Write 3 to 4 sentences of plain formal prose. State that approval is
sought to shut down the equipment and carry out the recommended work,
cite the report number, and state the approval requirement from the SOP
text above. Quote all figures exactly. No bullet points, no headings,
no markdown. Output the paragraph only."""


def _json_from(text: str) -> dict:
    text = re.sub(r"```(?:json)?", "", text).strip()
    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end == -1:
        raise ValueError(f"no JSON object in model output: {text[:180]}")
    return json.loads(text[start:end + 1])


class InspectionToApprovalWorkflow:
    """Scanned inspection report -> SOP lookup -> Word approval note.

    Exactly four stages, fixed order, no tool selection by the model.
    """

    NAME = "inspection_to_approval"

    def __init__(self, client: OllamaClient | None = None,
                 registry: ModelRegistry | None = None,
                 toolbox: ToolBox | None = None,
                 kb: KnowledgeBase | None = None):
        self.client = client or OllamaClient()
        self.registry = registry or ModelRegistry()
        self.toolbox = toolbox or build_toolbox()
        self.kb = kb or KnowledgeBase()

    def _model(self):
        spec = self.registry.by_role("general")
        return spec, self.registry.options_for(spec.id)

    def run(self, document_path: str, output_filename: str = "approval_note.docx",
            on_stage=None) -> WorkflowRun:
        run = WorkflowRun(workflow=self.NAME)
        t_start = time.perf_counter()
        spec, options = self._model()

        def stage(n, name, fn):
            t0 = time.perf_counter()
            st = Stage(n=n, name=name)
            try:
                st.detail, payload = fn()
            except Exception as e:
                st.ok = False
                st.detail = f"{type(e).__name__}: {e}"
                payload = None
            st.elapsed_ms = round((time.perf_counter() - t0) * 1000)
            run.stages.append(st)
            if on_stage:
                on_stage(st)
            return st, payload

        # 1. Ingest
        def _ingest():
            res = self.toolbox.call("read_document", {"path": document_path})
            if not res.ok:
                raise RuntimeError(res.output)
            return (f"{res.meta.get('method')} in {res.elapsed_ms} ms, "
                    f"{len(res.output)} chars"), res.output

        st, text = stage(1, "ingest document", _ingest)
        if not st.ok:
            run.failed = st.detail
            run.total_ms = round((time.perf_counter() - t_start) * 1000)
            return run

        # 2. Structured extraction
        def _extract():
            res = self.client.chat(
                spec.name,
                [{"role": "user", "content": EXTRACT_PROMPT.format(text=text[:6000])}],
                options={**options, "temperature": 0.0, "num_predict": 700},
                think=False, keep_alive="15m")
            data = _json_from(res["content"])
            return (f"{data.get('equipment_tag')} | {data.get('criticality')} | "
                    f"{len(data.get('findings', []))} findings"), data

        st, data = stage(2, "extract structured fields", _extract)
        if not st.ok:
            run.failed = st.detail
            run.total_ms = round((time.perf_counter() - t_start) * 1000)
            return run

        # 3. SOP lookup - question built by the pipeline, not the model
        def _sop():
            crit = str(data.get("criticality", "HIGH")).upper()
            q = (f"Who must approve a shutdown for {crit} criticality "
                 f"equipment, and within how many days must it be scheduled?")
            a = self.kb.ask(q)
            # Only chunks within 0.12 of the top score plausibly informed
            # the answer. Listing every retrieved chunk as a governing
            # procedure cites documents that had no bearing on it.
            used = [c for c in a.chunks if a.top_score - c.score <= 0.12][:3]
            cites = ", ".join(c.citation() for c in used)
            return (f"top {a.top_score:.3f} {cites}"),                    {"answer": a.answer, "citations": [c.citation() for c in used],
                    "confident": a.confident}

        st, sop = stage(3, "consult SOPs", _sop)
        if not st.ok:
            sop = {"answer": "SOP lookup unavailable.", "citations": [],
                   "confident": False}

        # 4. Generate the document
        def _write():
            res = self.client.chat(
                spec.name,
                [{"role": "user", "content": NOTE_PROMPT.format(
                    report_number=data.get("report_number", "not stated"),
                    tag=data.get("equipment_tag", "not stated"),
                    unit=data.get("unit", "not stated"),
                    date=data.get("inspection_date", "not stated"),
                    criticality=data.get("criticality", "not stated"),
                    recommendation=data.get("recommendation", "not stated"),
                    sop_answer=sop["answer"])}],
                options={**options, "num_predict": 400},
                think=False, keep_alive="15m")
            background = res["content"].strip()

            cite_line = ("\n\nGoverning procedure: " + ", ".join(sop["citations"])
                         if sop["citations"] else "")

            tool_res = self.toolbox.call("create_word_document", {
                "filename": output_filename,
                "title": f"Approval Note - {data.get('equipment_tag', 'Equipment')}",
                "subject": str(data.get("recommendation", ""))[:160],
                "reference": data.get("report_number", ""),
                "background": background + cite_line,
                "findings": data.get("findings", []),
                "recommendation": data.get("recommendation", ""),
                "approval_sought": sop["answer"],
            })
            if not tool_res.ok:
                raise RuntimeError(tool_res.output)
            run.artifacts.extend(tool_res.artifacts)
            return tool_res.output, background

        st, _ = stage(4, "draft approval note", _write)
        if not st.ok:
            run.failed = st.detail

        run.total_ms = round((time.perf_counter() - t_start) * 1000)
        run.summary = (
            f"Processed {Path(document_path).name}: "
            f"{data.get('equipment_tag')} ({data.get('criticality')} criticality), "
            f"{len(data.get('findings', []))} findings, "
            f"grounded in {len(sop.get('citations', []))} SOP section(s). "
            f"Output: {', '.join(run.artifacts) or 'none'}")
        return run


WORKFLOWS = {InspectionToApprovalWorkflow.NAME: InspectionToApprovalWorkflow}
