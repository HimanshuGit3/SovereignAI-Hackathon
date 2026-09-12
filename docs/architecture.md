# Architecture

Every decision below was made after measuring on the target hardware:
an RTX 3050 Laptop with 4 GB VRAM, RHEL 10 in VirtualBox, 10 GB RAM.
Where a measurement changed the design, the numbers are given.

## Deployment topology

The GPU inference node is separate from the application node.

    Windows host                   RHEL 10 VM
    Ollama, RTX 3050 4 GB    <->   FastAPI + agent + tools
    5 open-weight models    private  sandbox containers
                            network  egress + packet monitor

VirtualBox cannot pass a GPU through to a guest, so running Ollama inside
the VM would mean CPU-only inference. Measured difference: 15 tok/s on
CPU against 91 tok/s with the model fully resident in VRAM.

Splitting the nodes is also closer to a real refinery deployment than a
single box would be: an application server talking to a GPU inference
server over an isolated internal segment, with no WAN route from either.

## Model selection

`models/registry.yaml` is the single source of truth. Adding a model means
adding six lines of YAML; no code changes.

| Role | Model | Why |
|---|---|---|
| router | qwen3.5:0.8b | 1.0 GB, 123 tok/s, classification only |
| general / orchestrator | qwen3.5:2b-q4_K_M | 1.6 GB, 100% GPU, native tool calls |
| code | qwen2.5-coder:3b | better code, cannot drive the loop |
| vision | qwen3.5:2b-q4_K_M | same weights already resident, no swap |
| vision-alt | gemma3:4b | hot-swap demonstration |
| embedding | nomic-embed-text | 274 MB, runs on CPU |

### Why qwen2.5-coder does not orchestrate

Ollama reports `tools` in its capabilities, but testing showed it emits
tool calls as plain text in the content field rather than through the
native `tool_calls` channel, and on one prompt it copied the JSON schema
into the arguments instead of filling it in. Advertised capability did not
match behaviour. It is now a delegate for code generation only, invoked
through the `generate_code` tool.

### Context windows are per-model and measured

A context sweep across 2048 to 16384 tokens recorded GPU occupancy at each
setting:

| Model | Safe ceiling | tok/s there |
|---|---|---|
| qwen3.5:0.8b | 16384 | 123 |
| qwen3.5:2b-q4_K_M | 16384 | 91 |
| qwen2.5-coder:3b | 8192 | 70 (drops to 50 at 16k, 81% GPU) |
| gemma3:4b | none | 19, never above 46% GPU |

Ollama defaults every model to 4096 tokens regardless of what the model
card advertises, which silently truncates retrieved documents. Each entry
in the registry sets `num_ctx` explicitly.

## Routing

Deterministic signals first, LLM classifier only when genuinely ambiguous.

    request -> image attachment?      -> VISION    (0 ms)
            -> code signals >= 3.0    -> CODE      (0 ms)
            -> document signals       -> DOCUMENT  (0 ms)
            -> question-shaped        -> CHAT      (0 ms)
            -> ambiguous              -> LLM classifier (~400 ms, rare)

All ten routing test cases resolve deterministically in 0-1 ms. Spending a
model call to notice an attached PNG is an image would be waste, and on
this hardware a classifier call costs more than the work it saves.

The routing decision also gates **which tools are offered**. A document
task never sees `generate_code`; a chat task sees only retrieval tools.
Fewer choices measurably reduces wrong tool selection by a 2B model.

## Agent loop and scripted workflows

The open-ended loop is plan / act / observe with native tool calling, the
model pinned for the whole task (a model swap costs 12-20 s with
`OLLAMA_MAX_LOADED_MODELS=1`).

It degrades with depth. On an 8-step task it invented a file path, called
`run_python` with another tool's arguments, and **fabricated pump
parameters** (0.8 m3/s, 120 m head) that appeared in no source document.

So for known task shapes the pipeline owns the sequence and the model owns
the content:

| | Open-ended agent | Scripted workflow |
|---|---|---|
| Steps | 8 (hit the limit) | 4 |
| Tool errors | 3 | 0 |
| Fabricated data | yes | no |
| Source facts preserved | lost the SOP authority | 9/9 |
| Time | 24.8 s | 12.4 s |

The model still extracts the findings, writes the background prose and
phrases the recommendation. It simply does not choose what happens next.
The open-ended agent remains available for task shapes not known ahead of
time.

## Deterministic over generative, wherever facts are involved

Three places where a language model was replaced by code:

**Equipment tag meaning.** Asked to interpret a P&ID, the vision model
called pump P-101A "an instrument reading (likely pressure)". Tags are now
decoded from ISA-5.1 prefix conventions in `app/ingest/tags.py`. The model
reads the tag *string*; code decides what it *means*.

An earlier permissive regex turned the prose "recorded at 82 deg C" into
instrument tag AT-82 and "03 Dec 2026" into DEC-2026. Matching is now
strict on prose and space-tolerant only on diagram transcriptions, where
OCR routinely drops the hyphen in "V 204".

