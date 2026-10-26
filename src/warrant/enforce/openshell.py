"""NVIDIA OpenShell backend: one sandbox per mission run, created with the warrant's policy.

Verified against OpenShell 0.1.5 (Linux, native Docker Engine) on 2026-10-26:

    openshell sandbox create --name NAME --from IMAGE --policy policy.yaml --detach --no-tty --no-auto-providers
    openshell sandbox exec -n NAME --no-tty -- CMD
    openshell logs NAME --since 10m --source sandbox
    openshell sandbox delete NAME

Sandbox names are limited to 19 characters. Policy decisions are logged as OCSF lines, for example::

    [1793024149.462] [sandbox] [OCSF ] [ocsf] HTTP:POST [MED] DENIED POST https://example.com/
        [policy:example_read_home engine:l7] [reason:L7_REQUEST deny POST example.com:443/ ...]
"""

from __future__ import annotations

import re
import secrets
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlsplit

from ..models import Warrant
from ..policy import render_policy

MAX_NAME = 19
DEFAULT_IMAGE = "warrant-sandbox:dev"  # built from deploy/sandbox.Dockerfile

OCSF = re.compile(
    r"^\[(?P<ts>[\d.]+)\]\s+\[sandbox\]\s+\[OCSF\s*\]\s+\[ocsf\]\s+"
    r"(?P<cls>HTTP:[A-Z]+|NET:OPEN|NET:REFUSE)\s+\[(?P<sev>[A-Z]+)\]\s+(?P<decision>ALLOWED|DENIED)\s+(?P<rest>.*)$"
)
HTTP_TARGET = re.compile(r"^(?P<method>[A-Z]+)\s+(?P<url>https?://\S+)")
NET_TARGET = re.compile(r"(?:(?P<binary>/\S+?)\(\d+\)\s+->\s+)?(?P<host>[A-Za-z0-9.-]+)(?::(?P<port>\d+))?")
TAG = re.compile(r"\[(policy|reason):([^\]]*)\]")


class OpenShellUnavailable(RuntimeError):
    pass


@dataclass
class Sandbox:
    name: str
    policy_path: Path


def sandbox_name(prefix: str = "wrt") -> str:
    return f"{prefix}-{secrets.token_hex(6)}"[:MAX_NAME]


def cli() -> str:
    path = shutil.which("openshell")
    if not path:
        raise OpenShellUnavailable("openshell CLI not found. Install it on the Linux host (see deploy/README.md).")
    return path


def _run(args: list[str], timeout: int = 120) -> subprocess.CompletedProcess[str]:
    return subprocess.run([cli(), *args], capture_output=True, text=True, timeout=timeout, check=False)


def create(
    warrant: Warrant, inference_url: str | None = None, image: str = DEFAULT_IMAGE, workdir: Path | None = None
) -> Sandbox:
    name = sandbox_name()
    directory = workdir or Path(tempfile.mkdtemp(prefix="warrant-"))
    policy_path = directory / f"{name}.policy.yaml"
    policy_path.write_text(render_policy(warrant, inference_url=inference_url), encoding="utf-8")
    args = ["sandbox", "create", "--name", name, "--from", image, "--policy", str(policy_path)]
    result = _run([*args, "--detach", "--no-tty", "--no-auto-providers"], timeout=900)
    if result.returncode != 0:
        raise OpenShellUnavailable(f"sandbox create failed: {(result.stderr or result.stdout).strip()[-500:]}")
    return Sandbox(name=name, policy_path=policy_path)


def exec_in(sandbox: Sandbox, command: list[str], timeout: int = 300) -> subprocess.CompletedProcess[str]:
    return _run(["sandbox", "exec", "-n", sandbox.name, "--no-tty", "--", *command], timeout=timeout)


def parse_ocsf(lines: str) -> list[dict]:
    """Turn OpenShell OCSF log lines into Warrant network events (both allowed and denied)."""
    events = []
    for line in lines.splitlines():
        m = OCSF.match(line.strip())
        if not m:
            continue
        rest = m.group("rest")
        tags = dict(TAG.findall(rest))
        denied = m.group("decision") == "DENIED"
        event: dict = {
            "decision": "blocked" if denied else "allowed",
            "layer": "http" if m.group("cls").startswith("HTTP") else "connection",
            "t": float(m.group("ts")),
            "severity": m.group("sev"),
            "policy": (tags.get("policy") or "").split(" ")[0] or None,
            "reason": tags.get("reason") or ("denied by OpenShell policy" if denied else ""),
            "raw": line.strip()[:600],
        }
        http = HTTP_TARGET.match(rest)
        if http:
            parts = urlsplit(http.group("url"))
            event |= {
                "method": http.group("method"),
                "url": http.group("url"),
                "host": parts.hostname or "",
                "port": parts.port or (443 if parts.scheme == "https" else 80),
                "path": parts.path or "/",
            }
        else:
            net = NET_TARGET.search(rest)
            event |= {
                "method": "CONNECT",
                "host": net.group("host") if net else "",
                "port": int(net.group("port")) if net and net.group("port") else None,
                "path": "",
                "binary": net.group("binary") if net else None,
            }
        events.append(event)
    return events


def decisions(sandbox: Sandbox, since: str = "10m") -> list[dict]:
    result = _run(["logs", sandbox.name, "--since", since, "--source", "sandbox"], timeout=60)
    return parse_ocsf(result.stdout)


def delete(sandbox: Sandbox) -> None:
    _run(["sandbox", "delete", sandbox.name], timeout=120)
