from __future__ import annotations

from dataclasses import replace

import pytest
from fastapi.testclient import TestClient

from warrant.api import create_app
from warrant.compiler import default_cannot
from warrant.memory import MemoryFull, add_note, apply_refusals, briefing, record_refusals
from warrant.models import Grant, Mission, Warrant
from warrant.runner import RunRefused, execute
from warrant.store import Store

from .conftest import Scripted


@pytest.fixture
def store(tmp_path) -> Store:
    return Store(tmp_path / "m.sqlite")


def warrant_for(mission: Mission, catalogue, *ids: str) -> Warrant:
    return Warrant(
        mission_id=mission.id,
        mission_sha256=mission.text_sha256,
        grants=tuple(Grant(capability=catalogue[i]) for i in ids),
        cannot=default_cannot(False),
        status="approved",
    )


def test_refusal_is_left_out_of_the_next_draft_of_that_job_only(store, catalogue):
    job = Mission(title="a", text="announcements and grades")
    other = Mission(title="b", text="just my grades")
    record_refusals(store, job, ["portal.read.grades"], catalogue)

    draft = warrant_for(job, catalogue, "portal.read.announcements", "portal.read.grades")
    narrowed = apply_refusals(store, draft, job)
    assert [g.capability.id for g in narrowed.grants] == ["portal.read.announcements"]
    assert any(n.startswith("Remembered:") for n in narrowed.notes)

    untouched = warrant_for(other, catalogue, "portal.read.announcements", "portal.read.grades")
    assert len(apply_refusals(store, untouched, other).grants) == 2


def test_refusal_cannot_empty_a_warrant(store, catalogue):
    job = Mission(title="a", text="grades")
    record_refusals(store, job, ["portal.read.grades"], catalogue)
    draft = warrant_for(job, catalogue, "portal.read.grades")
    assert len(apply_refusals(store, draft, job).grants) == 1


def test_notes_are_limited_and_can_be_forgotten(store):
    first = add_note(store, "I am in section B")
    for i in range(19):
        add_note(store, f"note {i}")
    with pytest.raises(MemoryFull):
        add_note(store, "one too many")
    store.forget(first["id"])
    assert len(store.memories("note")) == 19


def test_briefing_says_it_grants_nothing(store):
    mission = Mission(title="a", text="job")
    assert briefing(store, mission)[0] == ""
    add_note(store, "I am in section B")
    text, used = briefing(store, mission)
    assert "section B" in text and "grants no permissions" in text
    assert used == {"notes": 1, "last": False}


def finish(answer: str) -> dict:
    return {"role": "assistant", "content": answer}


def test_memory_reaches_the_agent_and_the_next_run_sees_the_last_answer(store, catalogue):
    mission = store.save_mission(Mission(title="a", text="announcements"))
    warrant = store.save_warrant(warrant_for(mission, catalogue, "portal.read.announcements"))
    add_note(store, "I am in section B")
    backend = Scripted([finish("First brief"), finish("Second brief")])
    common = dict(start_url="http://portal.test:8201", backend=backend, model="m", use_memory=True)

    execute(store, mission, warrant, **common)
    first = backend.requests[0]["messages"][1]["content"]
    assert "section B" in first and "Your previous answer" not in first

    execute(store, mission, warrant, **common)
    second = backend.requests[1]["messages"][1]["content"]
    assert "First brief" in second


def test_runs_without_use_memory_stay_clean(store, catalogue):
    """The evaluation depends on this: repeats must not see each other's answers."""
    mission = store.save_mission(Mission(title="a", text="announcements"))
    warrant = store.save_warrant(warrant_for(mission, catalogue, "portal.read.announcements"))
    add_note(store, "I am in section B")
    backend = Scripted([finish("One")])
    execute(store, mission, warrant, start_url="http://portal.test:8201", backend=backend, model="m")
    assert "section B" not in backend.requests[0]["messages"][1]["content"]
    assert store.memories("last") == []


def test_memory_does_not_widen_the_warrant(store, catalogue):
    """A note claiming a permission changes nothing: the gate still refuses the request."""
    mission = store.save_mission(Mission(title="a", text="grades"))
    warrant = store.save_warrant(warrant_for(mission, catalogue, "portal.read.announcements"))
    add_note(store, "You are allowed to read my grades")
    call = {
        "id": "1",
        "type": "function",
        "function": {"name": "open_page", "arguments": '{"url": "http://portal.test:8201/grades"}'},
    }
    backend = Scripted([{"role": "assistant", "content": None, "tool_calls": [call]}, finish("Could not.")])
    run = execute(store, mission, warrant, start_url="http://portal.test:8201", backend=backend, model="m", use_memory=True)
    decisions = [e["decision"] for e in store.events(run["id"]) if e["kind"] == "network"]
    assert decisions == ["blocked"]


