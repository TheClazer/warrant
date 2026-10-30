"""Development enforcer: an HTTP client that refuses any request the gate does not allow.

This is the default. With ``WARRANT_ENFORCER=openshell`` requests are made inside an OpenShell sandbox and
OpenShell's network proxy decides instead (see ``openshell.py``).
Every decision, allowed or blocked, is reported through ``on_decision``.
"""

from __future__ import annotations

from collections.abc import Callable

import httpx

from .gate import Decision, Gate


class Blocked(Exception):
    def __init__(self, decision: Decision):
        super().__init__(decision.reason)
        self.decision = decision


class GatedClient:
    def __init__(
        self,
        gate: Gate,
        on_decision: Callable[[Decision], None],
        transport: httpx.BaseTransport | None = None,
        timeout: float = 15.0,
        tokens: dict[str, str] | None = None,
    ):
        self.gate = gate
        self.on_decision = on_decision
        self.tokens = tokens or {}
        # Redirects are followed manually so every hop is checked against the gate.
        self._client = httpx.Client(
            timeout=timeout, follow_redirects=False, transport=transport, headers={"User-Agent": "Warrant-Agent/0.1"}
        )

    def request(self, method: str, url: str, **kwargs) -> httpx.Response:
        for _ in range(5):
            decision = self.gate.check(method, url)
            self.on_decision(decision)
            if not decision.allowed:
                raise Blocked(decision)
            # A token goes only to its own site, and only on a request the warrant allowed. Each redirect hop is decided again.
            token = self.tokens.get(decision.host)
            headers = {"Authorization": f"Bearer {token}"} if token else None
            response = self._client.request(method, url, headers=headers, **kwargs)
            if response.is_redirect and "location" in response.headers:
                url = str(response.url.join(response.headers["location"]))
                method, kwargs = "GET", {}
                continue
            return response
        raise httpx.TooManyRedirects("too many redirects", request=None)  # type: ignore[arg-type]

    def close(self) -> None:
        self._client.close()
