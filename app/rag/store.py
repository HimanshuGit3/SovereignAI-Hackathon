"""Local vector store: SQLite for text, numpy for similarity.

Deliberately not ChromaDB. At this scale brute-force cosine over a few
hundred vectors is sub-millisecond, and every dependency removed is one
fewer thing to fail on demo day. Nothing here touches the network.

Embeddings come from nomic-embed-text running on the local Ollama node.
Its context is 2048 tokens, so chunks are capped well below that.
"""
import json
import re
import sqlite3
import time
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from app.config import BASE_DIR, settings
from app.core.llm import OllamaClient
from app.router.registry import ModelRegistry

# nomic-embed-text reports a 2048-token context. ~4 chars per token, so
# 1200 chars leaves comfortable headroom against silent truncation.
CHUNK_CHARS = 1200
CHUNK_OVERLAP = 180

# Smaller target for heading-delimited sections. SOPs are already written
# as one topic per numbered section; a chunk that spans four sections
# embeds to a vector describing "a maintenance document" rather than
# "75 degree bearing alarm setpoint", and retrieval then misses.
SECTION_MAX = 900
HEADING_RE = re.compile(r"^(#{1,6})\s+(.+)$", re.MULTILINE)


@dataclass
class Chunk:
    doc_id: str
    source: str
    ordinal: int
    text: str
    score: float = 0.0

    def citation(self) -> str:
        return f"[{Path(self.source).name} #{self.ordinal + 1}]"


def split_markdown(text: str, max_chars: int = SECTION_MAX) -> list[str]:
    """Split on markdown headings, one chunk per section.

    Each chunk is prefixed with the document title so an isolated section
    still carries its source context into the embedding. Sections longer
    than max_chars fall back to character splitting.
    """
    matches = list(HEADING_RE.finditer(text))
    if len(matches) < 2:
        return split_text(text)

    title = matches[0].group(2).strip()
    chunks = []
    for i, m in enumerate(matches):
        start = m.start()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        section = text[start:end].strip()
        if not section or len(section) < 40:
            continue
        heading = m.group(2).strip()
        if heading != title:
            section = f"[{title}]\n\n{section}"
        if len(section) > max_chars:
            chunks.extend(split_text(section, max_chars, 120))
        else:
            chunks.append(section)
    return chunks


def split_text(text: str, size: int = CHUNK_CHARS,
               overlap: int = CHUNK_OVERLAP) -> list[str]:
    """Fallback splitter for unstructured text. Never cuts mid-sentence."""
    text = text.strip()
    if len(text) <= size:
        return [text] if text else []

    chunks, start = [], 0
    while start < len(text):
        end = min(start + size, len(text))
        if end < len(text):
            for sep in ("\n\n", "\n", ". ", " "):
                cut = text.rfind(sep, start + size // 2, end)
                if cut != -1:
                    end = cut + len(sep)
                    break
        piece = text[start:end].strip()
        if piece:
            chunks.append(piece)
        if end >= len(text):
            break
        start = max(end - overlap, start + 1)
    return chunks


class VectorStore:
    def __init__(self, db_path: Path | None = None,
                 client: OllamaClient | None = None,
                 registry: ModelRegistry | None = None):
        self.db_path = db_path or (BASE_DIR / "data" / "vectorstore" / "kb.sqlite")
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.client = client or OllamaClient()
        self.registry = registry or ModelRegistry()
        self._init_db()
        self._cache: tuple[np.ndarray, list[dict]] | None = None

    def _conn(self):
        return sqlite3.connect(self.db_path)

    def _init_db(self):
        with self._conn() as c:
            c.execute("""
                CREATE TABLE IF NOT EXISTS chunks (
                    id       INTEGER PRIMARY KEY,
                    doc_id   TEXT NOT NULL,
                    source   TEXT NOT NULL,
                    ordinal  INTEGER NOT NULL,
                    text     TEXT NOT NULL,
                    vector   BLOB NOT NULL,
                    added_at REAL NOT NULL
                )""")
            c.execute("CREATE INDEX IF NOT EXISTS idx_doc ON chunks(doc_id)")

    @property
    def embed_model(self) -> str:
        return self.registry.by_role("embedding").name

    def _embed(self, texts: list[str]) -> list[list[float]]:
        return self.client.embed(self.embed_model, texts)

    def add_document(self, source: str, text: str,
                     doc_id: str | None = None) -> dict:
        doc_id = doc_id or Path(source).stem
        pieces = split_markdown(text)
        if not pieces:
            return {"doc_id": doc_id, "chunks": 0, "skipped": "empty document"}

        t0 = time.perf_counter()
        vectors = self._embed(pieces)
        if len(vectors) != len(pieces):
            raise RuntimeError(
                f"embedder returned {len(vectors)} vectors for {len(pieces)} chunks")

        with self._conn() as c:
            c.execute("DELETE FROM chunks WHERE doc_id = ?", (doc_id,))
            for i, (piece, vec) in enumerate(zip(pieces, vectors)):
                c.execute(
                    "INSERT INTO chunks (doc_id, source, ordinal, text, vector, added_at)"
                    " VALUES (?,?,?,?,?,?)",
                    (doc_id, source, i, piece,
                     np.asarray(vec, dtype=np.float32).tobytes(), time.time()))
        self._cache = None
        return {"doc_id": doc_id, "source": source, "chunks": len(pieces),
                "dim": len(vectors[0]),
                "embed_ms": round((time.perf_counter() - t0) * 1000)}

    def _load(self) -> tuple[np.ndarray, list[dict]]:
        if self._cache is not None:
            return self._cache
        with self._conn() as c:
            rows = c.execute(
                "SELECT doc_id, source, ordinal, text, vector FROM chunks"
            ).fetchall()
        if not rows:
            self._cache = (np.zeros((0, 1), dtype=np.float32), [])
            return self._cache

        meta = [{"doc_id": r[0], "source": r[1], "ordinal": r[2], "text": r[3]}
                for r in rows]
        mat = np.vstack([np.frombuffer(r[4], dtype=np.float32) for r in rows])
        norms = np.linalg.norm(mat, axis=1, keepdims=True)
        mat = mat / np.clip(norms, 1e-9, None)
        self._cache = (mat, meta)
        return self._cache

    def search(self, query: str, k: int = 4,
               min_score: float = 0.45) -> list[Chunk]:
        mat, meta = self._load()
        if not meta:
            return []
        qv = np.asarray(self._embed([query])[0], dtype=np.float32)
        qv = qv / max(float(np.linalg.norm(qv)), 1e-9)
        scores = mat @ qv
        order = np.argsort(-scores)[:k]
        out = []
        for i in order:
            s = float(scores[i])
            if s < min_score:
                continue
            m = meta[i]
            out.append(Chunk(m["doc_id"], m["source"], m["ordinal"],
                             m["text"], round(s, 4)))
        return out

    def stats(self) -> dict:
        with self._conn() as c:
            total = c.execute("SELECT COUNT(*) FROM chunks").fetchone()[0]
            docs = c.execute(
                "SELECT doc_id, source, COUNT(*) FROM chunks GROUP BY doc_id"
            ).fetchall()
        return {
            "db": str(self.db_path),
            "total_chunks": total,
            "documents": [{"doc_id": d, "source": s, "chunks": n}
                          for d, s, n in docs],
            "embed_model": self.embed_model,
        }

    def clear(self) -> int:
        with self._conn() as c:
            n = c.execute("SELECT COUNT(*) FROM chunks").fetchone()[0]
            c.execute("DELETE FROM chunks")
        self._cache = None
        return n
