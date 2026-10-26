from __future__ import annotations

import json
from dataclasses import replace

import pytest

from warrant.config import Settings
from warrant.llm import ChatResult, Usage
from warrant.models import Mission
from warrant.sites import build_registry, capability_index


class Scripted:
    """A chat backend that returns prepared replies in order and records every request."""

    def __init__(self, replies: list[dict]):
        self.replies = list(replies)
        self.requests: list[dict] = []

    def chat(self, model, messages, **kwargs) -> ChatResult:
        self.requests.append({"model": model, "messages": messages, **kwargs})
        message = self.replies.pop(0)
        return ChatResult(message=message, usage=Usage(model, 100, 20, 0.01, None, kwargs.get("purpose", "")))


def json_reply(obj: dict) -> dict:
    return {"role": "assistant", "content": json.dumps(obj)}


@pytest.fixture
def settings(tmp_path) -> Settings:
    return replace(
        Settings(), data_dir=tmp_path, nebius_api_key="", portal_url="http://portal.test:8201", tavily_api_key=""
    )


@pytest.fixture
def catalogue(settings):
    return capability_index(build_registry(settings))


@pytest.fixture
def mission() -> Mission:
    return Mission(
        title="Morning course brief",
        text="Every morning, check my course portal for new announcements and deadlines and brief me.",
    )
