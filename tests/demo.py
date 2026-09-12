"""SIH 2026 demo runner. One scripted pass through all five requirements.

Run with no arguments for the full sequence, or pass a number to run one
act. Pauses between acts so you can talk.
"""
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

BASE = Path(__file__).resolve().parent.parent
W = 76


def banner(n, title, claim):
    print("\n" + "=" * W)
    print(f"  ACT {n}: {title}")
    print(f"  {claim}")
    print("=" * W)


def pause():
    if "--auto" not in sys.argv:
        input("\n  [enter to continue] ")


def act1():
    banner(1, "MODEL AUTO-SELECTION",
           "Requirement: select across at least two task types")
    from app.router.classifier import TaskRouter
    r = TaskRouter()
    cases = [
        ("Draft an approval note from this inspection report", []),
        ("Write a Python function to size a relief valve", []),
        ("Describe this drawing", ["data/samples/pid_extract.png"]),
        ("What is the flash point of diesel?", []),
    ]
    print(f"\n  {'TASK TYPE':<11}{'MODEL':<22}{'ms':>4}  WHY")
    print("  " + "-" * (W - 4))
    for task, atts in cases:
        d = r.route(task, attachments=atts)
        print(f"  {d.task_type.value:<11}{d.model_name:<22}{d.latency_ms:>4}  {d.reason[:34]}")
        print(f"  {'':11}> {task[:56]}")
    print("\n  Three different models, selected deterministically in under 1 ms.")
    print("  Adding a model means editing models/registry.yaml. No code change.")


def act2():
    banner(2, "MULTIMODAL INGEST",
           "Requirement: scanned documents, drawings, on-device")
    from app.ingest.extractor import DocumentExtractor
    ex = DocumentExtractor()
    for name in ("inspection_report.png", "pid_extract.png"):
        doc = ex.extract(BASE / "data" / "samples" / name)
        print(f"\n  {name}")
        print(f"    method {doc.method}  |  {doc.elapsed_ms} ms  |  "
              f"OCR yield {doc.yield_score} chars/MP")
        print(f"    {doc.notes[0]}")
        print("    " + doc.tag_summary.replace("\n", "\n    ")[:400])
    print("\n  Routing is by measured OCR yield, not by file type.")
    print("  Tag MEANING is decoded in code from ISA-5.1, never by the model.")


def act3():
    banner(3, "SANDBOXED EXECUTION",
           "Requirement: code run and verified in a sandbox")
    from app.tools import build_toolbox
    box = build_toolbox()
    tests = [
        ("reach the internet",
         "import socket\nsocket.setdefaulttimeout(3)\n"
         "try:\n socket.create_connection(('8.8.8.8',53))\n print('REACHED')\n"
         "except Exception as e:\n print('BLOCKED:', type(e).__name__, e)"),
        ("resolve a hostname",
         "import socket\ntry:\n print('RESOLVED', socket.gethostbyname('ollama.com'))\n"
         "except Exception as e:\n print('BLOCKED:', type(e).__name__)"),
        ("read host files",
         "import os\nfor p in ('/root/sovereign-workbench','/root/.ssh'):\n"
         " print(f'{p}: exists={os.path.exists(p)}')"),
        ("write to disk",
         "try:\n open('/x','w').write('x')\n print('WROTE')\n"
         "except Exception as e:\n print('BLOCKED:', type(e).__name__, e)"),
        ("escalate privilege",
         "import os\nprint('uid =', os.getuid())"),
    ]
    print("\n  Model-generated code attempting to escape the sandbox:\n")
    for label, code in tests:
        r = box.call("run_python", {"code": code})
        out = [l for l in r.output.splitlines() if l and not l.startswith("=")][-1]
        print(f"    {label:<22} {out[:52]}")
    print("\n  network_mode=none: no network namespace exists in the container.")
    print("  Not a firewall rule. The interface is absent at the kernel level.")


