"""Attempts to get past the checks, including ones found by reviewing the code as an attacker would."""

from __future__ import annotations

from dataclasses import replace

import httpx
import pytest
from fastapi.testclient import TestClient

from warrant.api import LOOPBACK, create_app
from warrant.checker import check
from warrant.compiler import default_cannot
from warrant.config import Settings
from warrant.enforce.client import Blocked, GatedClient
from warrant.enforce.gate import Gate
from warrant.memory import briefing, record_refusals
from warrant.models import Grant, Mission, Warrant
from warrant.runner import execute
from warrant.sites import add_site, build_registry
from warrant.store import Store

from .conftest import Scripted

PORTAL = "http://portal.test:8201"


def warrant_for(mission: Mission, catalogue, *ids: str) -> Warrant:
    return Warrant(
        mission_id=mission.id,
        mission_sha256=mission.text_sha256,
        grants=tuple(Grant(capability=catalogue[i]) for i in ids),
        cannot=default_cannot(False),
        status="approved",
    )


@pytest.fixture
def gate(catalogue) -> Gate:
    mission = Mission(title="t", text="read announcements")
    return Gate.for_warrant(warrant_for(mission, catalogue, "portal.read.announcements"))


@pytest.mark.parametrize(
    "path",
    [
        "/grades",
        "/announcements/../grades",
        "/announcements/./../grades",
        "/announcements/x/../../grades",
        "/announcements/%2e%2e/grades",
        "/announcements/%2E%2E/grades",
        "/announcements/..%2fgrades",
        "/announcements/%252e%252e/grades",
        "/announcements/..%5cgrades",
    ],
)
def test_path_tricks_cannot_leave_the_warrant(gate, path):
    assert not gate.check("GET", PORTAL + path).allowed


@pytest.mark.parametrize("path", ["/announcements", "/announcements/a1", "/announcements?week=1"])
def test_ordinary_paths_still_work(gate, path):
    assert gate.check("GET", PORTAL + path).allowed


def test_the_path_checked_is_the_path_sent(gate):
    sent = []

    def respond(request: httpx.Request) -> httpx.Response:
        sent.append(request.url.raw_path)
        return httpx.Response(200, text="ok")

    client = GatedClient(gate, lambda _: None, transport=httpx.MockTransport(respond))
    with pytest.raises(Blocked):
        client.request("GET", f"{PORTAL}/announcements/../grades")
    assert sent == []


@pytest.mark.parametrize(
    "url",
    ["http://evil.example@portal.test:1/announcements", "http://portal.test:8201@evil.example/announcements", "not a url"],
)
def test_host_tricks_are_blocked(gate, url):
    assert not gate.check("GET", url).allowed


@pytest.mark.parametrize("glob", ["/**", "/*", "/*/**", "/**/*"])
def test_checker_refuses_whole_site_globs_in_any_spelling(catalogue, glob):
    cap = catalogue["portal.read.grades"]
    wide = cap.model_copy(update={"rule": cap.rule.model_copy(update={"paths": (glob,)})})
    mission = Mission(title="t", text="grades")
    warrant = Warrant(mission_id=mission.id, mission_sha256=mission.text_sha256, grants=(Grant(capability=wide),))
    assert not check(warrant, mission, {**catalogue, cap.id: wide}).ok


@pytest.mark.parametrize(
    ("name", "read"),
    [("My Site", ["/pages"]), ("wiki", ["/a/../b"]), ("wiki", ["/*/**"]), ("wiki", ["pages"])],
)
def test_add_site_refuses_bad_input_and_leaves_the_registry_working(settings, tmp_path, monkeypatch, name, read):
    monkeypatch.setenv("WARRANT_SITES", str(tmp_path / "sites.yaml"))
    with pytest.raises(ValueError):
        add_site(name, "https://wiki.example.com", read, [])
    assert build_registry(settings)


def test_unknown_enforcer_is_refused():
    with pytest.raises(ValueError):
        replace(Settings(), enforcer="openshel")


def test_saved_answers_do_not_reach_jobs_that_can_write(tmp_path):
    store = Store(tmp_path / "m.sqlite")
    mission = Mission(title="a", text="job")
    store.remember("last", "text a page planted", key=mission.text_sha256)
    assert "planted" in briefing(store, mission)[0]
    assert "planted" not in briefing(store, mission, writes=True)[0]


