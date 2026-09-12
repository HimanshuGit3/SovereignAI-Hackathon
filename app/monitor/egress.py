"""Egress audit: record every network destination this process contacts.

Implemented by patching httpx at the transport layer, so it captures
calls from anywhere in the application, including libraries we did not
write. Each destination is classified against an allowlist of local
addresses; anything else is flagged EXTERNAL.

This is the application's own account of its behaviour. It is necessary
but not sufficient as proof - see monitor/capture.py for the independent
kernel-level view, which does not trust this module at all.
"""
import ipaddress
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime
from urllib.parse import urlparse

import httpx


@dataclass
class EgressEvent:
    ts: str
    host: str
    port: int
    scheme: str
    path: str
    classification: str      # LOCAL | PRIVATE | EXTERNAL
    reason: str
    status: int | None = None
    elapsed_ms: int = 0

    def as_dict(self) -> dict:
        return {
            "ts": self.ts, "host": self.host, "port": self.port,
            "url": f"{self.scheme}://{self.host}:{self.port}{self.path}",
            "classification": self.classification, "reason": self.reason,
            "status": self.status, "elapsed_ms": self.elapsed_ms,
        }


class EgressMonitor:
    """Singleton audit log. Install once at startup."""

    _instance: "EgressMonitor | None" = None
    _lock = threading.Lock()

    def __init__(self) -> None:
        self.events: list[EgressEvent] = []
        self._installed = False
        self._orig_handle = None

    @classmethod
    def instance(cls) -> "EgressMonitor":
        with cls._lock:
            if cls._instance is None:
                cls._instance = cls()
        return cls._instance

    @staticmethod
    def classify(host: str) -> tuple[str, str]:
        if host in ("localhost", "127.0.0.1", "::1"):
            return "LOCAL", "loopback interface"
        try:
            ip = ipaddress.ip_address(host)
        except ValueError:
            return "EXTERNAL", f"hostname '{host}' requires DNS resolution"

        if ip.is_loopback:
            return "LOCAL", "loopback address"
        if ip.is_private:
            if str(ip).startswith("10.0.2."):
                return "PRIVATE", "VirtualBox NAT gateway (same physical host)"
            if str(ip).startswith("192.168.59."):
                return "PRIVATE", "VirtualBox host-only segment (no internet route)"
            if str(ip).startswith("172.17."):
                return "PRIVATE", "Docker bridge (local containers)"
            return "PRIVATE", "RFC1918 private address"
        return "EXTERNAL", "routable public address"

    def record(self, url: str, status: int | None, elapsed_ms: int) -> EgressEvent:
        p = urlparse(url)
        host = p.hostname or "unknown"
        port = p.port or (443 if p.scheme == "https" else 80)
        cls_, reason = self.classify(host)
        ev = EgressEvent(
            ts=datetime.now().isoformat(timespec="milliseconds"),
            host=host, port=port, scheme=p.scheme or "http",
            path=p.path or "/", classification=cls_, reason=reason,
            status=status, elapsed_ms=elapsed_ms,
        )
        self.events.append(ev)
        return ev

    def install(self) -> None:
        """Patch httpx so every request in this process is recorded."""
        if self._installed:
            return
        monitor = self
        transport_cls = httpx.HTTPTransport
        self._orig_handle = transport_cls.handle_request

        def patched(self_t, request):
            t0 = time.perf_counter()
            status = None
            try:
                response = monitor._orig_handle(self_t, request)
                status = response.status_code
                return response
            finally:
                monitor.record(str(request.url), status,
                               round((time.perf_counter() - t0) * 1000))

        transport_cls.handle_request = patched
        self._installed = True

    def summary(self) -> dict:
        counts = {"LOCAL": 0, "PRIVATE": 0, "EXTERNAL": 0}
        for e in self.events:
            counts[e.classification] = counts.get(e.classification, 0) + 1
        return {
            "total_requests": len(self.events),
            "by_classification": counts,
            "external_count": counts["EXTERNAL"],
            "sovereign": counts["EXTERNAL"] == 0,
            "destinations": sorted({f"{e.host}:{e.port}" for e in self.events}),
        }

    def render(self, limit: int = 40) -> str:
        s = self.summary()
        lines = [
            "=" * 74,
            "EGRESS AUDIT - every network call made by this process",
            "=" * 74,
            f"  total requests : {s['total_requests']}",
            f"  loopback       : {s['by_classification']['LOCAL']}",
            f"  private/LAN    : {s['by_classification']['PRIVATE']}",
            f"  EXTERNAL       : {s['external_count']}",
            "",
            f"  VERDICT: {'SOVEREIGN - no external calls' if s['sovereign'] else 'VIOLATION - external calls detected'}",
            "",
            "  destinations contacted:",
        ]
        for d in s["destinations"]:
            host = d.rsplit(":", 1)[0]
            c, reason = self.classify(host)
            lines.append(f"    [{c:<8}] {d:<28} {reason}")
        lines += ["", "  recent calls:"]
        for e in self.events[-limit:]:
            flag = "!!" if e.classification == "EXTERNAL" else "  "
            lines.append(f"  {flag} {e.ts[11:]} {e.classification:<8} "
                         f"{e.host}:{e.port}{e.path[:34]} -> {e.status} "
                         f"({e.elapsed_ms} ms)")
        lines.append("=" * 74)
        return "\n".join(lines)

    def reset(self) -> None:
        self.events.clear()


def install_monitor() -> EgressMonitor:
    m = EgressMonitor.instance()
    m.install()
    return m
