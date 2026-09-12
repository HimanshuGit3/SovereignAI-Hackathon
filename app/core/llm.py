import base64
from pathlib import Path
from typing import Any

import httpx

from app.config import settings


class OllamaError(RuntimeError):
    pass


class OllamaClient:
    """Thin client over the local Ollama HTTP API. No external calls, ever."""

    def __init__(self, base_url: str | None = None, timeout: int = 300):
        self.base_url = (base_url or settings.ollama_base_url).rstrip("/")
        self._client = httpx.Client(timeout=timeout)

    def health(self) -> bool:
        try:
            r = self._client.get(f"{self.base_url}/api/tags")
            return r.status_code == 200
        except httpx.HTTPError:
            return False

    def list_models(self) -> list[str]:
        r = self._client.get(f"{self.base_url}/api/tags")
        r.raise_for_status()
        return [m["name"] for m in r.json().get("models", [])]

    def chat(
        self,
        model: str,
        messages: list[dict[str, Any]],
        options: dict | None = None,
        think: bool | None = None,
        keep_alive: str | int | None = None,
        tools: list[dict] | None = None,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "model": model,
            "messages": messages,
            "stream": False,
        }
        if keep_alive is not None:
            payload["keep_alive"] = keep_alive
        if tools:
            payload["tools"] = tools
        if options:
            payload["options"] = options
        if think is not None:
            payload["think"] = think

        r = self._client.post(f"{self.base_url}/api/chat", json=payload)
        if r.status_code != 200:
            raise OllamaError(f"{model} -> HTTP {r.status_code}: {r.text[:300]}")

        data = r.json()
        msg = data.get("message", {})

        calls = []
        for tc in msg.get("tool_calls") or []:
            fn = tc.get("function", {})
            args = fn.get("arguments", {})
            if isinstance(args, str):
                import json as _json
                try:
                    args = _json.loads(args)
                except _json.JSONDecodeError:
                    args = {"_raw": args}
            calls.append({"name": fn.get("name", ""), "arguments": args or {}})

        return {
            "content": msg.get("content", ""),
            "thinking": msg.get("thinking", ""),
            "tool_calls": calls,
            "raw_message": msg,
            "model": data.get("model", model),
            "eval_count": data.get("eval_count", 0),
            "total_duration_ms": round(data.get("total_duration", 0) / 1e6),
        }

    def chat_with_image(
        self,
        model: str,
        prompt: str,
        image_path: str | Path,
        options: dict | None = None,
        think: bool | None = False,
        keep_alive: str | int | None = None,
    ) -> dict[str, Any]:
        raw = Path(image_path).read_bytes()
        b64 = base64.b64encode(raw).decode("ascii")
        messages = [{"role": "user", "content": prompt, "images": [b64]}]
        return self.chat(
            model, messages, options=options,
            think=think, keep_alive=keep_alive,
        )

    def embed(self, model: str, text: str | list[str]) -> list[list[float]]:
        r = self._client.post(
            f"{self.base_url}/api/embed",
            json={"model": model, "input": text},
        )
        if r.status_code != 200:
            raise OllamaError(f"embed {model} -> HTTP {r.status_code}: {r.text[:300]}")
        return r.json().get("embeddings", [])

    def warm(self, model: str, keep_alive: str = "10m") -> float:
        import time
        t0 = time.perf_counter()
        self.chat(
            model,
            [{"role": "user", "content": "hi"}],
            options={"num_predict": 1},
            think=False,
            keep_alive=keep_alive,
        )
        return round((time.perf_counter() - t0) * 1000)

    def unload(self, model: str) -> None:
        self._client.post(
            f"{self.base_url}/api/chat",
            json={"model": model, "messages": [], "keep_alive": 0},
        )

    def loaded(self) -> list[dict[str, Any]]:
        r = self._client.get(f"{self.base_url}/api/ps")
        r.raise_for_status()
        return r.json().get("models", [])

    def close(self) -> None:
        self._client.close()
