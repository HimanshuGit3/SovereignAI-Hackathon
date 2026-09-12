from dataclasses import dataclass, field
from enum import Enum


class TaskType(str, Enum):
    CHAT = "chat"
    DOCUMENT = "document"
    CODE = "code"
    VISION = "vision"
    EMBEDDING = "embedding"


@dataclass
class RoutingDecision:
    """Everything the UI needs to SHOW the user why a model was chosen."""

    task_type: TaskType
    model_id: str
    model_name: str
    reason: str
    method: str
    confidence: float
    latency_ms: int
    options: dict = field(default_factory=dict)

    def as_dict(self) -> dict:
        return {
            "task_type": self.task_type.value,
            "model_id": self.model_id,
            "model_name": self.model_name,
            "reason": self.reason,
            "method": self.method,
            "confidence": round(self.confidence, 2),
            "routing_latency_ms": self.latency_ms,
        }
