"""The policy gate: decide, for one outgoing request, whether the active warrant allows it.

With ``WARRANT_ENFORCER=openshell`` the decision is made by NVIDIA OpenShell's network proxy from the rendered
policy. This is the built-in enforcer, used otherwise. It runs inside the Warrant process, so it limits what the
agent's own HTTP client does; it is not a sandbox.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from urllib.parse import unquote

import httpx

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
    """Host, port and path as the HTTP client will send them. Parsing with a different library than the one
    making the request is how checks get bypassed: httpx turns ``/a/../b`` into ``/b`` before sending."""
    try:
        parts = httpx.URL(url)
    except (httpx.InvalidURL, TypeError):
        return "", 0, "/"
    port = parts.port or (443 if parts.scheme == "https" else 80)
    return parts.host.lower(), port, parts.raw_path.decode("ascii").split("?", 1)[0] or "/"


def ambiguous(path: str) -> bool:
    """Encoded dots and slashes, or backslashes, can mean a different path to the server than to this check."""
    lowered = path.lower()
    if "\\" in path or any(token in lowered for token in ("%2e", "%2f", "%5c", "%25")):
        return True
    return ".." in unquote(path).split("/")


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
        if isinstance(verdict, Rule) and ambiguous(path):
            verdict = None
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
