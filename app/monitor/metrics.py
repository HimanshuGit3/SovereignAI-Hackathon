"""Host and session metrics for the dashboard.

Read straight from /proc rather than adding psutil: fewer dependencies
in an air-gapped deployment, and the values are the kernel's own.

Run history is kept in memory only. It is operational telemetry, not
user data, and nothing about it should outlive the process.
"""
import shutil
import time
from collections import deque
from pathlib import Path

from app.config import BASE_DIR

_runs: deque = deque(maxlen=60)
_started = time.time()


def record_run(entry: dict) -> None:
    entry["at"] = time.time()
    _runs.append(entry)


def runs() -> list[dict]:
    return list(_runs)


def _meminfo() -> dict:
    out = {}
    try:
        for line in Path("/proc/meminfo").read_text().splitlines():
            k, _, v = line.partition(":")
            out[k] = int(v.strip().split()[0]) * 1024
    except OSError:
        pass
    return out


_prev_cpu = {"idle": 0, "total": 0}


def _cpu_percent() -> float:
    try:
        parts = Path("/proc/stat").read_text().split("\n")[0].split()[1:]
        vals = [int(p) for p in parts]
    except (OSError, ValueError):
        return 0.0
    idle = vals[3] + (vals[4] if len(vals) > 4 else 0)
    total = sum(vals)
    d_idle = idle - _prev_cpu["idle"]
    d_total = total - _prev_cpu["total"]
    _prev_cpu["idle"], _prev_cpu["total"] = idle, total
    if d_total <= 0:
        return 0.0
    return round(100 * (1 - d_idle / d_total), 1)


def snapshot() -> dict:
    mem = _meminfo()
    total = mem.get("MemTotal", 0)
    avail = mem.get("MemAvailable", 0)
    used = total - avail
    du = shutil.disk_usage(BASE_DIR)

    try:
        load1, load5, load15 = (float(x) for x in
                                Path("/proc/loadavg").read_text().split()[:3])
    except (OSError, ValueError):
        load1 = load5 = load15 = 0.0

    rs = runs()
    ok = [r for r in rs if r.get("ok")]

    # Signals specific to this system rather than to any server.
    routing = {"deterministic": 0, "llm": 0}
    by_type: dict[str, int] = {}
    by_model: dict[str, int] = {}
    ingest = {"ocr": 0, "vision": 0, "native_pdf": 0, "plain_text": 0}
    retrieval = {"answered": 0, "refused": 0}
    verified_calcs = 0
    sandbox_runs = 0
    deliverables = 0
    swaps = 0

    for r in rs:
        method = r.get("routing_method")
        if method in routing:
            routing[method] += 1
        tt = r.get("task_type")
        if tt:
            by_type[tt] = by_type.get(tt, 0) + 1
        mdl = r.get("model")
        if mdl:
            by_model[mdl] = by_model.get(mdl, 0) + 1
        for k in r.get("ingest_methods", []):
            if k in ingest:
                ingest[k] += 1
        retrieval["answered"] += r.get("kb_answered", 0)
        retrieval["refused"] += r.get("kb_refused", 0)
        verified_calcs += r.get("verified_calcs", 0)
        sandbox_runs += r.get("sandbox_runs", 0)
        deliverables += len(r.get("artifacts", []))
        swaps += r.get("model_swaps", 0)
    durations = [r["total_ms"] for r in rs if r.get("total_ms")]
    tools: dict[str, int] = {}
    for r in rs:
        for t in r.get("tools", []):
            tools[t] = tools.get(t, 0) + 1

    return {
        "uptime_s": round(time.time() - _started),
        "cpu_percent": _cpu_percent(),
        "load": {"1m": load1, "5m": load5, "15m": load15},
        "memory": {
            "total_gb": round(total / 1e9, 2),
            "used_gb": round(used / 1e9, 2),
            "percent": round(100 * used / total, 1) if total else 0,
        },
        "disk": {
            "total_gb": round(du.total / 1e9, 1),
            "used_gb": round(du.used / 1e9, 1),
            "percent": round(100 * du.used / du.total, 1),
        },
        "sovereign": {
            "routing": routing,
            "deterministic_pct": (
                round(100 * routing["deterministic"] /
                      (routing["deterministic"] + routing["llm"]))
                if (routing["deterministic"] + routing["llm"]) else None),
            "by_task_type": sorted(by_type.items(), key=lambda kv: -kv[1]),
            "by_model": sorted(by_model.items(), key=lambda kv: -kv[1]),
            "ingest": ingest,
            "retrieval": retrieval,
            "verified_calcs": verified_calcs,
            "sandbox_runs": sandbox_runs,
            "deliverables": deliverables,
            "model_swaps": swaps,
        },
        "runs": {
            "total": len(rs),
            "succeeded": len(ok),
            "success_rate": round(100 * len(ok) / len(rs)) if rs else None,
            "median_ms": sorted(durations)[len(durations) // 2] if durations else None,
            "tool_usage": sorted(tools.items(), key=lambda kv: -kv[1]),
            "recent": [
                {"at": r["at"], "task": r.get("task", "")[:70],
                 "task_type": r.get("task_type"), "steps": r.get("steps"),
                 "total_ms": r.get("total_ms"), "ok": r.get("ok")}
                for r in rs[-18:]
            ],
        },
    }
