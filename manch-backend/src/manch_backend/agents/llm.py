"""LLM client — thin wrapper around Google Gemini (primary) with fallback support."""
from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass, field
from typing import Any

import httpx

from manch_backend.config import settings
from manch_backend.models import ModelClass

logger = logging.getLogger(__name__)

# ── Model routing ────────────────────────────────────
_MODEL_MAP: dict[ModelClass, str] = {
    ModelClass.FAST: "gemini-2.0-flash",
    ModelClass.BALANCED: "gemini-2.5-flash-preview-05-20",
    ModelClass.REASONING: "gemini-2.5-pro-preview-05-06",
}


@dataclass
class LLMMessage:
    role: str  # "user" | "model" | "system"
    content: str


@dataclass
class LLMResponse:
    content: str
    model: str
    usage: dict[str, int] = field(default_factory=dict)
    tool_calls: list[dict[str, Any]] = field(default_factory=list)
    raw: dict[str, Any] = field(default_factory=dict)


class LLMClient:
    """Synchronous Gemini API client using REST (httpx)."""

    def __init__(self) -> None:
        self._api_key = settings.gemini_api_key or os.getenv("GEMINI_API_KEY", "")
        self._base_url = "https://generativelanguage.googleapis.com/v1beta"
        self._http = httpx.Client(timeout=120.0)

    # ── Public API ───────────────────────────────────
    def chat(
        self,
        messages: list[LLMMessage],
        model_class: ModelClass = ModelClass.BALANCED,
        temperature: float = 0.2,
        max_tokens: int = 8192,
        tools: list[dict[str, Any]] | None = None,
        response_format: str | None = None,
    ) -> LLMResponse:
        """Send a chat completion request to Gemini."""
        model = _MODEL_MAP.get(model_class, _MODEL_MAP[ModelClass.BALANCED])
        url = f"{self._base_url}/models/{model}:generateContent?key={self._api_key}"

        # Build Gemini payload
        system_instruction = None
        contents: list[dict[str, Any]] = []
        for msg in messages:
            if msg.role == "system":
                system_instruction = {"parts": [{"text": msg.content}]}
            else:
                role = "model" if msg.role in ("assistant", "model") else "user"
                contents.append({"role": role, "parts": [{"text": msg.content}]})

        body: dict[str, Any] = {
            "contents": contents,
            "generationConfig": {
                "temperature": temperature,
                "maxOutputTokens": max_tokens,
            },
        }
        if system_instruction:
            body["systemInstruction"] = system_instruction
        if tools:
            body["tools"] = tools
        if response_format == "json":
            body["generationConfig"]["responseMimeType"] = "application/json"

        logger.debug("LLM request: model=%s messages=%d", model, len(contents))
        resp = self._http.post(url, json=body)
        resp.raise_for_status()
        data = resp.json()

        return self._parse_response(data, model)

    def complete(
        self,
        prompt: str,
        model_class: ModelClass = ModelClass.BALANCED,
        system_prompt: str | None = None,
        temperature: float = 0.2,
        max_tokens: int = 8192,
        response_format: str | None = None,
    ) -> LLMResponse:
        """Simple prompt -> response convenience method."""
        messages = []
        if system_prompt:
            messages.append(LLMMessage(role="system", content=system_prompt))
        messages.append(LLMMessage(role="user", content=prompt))
        return self.chat(
            messages,
            model_class=model_class,
            temperature=temperature,
            max_tokens=max_tokens,
            response_format=response_format,
        )

    # ── Internal ─────────────────────────────────────
    @staticmethod
    def _parse_response(data: dict[str, Any], model: str) -> LLMResponse:
        candidates = data.get("candidates", [])
        if not candidates:
            return LLMResponse(content="", model=model, raw=data)

        parts = candidates[0].get("content", {}).get("parts", [])
        text_parts = [p["text"] for p in parts if "text" in p]
        content = "\n".join(text_parts)

        tool_calls = []
        for p in parts:
            if "functionCall" in p:
                tool_calls.append(p["functionCall"])

        usage_meta = data.get("usageMetadata", {})
        usage = {
            "prompt_tokens": usage_meta.get("promptTokenCount", 0),
            "completion_tokens": usage_meta.get("candidatesTokenCount", 0),
            "total_tokens": usage_meta.get("totalTokenCount", 0),
        }

        return LLMResponse(
            content=content,
            model=model,
            usage=usage,
            tool_calls=tool_calls,
            raw=data,
        )

    def close(self) -> None:
        self._http.close()


# Module-level singleton
llm_client = LLMClient()
