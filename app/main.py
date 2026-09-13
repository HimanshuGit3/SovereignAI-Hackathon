"""SovereignAI Workbench - HTTP API.

The egress monitor is installed on the FIRST line of application import,
before any HTTP client exists anywhere in the process. Anything created
later is captured. Order matters and is not incidental.
"""
from app.monitor.egress import install_monitor  # noqa: E402  (must be first)

EGRESS = install_monitor()

import asyncio  # noqa: E402
import json  # noqa: E402
import queue  # noqa: E402
import shutil  # noqa: E402
import threading  # noqa: E402
from datetime import datetime  # noqa: E402
from pathlib import Path  # noqa: E402

from fastapi import FastAPI, File, HTTPException, UploadFile  # noqa: E402
from fastapi.middleware.cors import CORSMiddleware  # noqa: E402
from fastapi.responses import FileResponse, StreamingResponse  # noqa: E402
from pydantic import BaseModel  # noqa: E402

from app.agent.loop import Agent  # noqa: E402
from app.agent.workflows import WORKFLOWS  # noqa: E402
from app.config import BASE_DIR, settings  # noqa: E402
from app.core.llm import OllamaClient  # noqa: E402
from app.monitor.capture import PacketCapture, classify_ip  # noqa: E402
from app.router.classifier import TaskRouter  # noqa: E402
from app.router.registry import ModelRegistry  # noqa: E402
from app.tools import build_toolbox  # noqa: E402

app = FastAPI(title="SovereignAI Workbench",
              description="On-premise agentic AI for confidential industrial work",
              version="1.0.0")

app.add_middleware(
    CORSMiddleware, allow_origins=["*"], allow_methods=["*"],
    allow_headers=["*"],
)

CLIENT = OllamaClient()
REGISTRY = ModelRegistry()
TOOLBOX = build_toolbox()
ROUTER = TaskRouter(REGISTRY, CLIENT)
AGENT = Agent(CLIENT, REGISTRY, TOOLBOX, ROUTER)

UPLOAD_DIR = BASE_DIR / "data" / "uploads"
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

_capture: PacketCapture | None = None
_capture_lock = threading.Lock()


class TaskRequest(BaseModel):
    task: str
    attachments: list[str] = []


class WorkflowRequest(BaseModel):
    workflow: str = "inspection_to_approval"
    document_path: str
    output_filename: str = "approval_note.docx"


class RouteRequest(BaseModel):
    task: str
    attachments: list[str] = []


@app.get("/api/health")
def health():
    reachable = CLIENT.health()
    available = set(CLIENT.list_models()) if reachable else set()
    models = []
    for spec in REGISTRY.all():
        models.append({
            "id": spec.id, "name": spec.name, "role": spec.role,
            "present": spec.name in available or f"{spec.name}:latest" in available,
        })
    docker_ok = shutil.which("docker") is not None
    return {
        "status": "ok" if reachable else "degraded",
        "inference_endpoint": CLIENT.base_url,
        "inference_reachable": reachable,
        "models": models,
        "sandbox_available": docker_ok,
        "tools": TOOLBOX.names(),
        "timestamp": datetime.now().isoformat(timespec="seconds"),
    }


@app.get("/api/models")
def models():
    """The registry, verbatim. Adding a model means editing YAML only."""
    loaded = {m["name"]: m for m in (CLIENT.loaded() if CLIENT.health() else [])}
    out = []
    for spec in REGISTRY.all():
        entry = loaded.get(spec.name) or loaded.get(f"{spec.name}:latest")
        out.append({
            "id": spec.id, "name": spec.name, "role": spec.role,
            "capabilities": spec.capabilities, "size_gb": spec.size_gb,
            "description": spec.description,
            "options": REGISTRY.options_for(spec.id),
            "resident": entry is not None,
            "vram_gb": round(entry.get("size_vram", 0) / 1e9, 2) if entry else 0,
        })
    return {"registry_file": str(REGISTRY.path), "models": out,
            "fallback": REGISTRY.fallback_id, "rules": REGISTRY.rules}


@app.post("/api/route")
def route(req: RouteRequest):
    """Routing decision only. Fast, and shows the selection reasoning."""
    d = ROUTER.route(req.task, attachments=req.attachments)
    return d.as_dict()


@app.post("/api/task")
def run_task(req: TaskRequest):
    run = AGENT.run(req.task, attachments=req.attachments)
    return {
        **run.as_dict(),
        "steps_detail": [
            {"n": s.n, "kind": s.kind, "tool": s.tool, "ok": s.ok,
             "arguments": s.arguments, "observation": s.observation[:2000],
             "content": s.content, "elapsed_ms": s.elapsed_ms,
             "model": s.model}
            for s in run.steps
        ],
    }


@app.post("/api/task/stream")
async def run_task_stream(req: TaskRequest):
    """Server-sent events: each agent step is pushed as it completes.

    The agent is synchronous, so it runs in a worker thread and posts
    steps onto a queue the event generator drains.
    """
    q: queue.Queue = queue.Queue()

    def on_step(step):
        q.put({
            "type": "step",
            "n": step.n, "kind": step.kind, "tool": step.tool,
            "ok": step.ok, "arguments": step.arguments,
            "observation": step.observation[:1500],
            "content": step.content, "elapsed_ms": step.elapsed_ms,
            "model": step.model,
        })

    def worker():
        try:
            run = AGENT.run(req.task, attachments=req.attachments,
                            on_step=on_step)
            q.put({"type": "done", **run.as_dict()})
        except Exception as e:
            q.put({"type": "error", "error": f"{type(e).__name__}: {e}"})
        finally:
            q.put(None)

    threading.Thread(target=worker, daemon=True).start()

    async def events():
        d = ROUTER.route(req.task, attachments=req.attachments)
        yield f"data: {json.dumps({'type': 'routing', **d.as_dict()})}\n\n"
        while True:
            try:
                item = q.get_nowait()
            except queue.Empty:
                await asyncio.sleep(0.15)
                continue
            if item is None:
                break
            yield f"data: {json.dumps(item)}\n\n"

    return StreamingResponse(events(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache",
                                      "X-Accel-Buffering": "no"})


