"""Parsing real OpenShell 0.1.5 decision logs captured during the deciding check on 2026-10-26."""

from __future__ import annotations

from pathlib import Path

from warrant.enforce.openshell import MAX_NAME, parse_ocsf, sandbox_name

LOG = (Path(__file__).parent / "fixtures" / "openshell_0.1.5_ocsf.log").read_text(encoding="utf-8")


def test_parses_allowed_and_denied_decisions_from_real_log():
    events = parse_ocsf(LOG)
    http = [e for e in events if e["layer"] == "http"]
    assert [(e["decision"], e["method"], e["path"]) for e in http] == [
        ("allowed", "GET", "/"),
        ("blocked", "POST", "/"),
        ("blocked", "GET", "/other"),
    ]
    assert all(e["host"] == "example.com" and e["port"] == 443 for e in http)
    assert http[1]["policy"] == "example_read_home"
    assert "not permitted by policy" in http[1]["reason"]


def test_parses_connection_level_denials_for_unlisted_hosts():
    blocked = [e for e in parse_ocsf(LOG) if e["layer"] == "connection" and e["decision"] == "blocked"]
    assert {e["host"] for e in blocked} == {"www.iana.org"}
    assert any(e["reason"] == "transparent_tcp_policy_denied" for e in blocked)


def test_ignores_non_decision_lines():
    assert parse_ocsf("[1.0] [sandbox] [OCSF ] [ocsf] CONFIG:READY [INFO] Policy DNS connected\nrandom text") == []


def test_sandbox_names_fit_openshell_limit():
    assert all(len(sandbox_name()) <= MAX_NAME for _ in range(50))