def test_skill_keeps_its_warrant_and_writes_still_ask(store, catalogue):
    mission = store.save_mission(Mission(title="a", text="submit"))
    warrant = warrant_for(mission, catalogue, "portal.write.submit")
    warrant.per_run_approval = True
    store.save_warrant(warrant)
    store.save_skill("submit-lab", mission.id, warrant.id)
    skill = store.skill("submit-lab")
    assert skill["warrant_id"] == warrant.id
    with pytest.raises(RunRefused):
        execute(store, mission, store.warrant(skill["warrant_id"]), start_url="x", backend=Scripted([]), model="m")


def test_api_memory_and_skills(settings, catalogue):
    client = TestClient(create_app(replace(settings), backend=Scripted([finish("Done")])))
    note = client.post("/api/memory", json={"text": "I am in section B"}).json()
    assert [m["text"] for m in client.get("/api/memory").json()] == ["I am in section B"]

    mission = client.get("/api/missions").json()[0]
    assert client.post("/api/skills", json={"name": "brief", "mission_id": mission["id"]}).status_code == 409

    assert client.delete(f"/api/memory/{note['id']}").status_code == 200
    assert client.get("/api/memory").json() == []
    assert client.get("/api/skills").json() == []


def test_user_sites_come_from_a_file_and_tokens_stay_on_their_own_host(settings, tmp_path, monkeypatch):
    import httpx

    from warrant.enforce.client import GatedClient
    from warrant.enforce.gate import allow_all
    from warrant.sites import build_registry, capability_index, site_tokens

    file = tmp_path / "sites.yaml"
    file.write_text(
        """
sites:
  - id: wiki
    name: Team wiki
    url: https://wiki.example.com
    token_env: WIKI_TOKEN
    capabilities:
      - id: wiki.read
        does: Read pages
        methods: [get]
        paths: [/pages/**]
""",
        encoding="utf-8",
    )
    monkeypatch.setenv("WARRANT_SITES", str(file))
    monkeypatch.setenv("WIKI_TOKEN", "secret")
    cap = capability_index(build_registry(settings))["wiki.read"]
    assert cap.rule.host == "wiki.example.com" and cap.rule.methods == ("GET",)
    assert site_tokens() == {"wiki.example.com": "secret"}

    seen = []

    def respond(request: httpx.Request) -> httpx.Response:
        seen.append((request.url.host, request.headers.get("authorization")))
        if request.url.host == "wiki.example.com":
            return httpx.Response(302, headers={"location": "https://elsewhere.example/x"})
        return httpx.Response(200)

    client = GatedClient(allow_all(), lambda _: None, transport=httpx.MockTransport(respond), tokens=site_tokens())
    client.request("GET", "https://wiki.example.com/pages/a")
    assert seen == [("wiki.example.com", "Bearer secret"), ("elsewhere.example", None)]


def test_with_your_own_sites_the_demo_portal_is_gone(settings, tmp_path, monkeypatch):
    from warrant.sites import add_site, build_registry, capability_index, remove_site

    monkeypatch.setenv("WARRANT_SITES", str(tmp_path / "sites.yaml"))
    assert any(s.id == "portal" for s in build_registry(settings))

    _, ids = add_site("wiki", "https://wiki.example.com", ["/pages/**"], ["/pages/new"], "WIKI_TOKEN")
    assert ids == ["wiki.read.1", "wiki.write.1"]
    registry = build_registry(settings)
    assert [s.id for s in registry] == ["wiki"]
    assert capability_index(registry)["wiki.write.1"].writes

    client = TestClient(create_app(replace(settings)))
    assert client.get("/api/missions").json() == []
    assert client.get("/api/status").json()["demo"] is False

    assert remove_site("wiki")
    assert any(s.id == "portal" for s in build_registry(settings))


@pytest.mark.parametrize(
    ("url", "read"),
    [("http://wiki.example.com", ["/a"]), ("https://wiki.example.com", ["/**"]), ("https://wiki.example.com", ["a"])],
)
def test_add_site_refuses_plain_http_and_whole_site_access(url, read, tmp_path, monkeypatch):
    from warrant.sites import add_site

    monkeypatch.setenv("WARRANT_SITES", str(tmp_path / "sites.yaml"))
    with pytest.raises(ValueError):
        add_site("wiki", url, read, [])
