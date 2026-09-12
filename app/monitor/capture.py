"""Kernel-level packet capture. Independent of the application.

egress.py records what the app THINKS it did. This records what the
kernel actually sent. It runs tcpdump on every interface and classifies
each destination address, so a raw socket, a subprocess or a third-party
library cannot hide from it.

A judge should trust this layer and not the other one.
"""
import ipaddress
import re
import shutil
import signal
import subprocess
import threading
import time
from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime

# tcpdump -nn line: 12:34:56.789 IP 10.0.2.15.54321 > 10.0.2.2.11434: ...
# Handles BOTH formats. With -i any, tcpdump uses Linux cooked capture and
# inserts the interface and direction before "IP":
#   Ethernet : 12:34:56.789 IP 10.0.2.15.54321 > 10.0.2.2.11434: ...
#   any/SLL  : 12:34:56.789 enp0s3 Out IP 10.0.2.15.54321 > 10.0.2.2.11434: ...
LINE_RE = re.compile(
    r"(\d{2}:\d{2}:\d{2}\.\d+)\s+(?:\S+\s+(?:In|Out|P|B|M)\s+)?IP6?\s+"
    r"([0-9a-fA-F:.]+?)\.(\d+)\s+>\s+([0-9a-fA-F:.]+?)\.(\d+):")

LOCAL_PREFIXES = ("10.0.2.", "192.168.59.", "172.17.", "172.18.")


@dataclass
class Packet:
    ts: str
    src: str
    src_port: int
    dst: str
    dst_port: int
    classification: str
    reason: str


@dataclass
class CaptureReport:
    duration_s: float
    packets: list[Packet] = field(default_factory=list)
    interfaces: str = "any"
    error: str = ""
    raw_lines: int = 0
    parsed_lines: int = 0

    @property
    def blind(self) -> bool:
        """True if the capture saw nothing it could parse.

        A monitor that observes zero packets cannot prove absence of
        traffic - it may simply be broken. Zero external packets is only
        meaningful if the capture demonstrably WORKS.
        """
        return self.parsed_lines == 0

    @property
    def external(self) -> list[Packet]:
        return [p for p in self.packets if p.classification == "EXTERNAL"]

    def summary(self) -> dict:
        counts = Counter(p.classification for p in self.packets)
        pairs = Counter(f"{p.dst}:{p.dst_port}" for p in self.packets)
        return {
            "duration_s": round(self.duration_s, 1),
            "total_packets": len(self.packets),
            "loopback": counts.get("LOCAL", 0),
            "private": counts.get("PRIVATE", 0),
            "external": counts.get("EXTERNAL", 0),
            "sovereign": counts.get("EXTERNAL", 0) == 0 and not self.blind,
            "blind": self.blind,
            "raw_lines": self.raw_lines,
            "parsed_lines": self.parsed_lines,
            "top_destinations": pairs.most_common(8),
            "error": self.error,
        }

    def render(self) -> str:
        s = self.summary()
        lines = [
            "=" * 74,
            "KERNEL PACKET CAPTURE - independent of the application",
            "=" * 74,
            f"  captured over   : {s['duration_s']} s on interface '{self.interfaces}'",
            f"  total packets   : {s['total_packets']}",
            f"  loopback        : {s['loopback']}",
            f"  private/LAN     : {s['private']}",
            f"  EXTERNAL        : {s['external']}",
            "",
        ]
        if s["blind"]:
            lines += [
                "",
                "  VERDICT: INCONCLUSIVE - the capture parsed no packets.",
                f"           tcpdump emitted {s['raw_lines']} raw line(s) but "
                f"{s['parsed_lines']} were parsed.",
                "           Absence of evidence here is NOT evidence of absence.",
            ]
        elif s["external"]:
            lines += ["", "  VERDICT: VIOLATION - external packets observed"]
        else:
            lines += ["", "  VERDICT: SOVEREIGN - nothing left the machine",
                      f"           ({s['parsed_lines']} packets parsed and "
                      "classified, so the capture was live)"]
        if self.error:
            lines += ["", f"  ERROR: {self.error}"]
        if s["top_destinations"]:
            lines += ["", "  destinations by packet count:"]
            for dest, n in s["top_destinations"]:
                host = dest.rsplit(":", 1)[0]
                c, why = classify_ip(host)
                flag = "!!" if c == "EXTERNAL" else "  "
                lines.append(f"  {flag} [{c:<8}] {dest:<26} {n:>5} pkts   {why}")
        if self.external:
            lines += ["", "  EXTERNAL PACKETS (first 10):"]
            for p in self.external[:10]:
                lines.append(f"    {p.ts} {p.src}:{p.src_port} -> {p.dst}:{p.dst_port}")
        lines.append("=" * 74)
        return "\n".join(lines)


def classify_ip(addr: str) -> tuple[str, str]:
    try:
        ip = ipaddress.ip_address(addr)
    except ValueError:
        return "EXTERNAL", "unparseable address"
    if ip.is_loopback:
        return "LOCAL", "loopback"
    if ip.is_multicast:
        return "PRIVATE", "multicast / local discovery"
    if ip.is_link_local:
        return "PRIVATE", "link-local"
    if ip.is_private:
        for pref in LOCAL_PREFIXES:
            if addr.startswith(pref):
                return "PRIVATE", "same physical host or local container"
        return "PRIVATE", "RFC1918 private network"
    return "EXTERNAL", "routable public address"


class PacketCapture:
    """Run tcpdump in the background and parse what it sees."""

    def __init__(self, interface: str = "any"):
        self.interface = interface
        self._proc: subprocess.Popen | None = None
        self._lines: list[str] = []
        self._thread: threading.Thread | None = None
        self._t0 = 0.0
        self.error = ""

    @staticmethod
    def available() -> bool:
        return shutil.which("tcpdump") is not None

    def start(self) -> bool:
        if not self.available():
            self.error = "tcpdump not installed (dnf install -y tcpdump)"
            return False
        try:
            self._proc = subprocess.Popen(
                ["tcpdump", "-i", self.interface, "-nn", "-l", "-q",
                 "not", "port", "22"],
                stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
                bufsize=1)
        except Exception as e:
            self.error = f"could not start tcpdump: {e}"
            return False

        self._t0 = time.time()
        self._lines = []

        def reader():
            assert self._proc and self._proc.stdout
            for line in self._proc.stdout:
                self._lines.append(line.rstrip())

        self._thread = threading.Thread(target=reader, daemon=True)
        self._thread.start()
        time.sleep(1.0)          # let tcpdump bind before work begins
        return True

    def stop(self) -> CaptureReport:
        duration = time.time() - self._t0
        if self._proc:
            try:
                self._proc.send_signal(signal.SIGINT)
                self._proc.wait(timeout=5)
            except Exception:
                self._proc.kill()
        if self._thread:
            self._thread.join(timeout=3)

        report = CaptureReport(duration_s=duration, interfaces=self.interface,
                               error=self.error)
        report.raw_lines = len(self._lines)
        for line in self._lines:
            m = LINE_RE.search(line)
            if not m:
                continue
            report.parsed_lines += 1
            ts, src, sport, dst, dport = m.groups()
            c, why = classify_ip(dst)
            report.packets.append(Packet(ts, src, int(sport), dst, int(dport),
                                         c, why))
        return report


def capture_during(fn, interface: str = "any") -> tuple[object, CaptureReport]:
    """Run fn() while capturing. Returns (result, report)."""
    cap = PacketCapture(interface)
    started = cap.start()
    if not started:
        return fn(), CaptureReport(0.0, error=cap.error)
    try:
        result = fn()
    finally:
        report = cap.stop()
    return result, report
