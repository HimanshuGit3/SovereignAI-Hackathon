"""Hybrid retrieval: BM25 lexical scoring fused with dense cosine.

Dense embeddings capture meaning and miss literal strings. Asked for
"SOP-MECH-014 section 4", cosine similarity ranks by topic, not by the
identifier, so the right section can fall below chunks that merely talk
about similar things. Industrial documents are referenced almost entirely
by exact tag and document number, so that failure mode matters here more
than it would elsewhere.

BM25 is the opposite: exact terms, no semantics. Fusing the two ranked
lists with Reciprocal Rank Fusion gives both, and RRF needs no score
normalisation between two scales that are not comparable.

Implemented directly rather than with rank_bm25 to avoid another
dependency in an air-gapped deployment.
"""
import math
import re
from collections import Counter
from dataclasses import dataclass

from app.rag.store import Chunk, VectorStore

# Split on non-alphanumerics but keep hyphenated identifiers whole, so
# "SOP-MECH-014" and "E-204B" survive as single searchable terms.
TOKEN = re.compile(r"[A-Za-z0-9]+(?:-[A-Za-z0-9]+)*")

K1 = 1.5    # term-frequency saturation
B = 0.75    # length normalisation
RRF_K = 60  # standard RRF constant


def tokenize(text: str) -> list[str]:
    out = []
    for t in TOKEN.findall(text.lower()):
        out.append(t)
        # index hyphenated identifiers whole AND in parts, so both
        # "SOP-MECH-014" and "MECH" find the same chunk
        if "-" in t:
            out.extend(p for p in t.split("-") if p)
    return out


@dataclass
class Scored:
    chunk: Chunk
    dense: float = 0.0
    lexical: float = 0.0
    fused: float = 0.0
    matched: tuple = ()


class BM25:
    def __init__(self, docs: list[list[str]]):
        self.docs = docs
        self.n = len(docs)
        self.lens = [len(d) for d in docs]
        self.avg = (sum(self.lens) / self.n) if self.n else 0.0
        self.tf = [Counter(d) for d in docs]
        df = Counter()
        for d in docs:
            df.update(set(d))
        self.idf = {
            t: math.log(1 + (self.n - c + 0.5) / (c + 0.5))
            for t, c in df.items()
        }

    def score(self, query: list[str]) -> list[float]:
        out = [0.0] * self.n
        for i in range(self.n):
            tf, dl = self.tf[i], self.lens[i]
            s = 0.0
            for t in query:
                f = tf.get(t)
                if not f:
                    continue
                idf = self.idf.get(t, 0.0)
                s += idf * (f * (K1 + 1)) / (
                    f + K1 * (1 - B + B * dl / (self.avg or 1)))
            out[i] = s
        return out


class HybridRetriever:
    """Dense + BM25, fused by reciprocal rank."""

    def __init__(self, store: VectorStore | None = None):
        self.store = store or VectorStore()
        self._bm25 = None
        self._meta = None
        self._version = None

    def _index(self):
        mat, meta = self.store._load()
        if self._bm25 is not None and self._version == id(meta):
            return self._meta
        self._meta = meta
        self._bm25 = BM25([tokenize(m["text"]) for m in meta])
        self._version = id(meta)
        return meta

    def search(self, query: str, k: int = 4,
               min_fused: float = 0.0) -> list[Scored]:
        meta = self._index()
        if not meta:
            return []

        # dense: reuse the store's own path so embeddings stay consistent
        dense_hits = self.store.search(query, k=len(meta), min_score=-1.0)
        dense_rank = {}
        dense_score = {}
        for r, c in enumerate(dense_hits):
            key = (c.doc_id, c.ordinal)
            dense_rank[key] = r
            dense_score[key] = c.score

        # lexical
        q = tokenize(query)
        lex = self._bm25.score(q)
        order = sorted(range(len(meta)), key=lambda i: -lex[i])
        lex_rank = {i: r for r, i in enumerate(order)}

        fused = []
        for i, m in enumerate(meta):
            key = (m["doc_id"], m["ordinal"])
            dr = dense_rank.get(key, len(meta))
            lr = lex_rank[i]
            score = 1 / (RRF_K + dr + 1)
            if lex[i] > 0:
                score += 1 / (RRF_K + lr + 1)
            chunk = Chunk(m["doc_id"], m["source"], m["ordinal"], m["text"],
                          round(dense_score.get(key, 0.0), 4))
            matched = tuple(sorted({t for t in q if t in set(tokenize(m["text"]))}))
            fused.append(Scored(chunk, dense_score.get(key, 0.0),
                                round(lex[i], 3), round(score, 5), matched))

        fused.sort(key=lambda s: -s.fused)
        return [s for s in fused[:k] if s.fused > min_fused]

    def confidence(self, results: list["Scored"],
                   query_text: str = "") -> float:
        """A separate signal from the fusion score.

        RRF is rank-based: the top hit scores ~0.033 whether the match is
        excellent or merely least-bad. That makes it useless as a
        confidence measure, and confidence is what drives refusal.

        So confidence stays on interpretable scales. A strong dense match
        means the passage is semantically on topic; a strong BM25 score
        means the query's exact identifiers appear in it. Either alone is
        sufficient evidence that the corpus actually covers the question.
        """
        if not results:
            return 0.0

        best_dense = max(r.dense for r in results)

        # Identifier evidence is BINARY, not a magnitude. Either the
        # query named something specific - SOP-MECH-014, API 579, E-204B -
        # and a retrieved chunk contains it, or it did not. BM25 scores
        # have no fixed range (they depend on corpus size and term
        # rarity), so thresholding them means tuning a number that breaks
        # the moment the corpus grows.
        #
        # Common vocabulary must not count. Matching "setpoint" and
        # "trip" only means the question used words every maintenance
        # document shares; it says nothing about whether the corpus
        # answers it.
        query_ids = {t for t in tokenize(query_text)
                     if any(c.isdigit() for c in t) and len(t) > 2}

        if query_ids:
            for r in results:
                if query_ids & set(r.matched):
                    # the corpus demonstrably contains what was named
                    return max(best_dense, 0.72)

        return best_dense
