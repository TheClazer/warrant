"""NVIDIA OpenShell backend: one sandbox per mission run, created with the warrant's policy.

Commands follow the OpenShell documentation ("Manage Sandbox Policies"):

    openshell sandbox create --name NAME --policy policy.yaml
    openshell policy set NAME --policy policy.yaml --wait
    openshell logs NAME --since 10m --source sandbox
    openshell sandbox delete NAME

OpenShell is alpha software. This module is exercised on the Linux host by ``warrant openshell-check``;
the log-line parser is deliberately tolerant and keeps the raw line with every event.
"""

from __future__ import annotations

import contextlib
import json
import re
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path

from ..models import Warrant
from ..policy import render_policy

DENY_WORDS = re.compile(r"\b(deny|denied|blocked|reject(ed)?)\b", re.IGNORECASE)
TARGET = re.compile(
    r"(?P<method>GET|POST|PUT|PATCH|DELETE|HEAD|CONNECT)?\s*(?P<host>[a-z0-9.-]+\.[a-z]{2,}|\d+\.\d+\.\d+\.\d+)(:(?P<port>\d+))?(?P<path>/\S*)?",
    re.IGNORECASE,
)


class OpenShellUnavailable(RuntimeError):
    pass


@dataclass
class Sandbox:
    name: str
    policy_path: Path


def cli() -> str:
    path = shutil.which("openshell")
    if not path:
        raise OpenShellUnavailable("openshell CLI not found. Install it on the Linux host (see deploy/README.md).")
    return path


def _run(args: list[str], timeout: int = 120) -> subprocess.CompletedProcess[str]:
    return subprocess.run([cli(), *args], capture_output=True, text=True, timeout=timeout, check=False)


def create(warrant: Warrant, name: str, inference_url: str, workdir: Path | None = None) -> Sandbox:
    directory = workdir or Path(tempfile.mkdtemp(prefix="warrant-"))
    policy_path = directory / f"{name}.policy.yaml"
    policy_path.write_text(render_policy(warrant, inference_url=inference_url), encoding="utf-8")
    result = _run(["sandbox", "create", "--name", name, "--policy", str(policy_path)])
    if result.returncode != 0:
        raise OpenShellUnavailable(f"sandbox create failed: {result.stderr.strip()[:500]}")
    return Sandbox(name=name, policy_path=policy_path)


def denials(sandbox: Sandbox, since: str = "10m") -> list[dict]:
    """Parse denied requests from the sandbox log. JSON lines are used when OpenShell emits them."""
    result = _run(["logs", sandbox.name, "--since", since, "--source", "sandbox"], timeout=30)
    events = []
    for line in result.stdout.splitlines():
        record: dict = {}
        with contextlib.suppress(json.JSONDecodeError):
            record = json.loads(line)
        text = json.dumps(record) if record else line
        if not DENY_WORDS.search(text):
            continue
        match = TARGET.search(text)
        events.append(
            {
                "decision": "blocked",
                "method": (match.group("method") or "").upper() if match else "",
                "host": match.group("host") if match else "",
                "port": int(match.group("port")) if match and match.group("port") else None,
                "path": match.group("path") if match else "",
                "reason": "denied by OpenShell policy",
                "raw": line[:500],
            }
        )
    return events


def delete(sandbox: Sandbox) -> None:
    _run(["sandbox", "delete", sandbox.name], timeout=60)