**Engineering arithmetic.** Asked for NPSH available, the coder model
converted bar to pascal using 101325 (the atmosphere constant, not the bar
constant), dropped parentheses so it computed `Ps - Pv/(rho*g)`, and
labelled a result in metres as pascal. It then reported -35 kPa and
concluded the pump would cavitate. The correct answer is +19.69 m, which
is safe. `app/tools/engineering.py` now computes NPSH, pump power and wall
thickness in verified code that prints every intermediate term with units.

**Document ingestion.** Routing is by measured OCR yield in characters per
megapixel: 819 for a typed report (OCR, 320 ms), 20 for a schematic
(escalate to the vision model, 4.3 s). OCR is 18x faster than the vision
model on typed text and returns the complete document rather than a
summary, so it goes first.

## Knowledge base

SQLite for text, numpy for cosine similarity. Not ChromaDB: at a few
hundred chunks brute-force similarity is sub-millisecond, and every
dependency removed is one fewer thing to fail on demo day.

Chunking follows markdown headings rather than character counts. With
1200-character chunks, one chunk spanned four SOP sections and embedded to
a vector describing "a maintenance document" rather than any specific
fact. The bearing alarm setpoint query returned the wrong half of the
document. After sectioning, the same query returns the correct section at
0.781 against 0.66 for the wrong one. Each chunk is prefixed with its
document title so an isolated section still carries its source context.

Retrieval has a confidence floor at 0.58. Below it, no model call is made
at all. A genuine match scores 0.65-0.80 against this corpus; an
adjacent-but-wrong chunk lands near 0.50.

### Tuning against both failure modes

The first prompt was written hard against hallucination and produced the
opposite error: asked for the mechanical seal lead time, retrieval found
the right document at 0.726 and the model still said "the documents do not
specify this." The answer was in the excerpt it was handed.

The prompt now states that refusing when the answer is present is as
serious an error as guessing when it is absent. `tests/test_kb.py` holds
five answerable and three unanswerable questions and both halves must
pass; tuning either direction is checked against both.

Current result: 8/8. The three unanswerable questions are refused
correctly, including one where retrieval scored 0.598 and the model saw
plausible-looking chunks.

## Code sandbox

Isolation is structural, not advisory.

| Threat | Control |
|---|---|
| Network exfiltration | `network_mode=none` - no network namespace exists |
| Host filesystem access | no volume mounts, `read_only=True` |
| Privilege escalation | non-root uid 10001, `cap_drop=ALL`, no-new-privileges |
| Resource exhaustion | 512 MB memory, 64 PIDs, 0.5 CPU |
| Infinite loops | hard timeout, container killed |

`tests/test_sandbox.py` runs ten escape attempts. Network unreachable, DNS
resolution fails, `/root/.ssh` does not exist, root filesystem read-only,
uid 10001, infinite loop terminated at the timeout.

Code is passed as a base64-encoded argument rather than copied in as a
file. `put_archive` is rejected when the root filesystem is read-only, and
mounting a writable volume to work around that would open a path between
the sandbox and the host - the exact thing the sandbox exists to prevent.

## Sovereignty proof

Three layers, because one is not proof.

**Application audit.** Patches the httpx transport so every request in the
process is recorded, then classifies destinations by IP properties rather
than against a blocklist. An unknown destination is EXTERNAL by default.

**Kernel packet capture.** tcpdump, independent of the application. Parses
both Ethernet and LINUX_SLL2 cooked-capture formats.

A capture that parses zero packets now reports INCONCLUSIVE, never
SOVEREIGN. This was added after a real bug: the regex failed on cooked
capture format and the monitor reported "SOVEREIGN - nothing left the
machine" while observing nothing at all. Absence of evidence had been
silently presented as evidence of absence.

Inside a container the capture reports an explicit caveat, because a
container network namespace shows only that container's own traffic.

**Negative control.** `tests/test_monitor_negative.py` makes a deliberate
external call and fails unless both layers detect it. A clean result is
only meaningful from an instrument shown to fire.

**Air-gap enforcement.** `infra/network/airgap.sh` stops host services that
reach the internet, then rejects public egress. Before enforcement,
`chronyd` was contacting public NTP servers in Germany, India and Apple's
network - discovered by running the capture, not by assuming.

Container traffic traverses the FORWARD chain rather than OUTPUT, so the
script covers both. Without the FORWARD rules the container could reach
the internet while the host could not.

Ollama itself was also calling out. `OLLAMA_NO_CLOUD:false` and
`OLLAMA_REMOTES:[ollama.com]` meant model-recommendation and cache
requests on every start. Setting `OLLAMA_NO_CLOUD=1` stops it, and the
server log confirms: "skipping model recommendations refresh because cloud
is disabled".

## Known limitations

- The open-ended agent is unreliable beyond about four steps on a 2B
  model. Known task shapes use scripted workflows for this reason.
- `/var/run/docker.sock` is mounted into the application container so it
  can create sandbox containers. Root-equivalent host access, acceptable
  only because the deployment is single-tenant and air-gapped.
- The packet capture excludes port 22 so the operator's own SSH session
  does not swamp the signal. An honest exclusion, but an exclusion.
- The vision model transcribes drawing text reliably and does not
  interpret symbols. Non-standard schematic symbology is out of scope.
- Sample SOPs and inspection reports are synthetic. No MRPL data was used.
