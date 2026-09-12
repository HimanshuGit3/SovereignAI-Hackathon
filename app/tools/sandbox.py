"""Execute model-generated Python inside a locked-down container.

Isolation is structural, not advisory:
  network_mode=none  - no network namespace exists; egress is impossible
  read_only=True     - root filesystem immutable
  no volume mounts   - host files unreachable
  cap_drop=ALL       - every Linux capability removed
  mem_limit/pids     - resource exhaustion bounded
  timeout            - container force-killed on overrun
"""
import base64
import time

import docker
from docker.errors import ContainerError, DockerException, ImageNotFound

from app.config import settings
from app.tools.base import ToolResult, ToolSpec

MEM_LIMIT = "512m"
PIDS_LIMIT = 64
CPU_QUOTA = 50000      # 0.5 of one core (period 100000)
OUTPUT_LIMIT = 8000

BANNER = "=" * 8 + " SANDBOX (no network, read-only, non-root) " + "=" * 8


def run_python(code: str, timeout: int | None = None) -> ToolResult:
    timeout = timeout or settings.sandbox_timeout
    try:
        client = docker.from_env()
    except DockerException as e:
        return ToolResult(False, f"Docker unavailable: {e}", "run_python")

    try:
        client.images.get(settings.sandbox_image)
    except ImageNotFound:
        return ToolResult(
            False,
            f"sandbox image '{settings.sandbox_image}' not built. "
            "Run: docker build -t sovereign-sandbox:latest sandbox/",
            "run_python")

    container = None
    t0 = time.perf_counter()
    try:
        # The script is base64-encoded and decoded inside the interpreter.
        # This avoids writing any file: put_archive() is rejected when the
        # rootfs is read-only, and mounting a writable volume would punch a
        # hole in the isolation we are claiming.
        payload = base64.b64encode(code.encode("utf-8")).decode("ascii")
        bootstrap = (
            "import base64,sys;"
            f"exec(compile(base64.b64decode('{payload}').decode('utf-8'),"
            "'<sandbox>','exec'))"
        )

        container = client.containers.create(
            image=settings.sandbox_image,
            command=["python", "-u", "-c", bootstrap],
            network_mode="none",
            mem_limit=MEM_LIMIT,
            memswap_limit=MEM_LIMIT,
            pids_limit=PIDS_LIMIT,
            cpu_quota=CPU_QUOTA,
            cpu_period=100000,
            read_only=True,
            cap_drop=["ALL"],
            security_opt=["no-new-privileges"],
            tmpfs={"/tmp": "rw,size=64m,exec"},
            working_dir="/workspace",
            user="10001",
        )
        container.start()

        try:
            result = container.wait(timeout=timeout + 5)
            exit_code = result.get("StatusCode", -1)
            timed_out = False
        except Exception:
            container.kill()
            exit_code, timed_out = -1, True

        logs = container.logs(stdout=True, stderr=True).decode(
            "utf-8", errors="replace")
        elapsed = round((time.perf_counter() - t0) * 1000)

        if timed_out:
            return ToolResult(
                False,
                f"{BANNER}\nExecution exceeded {timeout}s and was terminated.\n"
                f"Partial output:\n{logs[:OUTPUT_LIMIT]}",
                "run_python", meta={"exit_code": -1, "timed_out": True})

        body = logs[:OUTPUT_LIMIT] or "(no output; did you forget print()?)"
        if len(logs) > OUTPUT_LIMIT:
            body += f"\n...[truncated, {len(logs)} chars total]"

        if exit_code == 0:
            return ToolResult(
                True, f"{BANNER}\nExit code 0 in {elapsed} ms.\n\n{body}",
                "run_python", meta={"exit_code": 0})

        return ToolResult(
            False,
            f"{BANNER}\nExit code {exit_code}. The code raised an error:\n\n{body}",
            "run_python", meta={"exit_code": exit_code})

    except ContainerError as e:
        return ToolResult(False, f"container error: {e}", "run_python")
    except DockerException as e:
        return ToolResult(False, f"docker error: {e}", "run_python")
    finally:
        if container is not None:
            try:
                container.remove(force=True)
            except DockerException:
                pass


SPECS = [
    ToolSpec(
        name="run_python",
        description=(
            "Execute Python code in an isolated sandbox with no network access "
            "and no access to host files. numpy, pandas, scipy and sympy are "
            "available. You MUST use print() to see any result. Use this to "
            "verify calculations and to test code you have written."
        ),
        parameters={
            "type": "object",
            "properties": {
                "code": {"type": "string",
                         "description": "Python source. Use print() for output."},
            },
            "required": ["code"],
        },
        fn=run_python,
    ),
]
