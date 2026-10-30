"""SandboxClient against recorded OpenShell behaviour: curl output plus decision lines that arrive late."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from warrant.enforce import openshell
from warrant.enforce.client import Blocked
from warrant.enforce.sandbox_client import MARK, SandboxClient

ALLOW = (
    "[1.0] [sandbox] [OCSF ] [ocsf] HTTP:GET [INFO] ALLOWED GET http://10.0.0.5:8201/announcements "
    "[policy:portal_read_announcements engine:l7]"
)
DENY = (
    "[2.0] [sandbox] [OCSF ] [ocsf] HTTP:GET [MED] DENIED GET http://10.0.0.5:8201/grades "
    "[policy:portal_read_announcements engine:l7] [reason:L7_REQUEST deny GET 10.0.0.5:8201/grades]"
)


@pytest.fixture
def fake_openshell(monkeypatch):
    log: list[str] = []
    responses = {
        "http://10.0.0.5:8201/announcements": ("<html><title>A</title><body>Hall B</body></html>", 200, ALLOW),
        "http://10.0.0.5:8201/grades": ('{"error":"policy_denied"}', 403, DENY),
    }
    state = {"pending": None}

    def exec_in(sandbox, command, timeout=300):
        body, status, line = responses[command[-1]]
        state["pending"] = line  # the decision line shows up on the *next* log read
        return subprocess.CompletedProcess(command, 0, stdout=f"{body}{MARK}{status}", stderr="")

    def decisions(sandbox, since="5m"):
        if state["pending"] and state["pending"] not in log:
            log.append(state["pending"])
            return openshell.parse_ocsf("\n".join(log[:-1]))
        return openshell.parse_ocsf("\n".join(log))

    monkeypatch.setattr(openshell, "exec_in", exec_in)
    monkeypatch.setattr(openshell, "decisions", decisions)
    monkeypatch.setattr("warrant.enforce.sandbox_client.time.sleep", lambda s: None)
    return openshell.Sandbox(name="wrt-test", policy_path=Path("p.yaml"))


def test_allowed_page_returns_body_and_records_decision(fake_openshell):
    seen = []
    client = SandboxClient(fake_openshell, seen.append)
    response = client.request("GET", "http://10.0.0.5:8201/announcements")
    assert response.status_code == 200 and "Hall B" in response.text
    assert [(d.allowed, d.path) for d in seen] == [(True, "/announcements")]


def test_denied_request_is_attributed_to_the_right_url(fake_openshell):
    seen = []
    client = SandboxClient(fake_openshell, seen.append)
    client.request("GET", "http://10.0.0.5:8201/announcements")
    with pytest.raises(Blocked) as info:
        client.request("GET", "http://10.0.0.5:8201/grades")
    assert info.value.decision.path == "/grades"
    assert "L7_REQUEST deny" in info.value.decision.reason
    assert [(d.allowed, d.path) for d in seen] == [(True, "/announcements"), (False, "/grades")]


@pytest.mark.parametrize("path", ["/announcements/%252e%252e/grades", "/announcements/..%5cgrades", "/announcements/..%2fgrades"])
def test_ambiguous_paths_never_reach_the_sandbox(fake_openshell, monkeypatch, path):
    def must_not_run(*_args, **_kwargs):
        raise AssertionError("curl ran")

    monkeypatch.setattr(openshell, "exec_in", must_not_run)
    seen = []
    client = SandboxClient(openshell.Sandbox("wrt-test", Path("p.yaml")), seen.append)
    with pytest.raises(Blocked):
        client.request("GET", "http://10.0.0.5:8201" + path)
    assert [d.allowed for d in seen] == [False]
