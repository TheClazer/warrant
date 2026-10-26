"""The policy gate: decide, for one outgoing request, whether the active warrant allows it.

In production this decision is made by NVIDIA OpenShell's network proxy from the rendered policy. The
same logic is implemented here for the local development proxy and for tests, so both paths agree.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from urllib.parse import urlsplit

from ..models import Rule, Warrant


@dataclass(frozen=True)
class Decision:
    allowed: bool
    method: str
    url: str
    host: str
    port: int
    path: str
    rule_id: str | None
    reason: str

    def event(self) -> dict:
        return {
            "decision": "allowed" if self.allowed else "blocked",
            "method": self.method,
            "url": self.url,
            "host": self.host,
            "port": self.port,
            "path": self.path,
            "rule": self.rule_id,
            "reason": self.reason,
        }


def split(url: str) -> tuple[str, int, str]:
    parts = urlsplit(url)
    host = (parts.hostname or "").lower()
    port = parts.port or (443 if parts.scheme == "https" else 80)
    return host, port, parts.path or "/"


class Gate:
    def __init__(self, decide: Callable[[str, str, int, str], Rule | None | bool], label: str):
        self._decide = decide
        self.label = label

    @classmethod
    def for_warrant(cls, warrant: Warrant) -> Gate:
        return cls(warrant.allows, f"warrant {warrant.id}")

    def check(self, method: str, url: str) -> Decision:
        host, port, path = split(url)
        verdict = self._decide(method.upper(), host, port, path)
        if verdict is True:
            return Decision(True, method.upper(), url, host, port, path, None, f"allowed by {self.label}")
        if isinstance(verdict, Rule):
            return Decision(True, method.upper(), url, host, port, path, verdict.id, f"matches {verdict.id}")
        return Decision(
            False,
            method.upper(),
            url,
            host,
            port,
            path,
            None,
            f"{method.upper()} {host}:{port}{path} is not in {self.label}",
        )


def allow_all() -> Gate:
    """Broad access, used only as the comparison setup in evaluation."""
    return Gate(lambda *_: True, "broad access")
