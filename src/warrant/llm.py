"""Nebius Token Factory client for NVIDIA Nemotron (OpenAI-compatible chat completions).

Every call is recorded with model, tokens, latency and, when a price is configured, cost. The client has
no silent fallback: without a key it raises, and tests inject a scripted backend instead.
"""

from __future__ import annotations

import json
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any, Protocol

import httpx

from .config import Settings


class ModelUnavailable(RuntimeError):
    pass


class BudgetExceeded(RuntimeError):
    pass


@dataclass
class Usage:
    model: str
    prompt_tokens: int
    completion_tokens: int
    latency_s: float
    cost_usd: float | None
    purpose: str


@dataclass
class ChatResult:
    message: dict[str, Any]
    usage: Usage

    @property
    def content(self) -> str:
        return self.message.get("content") or ""

    @property
    def tool_calls(self) -> list[dict[str, Any]]:
        return self.message.get("tool_calls") or []


class ChatBackend(Protocol):
    def chat(
        self,
        model: str,
        messages: list[dict[str, Any]],
        *,
        tools: list[dict[str, Any]] | None = None,
        json_mode: bool = False,
        max_tokens: int = 1200,
        purpose: str = "",
    ) -> ChatResult: ...


@dataclass
class Ledger:
    """Running record of model usage for one run, a guest session, or an evaluation."""

    max_calls: int | None = None
    max_usd: float | None = None
    calls: list[Usage] = field(default_factory=list)
    on_record: Callable[[Usage], None] | None = None

    @property
    def cost_usd(self) -> float:
        return round(sum(u.cost_usd or 0.0 for u in self.calls), 8)

    @property
    def tokens(self) -> int:
        return sum(u.prompt_tokens + u.completion_tokens for u in self.calls)

    def reserve(self) -> None:
        if self.max_calls is not None and len(self.calls) >= self.max_calls:
            raise BudgetExceeded(f"model call cap reached ({self.max_calls})")
        if self.max_usd is not None and self.cost_usd >= self.max_usd:
            raise BudgetExceeded(f"spending cap reached (${self.max_usd:.2f})")

    def record(self, usage: Usage) -> None:
        self.calls.append(usage)
        if self.on_record:
            self.on_record(usage)

    def summary(self) -> dict[str, Any]:
        priced = all(u.cost_usd is not None for u in self.calls)
        return {
            "model_calls": len(self.calls),
            "prompt_tokens": sum(u.prompt_tokens for u in self.calls),
            "completion_tokens": sum(u.completion_tokens for u in self.calls),
            "cost_usd": self.cost_usd if priced else None,
            "models": sorted({u.model for u in self.calls}),
        }


class TokenFactory:
    """Live backend. One shared HTTP client, bounded responses, no automatic retries on 4xx."""

    def __init__(self, settings: Settings, transport: httpx.BaseTransport | None = None):
        if not settings.live_model:
            raise ModelUnavailable("NEBIUS_API_KEY is not set")
        self.settings = settings
        self.client = httpx.Client(
            base_url=settings.token_factory_url,
            timeout=httpx.Timeout(90, connect=10),
            headers={"Authorization": f"Bearer {settings.nebius_api_key}"},
            transport=transport,
        )

    def _cost(self, model: str, prompt: int, completion: int) -> float | None:
        price = self.settings.prices.get(model)
        if not price:
            return None
        return round((prompt * price[0] + completion * price[1]) / 1_000_000, 8)

    def chat(self, model, messages, *, tools=None, json_mode=False, max_tokens=1200, purpose=""):
        body: dict[str, Any] = {"model": model, "messages": messages, "temperature": 0, "max_tokens": max_tokens}
        if tools:
            body["tools"] = tools
            body["tool_choice"] = "auto"
        if json_mode:
            body["response_format"] = {"type": "json_object"}
        started = time.perf_counter()
        last_error = ""
        for attempt in range(5):
            try:
                response = self.client.post("/chat/completions", json=body)
            except httpx.HTTPError as exc:
                last_error = type(exc).__name__
                time.sleep(1.5 * (attempt + 1))
                continue
            if response.status_code in {429, 500, 502, 503, 504, 529}:
                last_error = f"HTTP {response.status_code}"
                time.sleep(2.0 * (attempt + 1))
                continue
            if response.status_code != 200:
                raise ModelUnavailable(f"Token Factory returned HTTP {response.status_code}")
            data = response.json()
            usage = data.get("usage") or {}
            prompt = int(usage.get("prompt_tokens") or 0)
            completion = int(usage.get("completion_tokens") or 0)
            return ChatResult(
                message=data["choices"][0]["message"],
                usage=Usage(
                    model,
                    prompt,
                    completion,
                    round(time.perf_counter() - started, 3),
                    self._cost(model, prompt, completion),
                    purpose,
                ),
            )
        raise ModelUnavailable(f"Token Factory unavailable after retries ({last_error})")


class Metered:
    """Wraps a backend so every call is capped and recorded on a ledger."""

    def __init__(self, backend: ChatBackend, ledger: Ledger):
        self.backend = backend
        self.ledger = ledger

    def chat(self, model, messages, **kwargs) -> ChatResult:
        self.ledger.reserve()
        result = self.backend.chat(model, messages, **kwargs)
        self.ledger.record(result.usage)
        return result


def parse_json_object(text: str) -> dict[str, Any]:
    """Accept a bare JSON object, or one wrapped in prose or a code fence."""
    text = text.strip()
    try:
        value = json.loads(text)
    except json.JSONDecodeError:
        start, end = text.find("{"), text.rfind("}")
        if start < 0 or end <= start:
            raise ValueError("model reply contained no JSON object") from None
        value = json.loads(text[start : end + 1])
    if not isinstance(value, dict):
        raise ValueError("model reply was not a JSON object")
    return value
