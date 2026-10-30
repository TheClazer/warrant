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

import os
import re
import secrets
import shlex
import shutil
import subprocess
import tempfile
import time
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


def cli() -> list[str]:
    """The OpenShell command. ``WARRANT_OPENSHELL_CMD`` overrides it, e.g. ``wsl -d Ubuntu -- openshell`` when the
    app runs on Windows and OpenShell runs in WSL during development."""
    override = os.environ.get("WARRANT_OPENSHELL_CMD", "").strip()
    if override:
        return shlex.split(override)
    path = shutil.which("openshell")
    if not path:
        raise OpenShellUnavailable("openshell CLI not found. Install it on the Linux host (see deploy/README.md).")
    return [path]


def _host_path(path: Path) -> str:
    """Path as the OpenShell CLI sees it. Through WSL, a Windows drive path becomes /mnt/<drive>/..."""
    command = cli()
    if command and Path(command[0]).stem.lower() == "wsl":
        resolved = path.resolve()
        drive = resolved.drive.rstrip(":").lower()
        return f"/mnt/{drive}" + resolved.as_posix()[len(resolved.drive) :]
    return str(path)


def _run(args: list[str], timeout: int = 120) -> subprocess.CompletedProcess[str]:
    # Output is parsed below, so colour codes must stay out of it whatever the caller's terminal asks for.
    env = {k: v for k, v in os.environ.items() if k != "FORCE_COLOR"} | {"NO_COLOR": "1"}
    return subprocess.run(
        [*cli(), *args],
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout,
        check=False,
    )


def create(
    warrant: Warrant, inference_url: str | None = None, image: str = DEFAULT_IMAGE, workdir: Path | None = None
) -> Sandbox:
    name = sandbox_name()
    directory = workdir or Path(tempfile.mkdtemp(prefix="warrant-"))
    directory.mkdir(parents=True, exist_ok=True)
    policy_path = directory / f"{name}.policy.yaml"
    policy_path.write_text(render_policy(warrant, inference_url=inference_url), encoding="utf-8")
    args = ["sandbox", "create", "--name", name, "--from", image, "--policy", _host_path(policy_path)]
    result = _run([*args, "--detach", "--no-tty", "--no-auto-providers"], timeout=900)
    if result.returncode != 0:
        raise OpenShellUnavailable(f"sandbox create failed: {(result.stderr or result.stdout).strip()[-500:]}")
    sandbox = Sandbox(name=name, policy_path=policy_path)
    wait_ready(sandbox)
    return sandbox


def wait_ready(sandbox: Sandbox, timeout_s: float = 180) -> None:
    """Block until OpenShell reports the sandbox Ready; a detached create returns before that."""
    deadline = time.monotonic() + timeout_s
    last = ""
    while time.monotonic() < deadline:
        last = _run(["sandbox", "get", sandbox.name], timeout=30).stdout
        if "Phase: Ready" in last:
            return
        if "Phase: Error" in last:
            break
        time.sleep(2)
    detail = next((line.strip() for line in last.splitlines() if "Ready:" in line), "not ready")
    delete(sandbox)
    raise OpenShellUnavailable(f"sandbox {sandbox.name} did not become ready: {detail}")


def exec_in(sandbox: Sandbox, command: list[str], timeout: int = 300) -> subprocess.CompletedProcess[str]:
    # OpenShell 0.1.5 runs exec arguments through a shell, so each argument is quoted to arrive intact.
    quoted = [shlex.quote(arg) for arg in command]
    return _run(["sandbox", "exec", "-n", sandbox.name, "--no-tty", "--", *quoted], timeout=timeout)


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


def raw_log(sandbox: Sandbox, since: str = "60m") -> list[str]:
    """OpenShell's own decision lines, unprocessed, so they can be kept after the sandbox is gone."""
    result = _run(["logs", sandbox.name, "--since", since, "--source", "sandbox"], timeout=60)
    return [line.strip() for line in result.stdout.splitlines() if "[OCSF" in line]


def delete(sandbox: Sandbox) -> None:
    _run(["sandbox", "delete", sandbox.name], timeout=120)
