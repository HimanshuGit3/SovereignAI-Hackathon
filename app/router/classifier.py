import re
import time
from pathlib import Path

from app.core.llm import OllamaClient
from app.core.schemas import RoutingDecision, TaskType
from app.router.registry import ModelRegistry

IMAGE_EXT = {".png", ".jpg", ".jpeg", ".bmp", ".tif", ".tiff", ".webp"}
SCAN_EXT = {".pdf"}
CODE_EXT = {".py", ".js", ".ts", ".java", ".c", ".cpp", ".go", ".rs", ".sh", ".sql"}

CODE_SIGNALS = [
    (r"```", 3.0),
    (r"\b(write|generate|fix|debug|refactor|optimi[sz]e)\b.{0,40}\b"
     r"(code|script|function|program|class|query)\b", 3.0),
    (r"\b(traceback|stack ?trace|syntax ?error|segfault|exception)\b", 2.5),
    (r"\b(unit ?test|pytest|compile|runtime error)\b", 2.0),
    (r"\b(python|javascript|typescript|bash|sql|regex|api endpoint)\b", 1.0),
    (r"\b(def |class |import |SELECT |INSERT |for\s*\(|函数)\b", 1.5),
]

DOC_SIGNALS = [
    (r"\b(approval note|office note|noting|minutes|memorandum)\b", 3.0),
    (r"\b(summari[sz]e|summary|extract|draft|compile|prepare)\b.{0,40}"
     r"\b(report|document|note|letter|findings|doc)\b", 3.0),
    (r"\b(inspection report|sop|manual|tender|vendor|procurement)\b", 2.0),
    (r"\b(word file|\.docx|spreadsheet|\.xlsx|presentation|\.pptx)\b", 2.0),
]

CHAT_SIGNALS = [
    (r"^\s*(what|who|when|where|why|which)\s+(is|are|was|were|does|do|did)\b", 3.0),
    (r"^\s*(tell me about|explain|describe|define)\s+\w+\s*\??\s*$", 3.0),
    (r"^\s*(hi|hello|hey|thanks|thank you)\b", 3.0),
    (r"\b(what|which|list)\b.{0,30}\b(files?|documents?|folders?)\b.{0,30}"
     r"\b(available|in|under|inside)\b", 3.0),
    (r"^\s*(list|show)\s+(the\s+)?(files?|contents)\b", 3.0),
    (r"\?\s*$", 0.5),
]

ROLE_FOR_TASK = {
    TaskType.VISION: "vision",
    TaskType.CODE: "code",
    TaskType.EMBEDDING: "embedding",
    TaskType.DOCUMENT: "general",
    TaskType.CHAT: "general",
}

LLM_CLASSIFIER_PROMPT = """Classify the request into exactly one category.

CODE = write, debug, run or explain program code
DOCUMENT = summarise, extract from, or draft reports and documents
CHAT = general questions, definitions, explanations, conversation

Examples:
"fix this null pointer exception" -> CODE
"draft an approval note from these findings" -> DOCUMENT
"what is the flash point of diesel" -> CHAT
"tell me about MRPL" -> CHAT
"write a script to parse logs" -> CODE

Answer with one word only.

"{prompt}" -> """


def _score(text: str, signals: list[tuple[str, float]]) -> tuple[float, list[str]]:
    total, hits = 0.0, []
    for pattern, weight in signals:
        if re.search(pattern, text, re.IGNORECASE):
            total += weight
            hits.append(pattern[:34])
    return total, hits


class TaskRouter:
    """Deterministic-first router. LLM classification only when ambiguous."""

    THRESHOLD = 3.0

    def __init__(
        self,
        registry: ModelRegistry | None = None,
        client: OllamaClient | None = None,
        use_llm_fallback: bool = True,
    ):
        self.registry = registry or ModelRegistry()
        self.client = client or OllamaClient()
        self.use_llm_fallback = use_llm_fallback

    def route(
        self,
        prompt: str,
        attachments: list[str] | None = None,
        task_hint: str | None = None,
    ) -> RoutingDecision:
        t0 = time.perf_counter()
        attachments = attachments or []

        result = self._deterministic(prompt, attachments, task_hint)
        method = "deterministic"

        if result is None:
            if self.use_llm_fallback:
                result = self._llm_classify(prompt)
                method = "llm"
            else:
                result = (TaskType.CHAT, "no signal matched; using fallback", 0.4)
                method = "fallback"

        task_type, reason, confidence = result
        spec = self.registry.by_role(ROLE_FOR_TASK[task_type])
        elapsed = round((time.perf_counter() - t0) * 1000)

        return RoutingDecision(
            task_type=task_type,
            model_id=spec.id,
            model_name=spec.name,
            reason=reason,
            method=method,
            confidence=confidence,
            latency_ms=elapsed,
            options=self.registry.options_for(spec.id),
        )

    def _deterministic(self, prompt, attachments, task_hint):
        if task_hint:
            try:
                return (TaskType(task_hint.lower()),
                        f"caller supplied explicit task_hint='{task_hint}'", 1.0)
            except ValueError:
                pass

        for a in attachments:
            ext = Path(a).suffix.lower()
            if ext in IMAGE_EXT:
                return (TaskType.VISION, f"image attachment detected ({ext})", 1.0)
            if ext in SCAN_EXT:
                return (TaskType.VISION, f"scanned document attachment ({ext})", 0.9)
            if ext in CODE_EXT:
                return (TaskType.CODE, f"source file attachment ({ext})", 0.9)

        code_score, code_hits = _score(prompt, CODE_SIGNALS)
        doc_score, doc_hits = _score(prompt, DOC_SIGNALS)

        if code_score >= self.THRESHOLD and code_score > doc_score:
            return (TaskType.CODE,
                    f"code signals score {code_score:.1f} ({len(code_hits)} matched)",
                    min(code_score / 6.0, 1.0))

        if doc_score >= self.THRESHOLD and doc_score > code_score:
            return (TaskType.DOCUMENT,
                    f"document signals score {doc_score:.1f} ({len(doc_hits)} matched)",
                    min(doc_score / 6.0, 1.0))

        chat_score, chat_hits = _score(prompt, CHAT_SIGNALS)
        if chat_score >= self.THRESHOLD and chat_score > max(code_score, doc_score):
            return (TaskType.CHAT,
                    f"question-shaped, score {chat_score:.1f} ({len(chat_hits)} matched)",
                    min(chat_score / 4.0, 1.0))

        return None

    def _llm_classify(self, prompt: str):
        spec = self.registry.by_role("router")
        try:
            res = self.client.chat(
                spec.name,
                [{"role": "user",
                  "content": LLM_CLASSIFIER_PROMPT.format(prompt=prompt[:1200])}],
                options={
                    "temperature": 0.0,
                    "num_ctx": 4096,
                    "num_predict": 4,
                    "stop": ["\n", ".", ","],
                },
                think=False,
                keep_alive="2m",
            )
            raw = res["content"].strip().upper()
        except Exception as e:
            return (TaskType.CHAT, f"classifier unavailable ({type(e).__name__})", 0.3)

        mapping = {
            "CODE": TaskType.CODE,
            "DOCUMENT": TaskType.DOCUMENT,
            "CHAT": TaskType.CHAT,
        }
        tokens = [re.sub(r"[^A-Z]", "", t) for t in raw.split()]
        for tok in tokens:
            if tok in mapping:
                return (mapping[tok], f"{spec.name} classified as {tok}", 0.75)

        return (TaskType.CHAT,
                f"unparseable reply '{raw[:30]}' -> safe default CHAT", 0.3)
