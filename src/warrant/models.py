"""Core data types: missions, capabilities, rules and warrants.

A warrant is the unit of trust. It lists, for one mission, exactly which network requests the agent may
make. Every rule comes from a capability in the site registry, never from free model output, and every
rule has one plain-language line the user reads before approving.
"""

from __future__ import annotations

import hashlib
import json
import re
import time
import uuid
from functools import lru_cache
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

Method = Literal["GET", "HEAD", "POST", "PUT", "PATCH", "DELETE"]
WRITE_METHODS: frozenset[str] = frozenset({"POST", "PUT", "PATCH", "DELETE"})
HOST_RE = re.compile(r"^[a-z0-9]([a-z0-9-]*[a-z0-9])?(\.[a-z0-9]([a-z0-9-]*[a-z0-9])?)*$")


def new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:12]}"


def now() -> float:
    return round(time.time(), 3)


def canonical(obj: BaseModel | dict | list) -> str:
    data = obj.model_dump(mode="json") if isinstance(obj, BaseModel) else obj
    return json.dumps(data, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


class Frozen(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


@lru_cache(maxsize=512)
def _glob_regex(pattern: str) -> re.Pattern[str]:
    """OpenShell-style path glob: ``**`` crosses segments, ``*`` stays within one segment."""
    out = []
    i = 0
    while i < len(pattern):
        if pattern.startswith("**", i):
            out.append(".*")
            i += 2
        elif pattern[i] == "*":
            out.append("[^/]*")
            i += 1
        else:
            out.append(re.escape(pattern[i]))
            i += 1
    return re.compile("^" + "".join(out) + "$")


def covers_whole_site(pattern: str) -> bool:
    """True when a glob has no fixed first path segment, such as ``/**``, ``/*/**`` or ``/**/*``."""
    return pattern.lstrip("/").startswith("*")


def path_matches(pattern: str, path: str) -> bool:
    return bool(_glob_regex(pattern).match(path))


class Rule(Frozen):
    """One allowed kind of request: methods on path globs of a single host and port."""

    id: Annotated[str, Field(pattern=r"^[a-z0-9][a-z0-9_.-]{0,63}$")]
    host: str
    port: Annotated[int, Field(ge=1, le=65535)]
    scheme: Literal["http", "https"] = "https"
    methods: Annotated[tuple[Method, ...], Field(min_length=1)]
    paths: Annotated[tuple[str, ...], Field(min_length=1)]

    @field_validator("host")
    @classmethod
    def _host(cls, v: str) -> str:
        v = v.lower()
        if not HOST_RE.match(v):
            raise ValueError("host must be a literal hostname, no wildcards")
        return v

    @field_validator("paths")
    @classmethod
    def _paths(cls, v: tuple[str, ...]) -> tuple[str, ...]:
        for p in v:
            if not p.startswith("/") or ".." in p or len(p) > 512:
                raise ValueError(f"invalid path glob {p!r}")
        return v

    @property
    def writes(self) -> bool:
        return bool(WRITE_METHODS & set(self.methods))

    def allows(self, method: str, host: str, port: int, path: str) -> bool:
        return (
            host.lower() == self.host
            and port == self.port
            and method.upper() in self.methods
            and any(path_matches(p, path) for p in self.paths)
        )


class Capability(Frozen):
    """A named, pre-reviewed ability on a known site. The compiler can only choose from these."""

    id: Annotated[str, Field(pattern=r"^[a-z0-9][a-z0-9_.-]{0,63}$")]
    site: str
    summary: str
    plain: str
    rule: Rule

    @property
    def writes(self) -> bool:
        return self.rule.writes


class Site(Frozen):
    id: str
    name: str
    base_url: str
    capabilities: tuple[Capability, ...]


class Mission(BaseModel):
    id: str = Field(default_factory=lambda: new_id("msn"))
    title: str
    text: Annotated[str, Field(min_length=3, max_length=2000)]
    schedule: str | None = None
    created_at: float = Field(default_factory=now)

    @property
    def text_sha256(self) -> str:
        return sha256(self.text.strip())


class Grant(Frozen):
    """A capability chosen for a mission, with the model's one-line reason."""

    capability: Capability
    reason: str = ""


WarrantStatus = Literal["draft", "checked", "rejected_by_checker", "approved", "rejected", "expired"]


class Warrant(BaseModel):
    id: str = Field(default_factory=lambda: new_id("wrt"))
    mission_id: str
    mission_sha256: str
    grants: tuple[Grant, ...]
    cannot: tuple[str, ...] = ()
    per_run_approval: bool = False
    model: str | None = None
    status: WarrantStatus = "draft"
    checker_findings: tuple[str, ...] = ()
    notes: tuple[str, ...] = ()
    created_at: float = Field(default_factory=now)
    decided_at: float | None = None
    decided_by: str | None = None

    @property
    def rules(self) -> tuple[Rule, ...]:
        return tuple(g.capability.rule for g in self.grants)

    @property
    def writes(self) -> bool:
        return any(r.writes for r in self.rules)

    @property
    def hosts(self) -> tuple[str, ...]:
        return tuple(sorted({f"{r.host}:{r.port}" for r in self.rules}))

    @property
    def fingerprint(self) -> str:
        body = {"mission_sha256": self.mission_sha256, "rules": [r.model_dump(mode="json") for r in self.rules]}
        return sha256(canonical(body))

    def allows(self, method: str, host: str, port: int, path: str) -> Rule | None:
        for rule in self.rules:
            if rule.allows(method, host, port, path):
                return rule
        return None

    def view(self) -> dict:
        """Shape sent to the interface: plain lines first, technical rules second."""
        return {
            "id": self.id,
            "mission_id": self.mission_id,
            "status": self.status,
            "can": [
                {
                    "capability": g.capability.id,
                    "text": g.capability.plain,
                    "reason": g.reason,
                    "writes": g.capability.writes,
                }
                for g in self.grants
            ],
            "cannot": list(self.cannot),
            "per_run_approval": self.per_run_approval,
            "rules": [r.model_dump(mode="json") for r in self.rules],
            "fingerprint": self.fingerprint,
            "checker_findings": list(self.checker_findings),
            "notes": list(self.notes),
            "model": self.model,
            "created_at": self.created_at,
            "decided_at": self.decided_at,
            "decided_by": self.decided_by,
        }
