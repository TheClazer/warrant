from __future__ import annotations

import httpx

from warrant import guard
from warrant.prove import held, run_proof

from .test_guard import (
    Hello,  # noqa: F401
    origin,  # noqa: F401
)


def test_the_warrant_stops_what_broad_access_lets_through():
    outcomes = run_proof()
    bare, guarded = outcomes["without"], outcomes["with"]

    # With broad access, the damage is real and is seen at the receiving end.
    assert bare.attempts["Read your grades"] == "read"
    assert bare.submissions == 1
    assert any("18 / 20" in body for body in bare.stranger_received)

    # Under the warrant, the job still works and nothing else arrives anywhere.
    assert guarded.attempts["Read the announcements (its job)"] == "read"
    assert guarded.attempts["Read your grades"] == "BLOCKED"
    assert guarded.attempts["Submit Lab 4 as you"] == "BLOCKED"
    assert guarded.attempts["Send your data to a stranger"] == "BLOCKED"
    assert guarded.submissions == 0
    assert guarded.stranger_received == []
    assert held(outcomes)


def test_guard_can_be_imported_and_used_around_code(origin):  # noqa: F811
    with guard(allow=["127.0.0.1"]) as report:
        assert httpx.get(f"http://127.0.0.1:{origin}/page").status_code == 200
        assert httpx.get("http://not-allowed.invalid/secret").status_code == 403
    assert [s.target for s in report.allowed] == ["127.0.0.1/page"]
    assert [s.target for s in report.blocked] == ["not-allowed.invalid/secret"]


def test_guard_restores_the_environment(monkeypatch):
    monkeypatch.setenv("HTTPS_PROXY", "http://mine:1")
    monkeypatch.setenv("NO_PROXY", "x")
    import os

    with guard(allow=[]):
        assert os.environ["HTTPS_PROXY"] != "http://mine:1"
        assert "NO_PROXY" not in os.environ
    assert os.environ["HTTPS_PROXY"] == "http://mine:1"
    assert os.environ["NO_PROXY"] == "x"
