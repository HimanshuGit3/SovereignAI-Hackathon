import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.tools import build_toolbox

box = build_toolbox()
print("tools:", box.names(), "\n")

CASES = [
    ("1. Basic execution",
     "print('hello from the sandbox')", True),

    ("2. Engineering calculation",
     "import math\n"
     "rho, g, H, Q, eta = 850, 9.81, 45.0, 0.028, 0.72\n"
     "P = rho * g * H * Q / eta\n"
     "print(f'Hydraulic power: {rho*g*H*Q/1000:.2f} kW')\n"
     "print(f'Shaft power at {eta:.0%} efficiency: {P/1000:.2f} kW')", True),

    ("3. scipy available",
     "import numpy as np, scipy.optimize as opt\n"
     "f = lambda x: x**3 - 2*x - 5\n"
     "print('root =', round(float(opt.brentq(f, 1, 3)), 6))", True),

    ("4. Error is reported, not raised",
     "print('before')\nresult = 1 / 0\nprint('after')", False),

    ("5. NETWORK BLOCKED",
     "import socket\n"
     "socket.setdefaulttimeout(4)\n"
     "try:\n"
     "    socket.create_connection(('8.8.8.8', 53))\n"
     "    print('FAIL: reached the internet')\n"
     "except Exception as e:\n"
     "    print('BLOCKED:', type(e).__name__, e)", True),

    ("6. DNS BLOCKED",
     "import socket\n"
     "try:\n"
     "    print('FAIL: resolved to', socket.gethostbyname('ollama.com'))\n"
     "except Exception as e:\n"
     "    print('BLOCKED:', type(e).__name__)", True),

    ("7. HOST FILES UNREACHABLE",
     "import os\n"
     "for p in ('/root/sovereign-workbench', '/root/.ssh', '/etc/shadow'):\n"
     "    print(f'{p}: exists={os.path.exists(p)}')\n"
     "print('workspace:', os.listdir('/workspace'))", True),

    ("8. ROOT FILESYSTEM READ-ONLY",
     "try:\n"
     "    open('/evil.txt', 'w').write('x')\n"
     "    print('FAIL: wrote to root fs')\n"
     "except Exception as e:\n"
     "    print('BLOCKED:', type(e).__name__, e)", True),

    ("9. RUNNING AS NON-ROOT",
     "import os\nprint('uid =', os.getuid(), '| euid =', os.geteuid())", True),

    ("10. TIMEOUT ENFORCED",
     "import time\nprint('looping forever')\nwhile True: time.sleep(1)", False),
]

for label, code, expect_ok in CASES:
    print("=" * 70)
    print(label)
    r = box.call("run_python", {"code": code})
    verdict = "as expected" if r.ok == expect_ok else ">>> UNEXPECTED <<<"
    print(f"  ok={r.ok} ({verdict})  {r.elapsed_ms} ms")
    for line in r.output.splitlines():
        if line.strip() and not line.startswith("="):
            print("    " + line)
    print()

print("=== SANDBOX TEST COMPLETE ===")