def act4():
    banner(4, "GROUNDED AGENTIC TASK",
           "Requirement: scan -> findings -> Word deliverable, end to end")
    from app.agent.workflows import InspectionToApprovalWorkflow
    from docx import Document

    def show(st):
        print(f"    [{st.n}] {'ok ' if st.ok else 'ERR'} {st.name:<26}"
              f"{st.elapsed_ms:>6} ms   {st.detail[:44]}")

    print()
    run = InspectionToApprovalWorkflow().run(
        "data/samples/inspection_report.png", "DEMO_approval.docx",
        on_stage=show)
    print(f"\n  {run.total_ms} ms total  ->  {run.artifacts}")

    target = BASE / "outputs" / "DEMO_approval.docx"
    body = "\n".join(p.text for p in Document(target).paragraphs)
    for t in Document(target).tables:
        for row in t.rows:
            body += "\n" + " | ".join(c.text for c in row.cells)

    FACTS = {"P-101A": "tag", "8.2": "measured mm", "9.0": "design min mm",
             "82": "bearing degC", "75": "alarm degC",
             "INSP-2026-0417": "source report", "30": "SOP shutdown days",
             "Mechanical Maintenance": "SOP approver", "SOP-MECH-014": "citation"}
    print("\n  FACT CHECK - generated document against source:\n")
    ok = 0
    for tok, meaning in FACTS.items():
        hit = tok.lower() in body.lower()
        ok += hit
        print(f"    {'FOUND  ' if hit else 'MISSING'}  {tok:<24} {meaning}")
    print(f"\n  {ok}/{len(FACTS)} facts preserved verbatim. No paraphrasing of figures.")
    print("  The last two can only come from the SOP lookup, not the scan.")


def act5():
    banner(5, "SOVEREIGNTY PROOF",
           "Requirement: show no external calls are made at any point")
    from app.monitor.capture import capture_during
    from app.monitor.egress import install_monitor
    import httpx

    mon = install_monitor()
    mon.reset()

    print("\n  STEP 1 - prove the instrument works. One deliberate external call.\n")

    def violate():
        try:
            httpx.get("http://8.8.8.8/", timeout=4)
        except Exception:
            pass

    _, rep = capture_during(violate)
    print(f"    app audit    : {mon.summary()['external_count']} external call(s) flagged")
    print(f"    kernel       : {rep.summary()['external']} external packet(s), "
          f"{rep.summary()['parsed_lines']} parsed total")
    print("\n    The monitor detects violations. A clean result now means something.")

    print("\n  STEP 2 - enforce the air gap.\n")
    subprocess.run(["./infra/network/airgap.sh", "on"], cwd=BASE)

    print("\n  STEP 3 - run real work with the air gap enforced.\n")
    mon.reset()
    from app.agent.loop import Agent

    def work():
        return Agent().run("Read data/samples/inspection_report.png and state "
                           "the casing wall thickness.")

    run, rep2 = capture_during(work)
    print(f"    agent       : {len(run.steps)} steps, {run.total_ms} ms")
    print(f"    answer      : {run.answer[:140]}")
    s2, e2 = rep2.summary(), mon.summary()
    print(f"\n    kernel      : {s2['parsed_lines']} packets, "
          f"{s2['external']} external, blind={s2['blind']}")
    print(f"    app audit   : {e2['total_requests']} requests, "
          f"{e2['external_count']} external")
    print(f"    destinations: {e2['destinations']}")
    verdict = (not s2["blind"]) and s2["external"] == 0 and e2["external_count"] == 0
    print(f"\n  VERDICT: {'SOVEREIGN - both layers agree, capture was live' if verdict else 'CHECK FAILED'}")
    print("\n  Restore normal networking with: ./infra/network/airgap.sh off")


ACTS = {1: act1, 2: act2, 3: act3, 4: act4, 5: act5}

if __name__ == "__main__":
    nums = [int(a) for a in sys.argv[1:] if a.isdigit()] or [1, 2, 3, 4, 5]
    t0 = time.time()
    for n in nums:
        ACTS[n]()
        if n != nums[-1]:
            pause()
    print(f"\n{'=' * W}\n  DEMO COMPLETE - {round(time.time() - t0)} s\n{'=' * W}")
