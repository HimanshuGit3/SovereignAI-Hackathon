"""Grounded question answering over the local knowledge base.

The hard requirement is refusal. Retrieval always returns its best
chunks, even when none of them answer the question - the vibration trip
setpoint query returns the bearing-temperature section at 0.53. If the
model treats every retrieved chunk as an answer, it will confidently
report 90 degrees for a setpoint the SOPs never define.

Two defences:
  1. A confidence floor. Below it, we do not call the model at all.
  2. A prompt that makes "the documents do not state this" a correct and
     expected answer rather than a failure.
"""
import time
from dataclasses import dataclass, field

from app.core.llm import OllamaClient
from app.rag.hybrid import HybridRetriever
from app.rag.store import Chunk, VectorStore
from app.router.registry import ModelRegistry

# Swept against 10 covered and 8 uncovered questions on a 20-chunk
# corpus (tests/test_threshold.py). The two classes overlap slightly, so
# no threshold separates them perfectly; this value favours refusing a
# borderline question over answering it wrongly.
#
# This number is fitted to a small corpus. Re-run the sweep after adding
# documents: score distributions shift as a corpus grows, and a floor
# tuned on 20 chunks is not evidence of anything at 20,000.
CONFIDENCE_FLOOR = 0.62

SYSTEM = """You answer questions using ONLY the organisation's own documents.

RULES
- Use only the excerpts provided. Never add knowledge from anywhere else.
- Cite the source in square brackets after each fact, exactly as labelled.
- Quote figures, limits and names exactly as written. Never round or rephrase.
- Read every excerpt fully before deciding. The answer is often a single
  line inside a longer passage about other things. If any excerpt states
  the fact, answer with it and cite the source.
- Only if NO excerpt contains the answer, say: "The provided documents do
  not specify this," then state what they do cover. Refusing when the
  answer IS present is as serious an error as guessing when it is not.
- Be brief. Two or three sentences unless more detail is genuinely needed."""


@dataclass
class GroundedAnswer:
    question: str
    answer: str
    chunks: list[Chunk] = field(default_factory=list)
    confident: bool = True
    top_score: float = 0.0
    elapsed_ms: int = 0
    model: str = ""

    def as_dict(self) -> dict:
        return {
            "question": self.question,
            "answer": self.answer,
            "confident": self.confident,
            "top_score": self.top_score,
            "sources": [
                {"citation": c.citation(), "score": c.score,
                 "source": c.source, "excerpt": c.text[:300]}
                for c in self.chunks
            ],
            "elapsed_ms": self.elapsed_ms,
            "model": self.model,
        }

    def render(self) -> str:
        head = "" if self.confident else "[LOW CONFIDENCE RETRIEVAL]\n"
        cites = "\n".join(f"  {c.score:.3f} {c.citation()}" for c in self.chunks)
        return (f"{head}{self.answer}\n\nSOURCES CONSULTED\n{cites or '  none'}\n"
                f"({self.elapsed_ms} ms, {self.model})")


class KnowledgeBase:
    def __init__(self, store: VectorStore | None = None,
                 client: OllamaClient | None = None,
                 registry: ModelRegistry | None = None):
        self.store = store or VectorStore()
        self.retriever = HybridRetriever(self.store)
        self.client = client or OllamaClient()
        self.registry = registry or ModelRegistry()

    def ask(self, question: str, k: int = 4) -> GroundedAnswer:
        t0 = time.perf_counter()
        scored = self.retriever.search(question, k=k)
        hits = [s.chunk for s in scored]
        # Confidence comes from dense/BM25, not the RRF score: see
        # HybridRetriever.confidence for why.
        top = self.retriever.confidence(scored, question)

        if not hits or top < CONFIDENCE_FLOOR:
            return GroundedAnswer(
                question=question,
                answer=("The provided documents do not appear to cover this. "
                        "The knowledge base holds pump maintenance procedures, "
                        "inspection reporting standards and vendor "
                        "correspondence; nothing in them addresses this "
                        "question directly."),
                chunks=hits, confident=False, top_score=top,
                elapsed_ms=round((time.perf_counter() - t0) * 1000),
                model="none (retrieval below confidence floor)",
            )

        context = "\n\n".join(
            f"--- EXCERPT {c.citation()} ---\n{c.text}" for c in hits)
        spec = self.registry.by_role("general")
        res = self.client.chat(
            spec.name,
            [{"role": "system", "content": SYSTEM},
             {"role": "user",
              "content": f"DOCUMENT EXCERPTS\n\n{context}\n\n"
                         f"QUESTION: {question}"}],
            options={**self.registry.options_for(spec.id), "num_predict": 400},
            think=False, keep_alive="15m",
        )

        return GroundedAnswer(
            question=question, answer=res["content"].strip(), chunks=hits,
            confident=True, top_score=top,
            elapsed_ms=round((time.perf_counter() - t0) * 1000),
            model=spec.name,
        )

    def index_directory(self, folder) -> list[dict]:
        from pathlib import Path
        from app.config import BASE_DIR
        results = []
        for f in sorted(Path(folder).glob("*")):
            if f.suffix.lower() not in (".md", ".txt"):
                continue
            rel = str(f.relative_to(BASE_DIR)) if BASE_DIR in f.parents else str(f)
            results.append(self.store.add_document(rel, f.read_text()))
        return results