@app.get("/api/workflows")
def list_workflows():
    return {"workflows": [
        {"name": n, "description": (c.__doc__ or "").strip().split("\n")[0]}
        for n, c in WORKFLOWS.items()]}


@app.post("/api/workflow")
def run_workflow(req: WorkflowRequest):
    cls = WORKFLOWS.get(req.workflow)
    if cls is None:
        raise HTTPException(404, f"unknown workflow '{req.workflow}'. "
                                 f"Available: {', '.join(WORKFLOWS)}")
    wf = cls(CLIENT, REGISTRY, TOOLBOX)
    run = wf.run(req.document_path, req.output_filename)
    return run.as_dict()


@app.get("/api/kb/status")
def kb_status():
    from app.rag.store import VectorStore
    return VectorStore().stats()


@app.post("/api/kb/reindex")
def kb_reindex():
    from app.rag.answer import KnowledgeBase
    kb = KnowledgeBase()
    kb.store.clear()
    results = kb.index_directory(BASE_DIR / "data" / "kb")
    return {"indexed": results, "stats": kb.store.stats()}


@app.post("/api/kb/ask")
def kb_ask(req: RouteRequest):
    from app.rag.answer import KnowledgeBase
    return KnowledgeBase().ask(req.task).as_dict()


@app.get("/api/monitor/egress")
def egress():
    s = EGRESS.summary()
    return {**s, "events": [e.as_dict() for e in EGRESS.events[-60:]],
            "report": EGRESS.render(limit=25)}


@app.post("/api/monitor/egress/reset")
def egress_reset():
    EGRESS.reset()
    return {"ok": True, "events": 0}


@app.post("/api/monitor/capture/start")
def capture_start(interface: str = "any"):
    global _capture
    with _capture_lock:
        if _capture is not None:
            raise HTTPException(409, "a capture is already running")
        cap = PacketCapture(interface)
        if not cap.start():
            raise HTTPException(500, cap.error or "tcpdump failed to start")
        _capture = cap
    return {"ok": True, "interface": interface}


@app.post("/api/monitor/capture/stop")
def capture_stop():
    global _capture
    with _capture_lock:
        if _capture is None:
            raise HTTPException(409, "no capture is running")
        report = _capture.stop()
        _capture = None
    s = report.summary()
    return {**s, "report": report.render(),
            "external_packets": [
                {"ts": p.ts, "dst": p.dst, "dst_port": p.dst_port}
                for p in report.external[:20]
            ]}


@app.get("/api/monitor/classify")
def classify(host: str):
    c, reason = classify_ip(host) if host.replace(".", "").isdigit() \
        else EGRESS.classify(host)
    return {"host": host, "classification": c, "reason": reason}


@app.get("/api/files")
def files():
    def listing(folder: Path, label: str):
        if not folder.exists():
            return []
        return [
            {"name": f.name, "path": str(f.relative_to(BASE_DIR)),
             "size": f.stat().st_size, "area": label,
             "modified": datetime.fromtimestamp(
                 f.stat().st_mtime).isoformat(timespec="seconds")}
            for f in sorted(folder.iterdir())
            if f.is_file() and f.name != ".gitkeep"
        ]

    return {
        "samples": listing(BASE_DIR / "data" / "samples", "sample"),
        "uploads": listing(UPLOAD_DIR, "upload"),
        "outputs": listing(BASE_DIR / "outputs", "output"),
    }


@app.post("/api/upload")
async def upload(file: UploadFile = File(...)):
    name = Path(file.filename or "upload.bin").name
    dest = UPLOAD_DIR / name
    data = await file.read()
    dest.write_bytes(data)
    return {"ok": True, "name": name,
            "path": str(dest.relative_to(BASE_DIR)), "size": len(data)}


@app.get("/api/preview")
def preview(path: str):
    """Serve a sample or uploaded file for display in the UI.

    Scoped to data/ so the endpoint cannot be used to read the filesystem.
    """
    target = (BASE_DIR / path).resolve()
    allowed = (BASE_DIR / "data").resolve()
    if allowed not in target.parents:
        raise HTTPException(403, "outside the data directory")
    if not target.exists():
        raise HTTPException(404, f"no such file: {path}")
    return FileResponse(target)


@app.get("/api/download/{filename}")
def download(filename: str):
    safe = Path(filename).name
    target = BASE_DIR / "outputs" / safe
    if not target.exists():
        raise HTTPException(404, f"no such output file: {safe}")
    return FileResponse(target, filename=safe,
                        media_type="application/octet-stream")


@app.get("/")
def root():
    index = BASE_DIR / "web" / "index.html"
    if index.exists():
        return FileResponse(index)
    return {"service": "SovereignAI Workbench", "docs": "/docs",
            "note": "no UI built yet; web/index.html is missing"}
