from dataclasses import dataclass, field
from pathlib import Path

import yaml

from app.config import settings


@dataclass
class ModelSpec:
    id: str
    name: str
    role: str
    capabilities: list[str]
    size_gb: float
    description: str
    options: dict = field(default_factory=dict)
    max_input_tokens: int | None = None

    def supports(self, capability: str) -> bool:
        return capability in self.capabilities


class ModelRegistry:
    """Loads models/registry.yaml. Adding a model = editing YAML, not code."""

    def __init__(self, path: str | Path | None = None):
        self.path = Path(path) if path else settings.registry_file
        self._raw = yaml.safe_load(self.path.read_text())
        self._defaults = self._raw.get("defaults", {})
        self._routing = self._raw.get("routing", {})
        self._models: dict[str, ModelSpec] = {}
        for entry in self._raw.get("models", []):
            spec = ModelSpec(
                id=entry["id"],
                name=entry["name"],
                role=entry["role"],
                capabilities=entry.get("capabilities", []),
                size_gb=float(entry.get("size_gb", 0)),
                description=entry.get("description", ""),
                options=entry.get("options") or {},
                max_input_tokens=entry.get("max_input_tokens"),
            )
            self._models[spec.id] = spec

    def get(self, model_id: str) -> ModelSpec:
        if model_id not in self._models:
            raise KeyError(f"unknown model id '{model_id}' in {self.path}")
        return self._models[model_id]

    def by_role(self, role: str) -> ModelSpec:
        for spec in self._models.values():
            if spec.role == role:
                return spec
        raise KeyError(f"no model with role '{role}'")

    def all(self) -> list[ModelSpec]:
        return list(self._models.values())

    def options_for(self, model_id: str) -> dict:
        merged = dict(self._defaults.get("options", {}))
        merged.update(self.get(model_id).options)
        return merged

    @property
    def fallback_id(self) -> str:
        return self._routing.get("fallback", "general")

    @property
    def rules(self) -> list[dict]:
        return self._routing.get("rules", [])
