# SovereignAI Workbench

**SIH 2026 | Problem Statement 26117 | Mangalore Refinery and Petrochemicals Limited**

An air-gapped, on-premise agentic AI workbench for confidential industrial
knowledge work. Runs entirely on the organisation's own hardware using
open-weight models. No data leaves the premises, and the system proves it
rather than asserting it.

## What it does

Reads a scanned inspection report, looks up the governing SOP to determine
who must approve the resulting shutdown, and produces a formal Word approval
note with every measurement transcribed exactly and every requirement cited.
In 12 seconds, on a laptop GPU, with no network egress.

| Requirement (from the problem statement) | Implementation |
|---|---|
| Model auto-selection across task types | YAML registry + hybrid router, 0-1 ms |
| Agentic multi-step task, end to end | Plan/act/observe loop + scripted workflows |
| Code executed and verified in a sandbox | Docker container, no network namespace |
| Multimodal document understanding | OCR-first routing with vision fallback |
| Proof of no external calls | Dual-layer monitor + air-gap enforcement |
| Grounding in manuals, SOPs, correspondence | Local vector store with grounded refusal |

## Architecture

Windows host runs Ollama on the GPU. RHEL VM runs the application. They
communicate over a private host-only segment with no internet route.
This mirrors a real refinery deployment: one physical machine, an isolated
internal network, zero WAN path.

    Windows host                    RHEL 10 VM
    Ollama + RTX 3050 (4 GB)  <-->  FastAPI
    4 open-weight models      priv  router -> agent / workflow
                              net   tools: ingest, docx, sandbox,
                                           calc, knowledge base
                                    monitor: egress + packet capture
                                    sandbox container (network: none)

## Design decisions that came from measurement

Every choice below was made after testing on the target hardware.

- **Deterministic beats generative for facts.** A vision model asked to
  interpret a P&ID called a pump a pressure instrument. Tag meaning is now
  decoded from ISA-5.1 conventions in code, so hallucination is impossible.
- **Small models cannot do unit arithmetic.** The coder model converted bar
  to pascal using 101325, dropped parentheses in the NPSH formula, and
  labelled metres as pascal. Engineering calculations now run in verified
  Python that prints every intermediate term.
- **OCR before vision.** On a typed report OCR is 18x faster and returns
  complete text. Routing is by measured characters per megapixel.
- **Scripted workflows for known task shapes.** The open-ended agent
  fabricated pump parameters by step 6 of an 8-step task. With a scripted
  pipeline: 4 stages, 0 errors, twice as fast, 9/9 source facts preserved.
- **A monitor that cannot see is not a monitor.** The packet capture once
  reported SOVEREIGN while parsing zero packets. It now reports
  INCONCLUSIVE unless it demonstrably observed traffic.

## Proving the sovereignty claim

Three independent layers: an application-level egress audit that classifies
destinations by IP properties (deny by default, not a blocklist), a kernel
packet capture that does not trust the application, and firewall-level
air-gap enforcement.

    ./infra/network/airgap.sh status       # before: chronyd reaching public NTP
    python tests/test_monitor_negative.py  # monitor catches a real violation
    ./infra/network/airgap.sh on           # DNS and 8.8.8.8 now unreachable
    python tests/test_capture.py           # workbench still works, 0 external

The negative control matters most. Proving absence of traffic is only
meaningful if the instrument is shown to detect traffic when it exists.

## Requirements

NVIDIA GPU with 4 GB VRAM or more (tested on RTX 3050 Laptop), Ollama on
the inference host, RHEL 10 or equivalent, Python 3.12, Docker. No internet
connection is required at run time.

## Quick start

    git clone https://github.com/HimanshuGit3/SovereignAI-Hackathon.git
    cd SovereignAI-Hackathon
    python3 -m venv .venv && source .venv/bin/activate
    pip install -r requirements.txt
    cp .env.example .env
    docker build -t sovereign-sandbox:latest sandbox/
    uvicorn app.main:app --host 0.0.0.0 --port 8080

Models to pull on the inference host:

    ollama pull qwen3.5:0.8b
    ollama pull qwen3.5:2b-q4_K_M
    ollama pull qwen2.5-coder:3b
    ollama pull gemma3:4b
    ollama pull nomic-embed-text

## Tests

    python tests/test_router.py            # routing, 0-1 ms deterministic
    python tests/test_ingest.py            # OCR vs vision routing
    python tests/test_tags.py              # ISA decoding, no false positives
    python tests/test_engineering.py       # verified calculations
    python tests/test_sandbox.py           # 10 isolation escape attempts
    python tests/test_kb.py                # 5 answerable + 3 must-refuse
    python tests/test_workflow.py          # flagship, 9/9 facts preserved
    python tests/test_monitor_negative.py  # monitor detects a violation

## Team

Team Blunder, Smart India Hackathon 2026

## Running with Docker

    ./start.sh      # detects Ollama, builds the sandbox image, starts everything
    ./stop.sh

Ollama and the model weights stay on the host. The container packages the
application, OCR, PDF tooling and the Docker CLI only.

### A note on the Docker socket

The workbench creates sandbox containers to execute model-written code, so
`/var/run/docker.sock` is mounted into the application container. This is
root-equivalent access to the host daemon and would be unacceptable in a
multi-tenant deployment.

It is acceptable here because the system is single-tenant and air-gapped:
the only code reaching the daemon is the workbench's own sandbox invocation,
which is fixed in `app/tools/sandbox.py` and always creates containers with
`network_mode=none`, a read-only root filesystem and all capabilities
dropped. A hardened deployment would replace this with a rootless Docker
socket proxy restricted to container create, start, wait and remove.
