"""Agent HTTP inside an OpenShell sandbox.

Every page the agent opens is fetched by ``curl`` running inside the mission's sandbox, so OpenShell's policy
engine, not Warrant, decides what gets through. Warrant reads OpenShell's own decision log afterwards and
turns each line into a security-feed event.
"""

from __future__ import annotations

import time
from collections.abc import Callable

import httpx

from . import openshell
from .client import Blocked
from .gate import Decision

MARK = "__WARRANT_HTTP_STATUS__"


def _decision(e: dict) -> Decision:
    return Decision(
        allowed=e["decision"] == "allowed",
        method=e.get("method") or "",
        url=e.get("url") or f"{e.get('host', '')}",
        host=e.get("host") or "",
        port=e.get("port") or 0,
        path=e.get("path") or "",
        rule_id=e.get("policy"),
        reason=f"OpenShell: {e['reason']}" if e.get("reason") else "OpenShell policy",
    )


class SandboxClient:
    def __init__(self, sandbox: openshell.Sandbox, on_decision: Callable[[Decision], None], timeout: int = 25):
        self.sandbox = sandbox
        self.on_decision = on_decision
        self.timeout = timeout
        self._seen: set[str] = set()
        self._recent: set[tuple] = set()

    def _new_decisions(self) -> list[dict]:
        fresh = []
        for e in openshell.decisions(self.sandbox, since="5m"):
            if e["raw"] in self._seen:
                continue
            self._seen.add(e["raw"])
            # Connection-level ALLOWED lines duplicate the HTTP-level ones; keep the feed readable.
            if e["layer"] == "connection" and e["decision"] == "allowed":
                continue
            # OpenShell logs a refused host twice (DNS refusal, then TCP denial); show it once.
            key = (e["layer"], e["decision"], e.get("host"), round(e["t"]))
            if e["layer"] == "connection" and key in self._recent:
                continue
            self._recent.add(key)
            fresh.append(e)
        return fresh

    def _matches(self, e: dict, method: str, url: httpx.URL) -> bool:
        if e["layer"] == "http":
            return e.get("method") == method and e.get("host") == url.host and e.get("path") == (url.path or "/")
        return e.get("host") == url.host

    def request(self, method: str, url: str, data: dict | None = None, **_: object) -> httpx.Response:
        method = method.upper()
        target = httpx.URL(url)
        cmd = ["curl", "-sS", "--max-time", str(self.timeout), "-X", method, "-w", MARK + "%{http_code}"]
        for key, value in (data or {}).items():
            cmd += ["--data-urlencode", f"{key}={value}"]
        result = openshell.exec_in(self.sandbox, [*cmd, url], timeout=self.timeout + 20)
        body, _sep, status_text = result.stdout.rpartition(MARK)
        status = int(status_text.strip()[:3]) if status_text.strip()[:3].isdigit() else 0

        # OpenShell writes its decision line just after answering, so wait briefly for the line for this request.
        mine: dict | None = None
        deadline = time.monotonic() + 6
        while True:
            for e in self._new_decisions():
                self.on_decision(_decision(e))
                if mine is None and self._matches(e, method, target):
                    mine = e
            if mine is not None or time.monotonic() > deadline:
                break
            time.sleep(0.5)

        if mine is not None and mine["decision"] == "blocked":
            raise Blocked(_decision(mine))
        if status == 0:
            why = (result.stderr or result.stdout).strip().splitlines()[-1:] or ["no response"]
            reason = f"OpenShell refused: {why[0][:160]}"
            raise Blocked(Decision(False, method, url, target.host, 0, target.path, None, reason))
        return httpx.Response(status, text=body, request=httpx.Request(method, url))

    def close(self) -> None:
        pass