def test_real_runs_tell_the_agent_pages_are_untrusted(tmp_path, catalogue):
    store = Store(tmp_path / "m.sqlite")
    mission = store.save_mission(Mission(title="a", text="announcements"))
    warrant = store.save_warrant(warrant_for(mission, catalogue, "portal.read.announcements"))
    backend = Scripted([{"role": "assistant", "content": "Done"}])
    execute(store, mission, warrant, start_url=PORTAL, backend=backend, model="m", use_memory=True)
    assert "untrusted" in backend.requests[0]["messages"][0]["content"]


@pytest.fixture
def secured(settings):
    return TestClient(create_app(replace(settings, admin_token="x" * 32), backend=Scripted([])))


@pytest.mark.parametrize("path", ["/api/missions", "/api/runs", "/api/memory", "/api/skills", "/api/catalogue"])
def test_owner_token_protects_reads(secured, path):
    assert secured.get(path).status_code == 401
    assert secured.get(path, headers={"Authorization": "Bearer " + "x" * 32}).status_code == 200


def test_event_stream_can_use_a_query_token_because_eventsource_cannot_send_headers(secured):
    assert secured.get("/api/runs?token=wrong").status_code == 401
    assert secured.get("/api/runs?token=" + "x" * 32).status_code == 200
    assert secured.get("/api/runs?token=caf%C3%A9").status_code == 401


def test_status_and_published_evaluation_stay_public(secured):
    assert secured.get("/api/status").status_code == 200
    assert secured.get("/api/eval/summary").status_code == 200


def test_other_websites_cannot_write_but_the_app_itself_can(settings):
    client = TestClient(create_app(replace(settings), backend=Scripted([])))
    assert client.post("/api/memory", json={"text": "x"}, headers={"Origin": "https://evil.example"}).status_code == 403
    assert client.post("/api/memory", json={"text": "x"}, headers={"Origin": "http://testserver"}).status_code == 201
    assert client.post("/api/memory", json={"text": "x"}).status_code == 201


def test_loopback_server_refuses_foreign_host_names(settings):
    client = TestClient(create_app(replace(settings), backend=Scripted([]), allowed_hosts=LOOPBACK))
    assert client.get("/api/status", headers={"Host": "evil.example"}).status_code == 400
    assert client.get("/api/status", headers={"Host": "127.0.0.1:8090"}).status_code == 200
    assert client.get("/api/status", headers={"Host": "localhost:8090"}).status_code == 200


def test_invalid_schedule_is_refused(settings):
    client = TestClient(create_app(replace(settings), backend=Scripted([])))
    bad = {"title": "t", "text": "abc", "schedule": "every tuesday maybe"}
    assert client.post("/api/missions", json=bad).status_code == 422
    assert client.post("/api/missions", json={**bad, "schedule": "daily 07:30"}).status_code == 201


def test_a_run_refuses_a_warrant_that_no_longer_matches_the_reviewed_list(settings, catalogue, tmp_path):
    store = Store(tmp_path / "m.sqlite")
    mission = store.save_mission(Mission(title="a", text="announcements"))
    old = catalogue["portal.read.announcements"]
    stale = old.model_copy(update={"rule": old.rule.model_copy(update={"paths": ("/announcements", "/grades")})})
    warrant = Warrant(
        mission_id=mission.id, mission_sha256=mission.text_sha256, grants=(Grant(capability=stale),), status="approved"
    )
    store.save_warrant(warrant)
    client = TestClient(create_app(replace(settings), backend=Scripted([]), store=store))
    response = client.post(f"/api/missions/{mission.id}/runs", json={})
    assert response.status_code == 409 and "changed" in response.json()["detail"]


def test_runs_cut_off_by_a_restart_are_closed(settings, tmp_path):
    store = Store(tmp_path / "m.sqlite")
    mission = store.save_mission(Mission(title="a", text="job"))
    rid = store.start_run(mission.id, None, "warrant", "owner")
    create_app(replace(settings), backend=Scripted([]), store=store)
    assert store.run(rid)["status"] == "failed"
    assert store.events(rid)[-1]["kind"] == "done"


def test_refusals_still_work_with_the_stricter_gate(tmp_path, catalogue):
    store = Store(tmp_path / "m.sqlite")
    record_refusals(store, Mission(title="a", text="job"), ["portal.read.grades"], catalogue)
    assert store.memories("refusal")
