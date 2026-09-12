"""Knowledge base tool: grounded answers from the organisation's own documents.

The agent uses this whenever a question concerns internal policy,
procedure, limits, authorisation or past correspondence. Answers are
generated only from retrieved excerpts and always carry citations.
"""
from app.rag.answer import KnowledgeBase
from app.tools.base import ToolResult, ToolSpec

_kb: KnowledgeBase | None = None


def _get_kb() -> KnowledgeBase:
    global _kb
    if _kb is None:
        _kb = KnowledgeBase()
    return _kb


def search_knowledge_base(question: str) -> ToolResult:
    kb = _get_kb()
    stats = kb.store.stats()
    if stats["total_chunks"] == 0:
        return ToolResult(
            False,
            "The knowledge base is empty. Index documents into data/kb first.",
            "search_knowledge_base")

    a = kb.ask(question)
    body = a.answer
    if a.chunks:
        body += "\n\nSOURCES:\n" + "\n".join(
            f"  {c.score:.3f} {c.citation()}" for c in a.chunks)
    if not a.confident:
        body += ("\n\n[Retrieval confidence was below threshold. Do not "
                 "present this as an organisational requirement.]")

    return ToolResult(
        True, body, "search_knowledge_base",
        meta={"confident": a.confident, "top_score": a.top_score,
              "citations": [c.citation() for c in a.chunks]},
    )


def knowledge_base_status() -> ToolResult:
    s = _get_kb().store.stats()
    lines = [f"Knowledge base: {s['total_chunks']} chunks, "
             f"embedder {s['embed_model']}"]
    for d in s["documents"]:
        lines.append(f"  {d['source']}  ({d['chunks']} chunks)")
    return ToolResult(True, "\n".join(lines), "knowledge_base_status")


SPECS = [
    ToolSpec(
        name="search_knowledge_base",
        description=(
            "Search the organisation's internal SOPs, manuals and past "
            "correspondence. Use this for ANY question about company policy, "
            "procedures, approval authority, limits, setpoints, lead times or "
            "internal requirements. Returns an answer grounded in the "
            "documents with citations, or states clearly that the documents "
            "do not cover the question. Always consult this before stating "
            "what the organisation requires."
        ),
        parameters={
            "type": "object",
            "properties": {
                "question": {"type": "string",
                             "description": "The question, in plain English."},
            },
            "required": ["question"],
        },
        fn=search_knowledge_base,
    ),
    ToolSpec(
        name="knowledge_base_status",
        description="List what documents are indexed in the knowledge base.",
        parameters={"type": "object", "properties": {}, "required": []},
        fn=knowledge_base_status,
    ),
]
