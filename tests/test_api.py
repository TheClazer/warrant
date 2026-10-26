from __future__ import annotations

import time
from dataclasses import replace

import httpx
from fastapi.testclient import TestClient

from warrant.api import create_app
from warrant.store import Store

from .conftest import Scripted, json_reply


def _client(settings, backend):
    return TestClient(create_app(settings, backend=backend, store=Store(settings.data_dir / "t.sqlite")))


def test_draft_check_approve_and_policy(settings):
    backend = Scripted(
        [
            json_reply(
                {
                    "capabilities": [
                        {"id": "portal.read.announcements", "reason": "news"},
                        {"id": "portal.read.assignments", "reason": "deadlines"},
                    ]
                }
            )
        ]
    )
    c = _client(settings, backend)
    missions = c.get("/api/missions").json()
    assert len(missions) == 3
    mid = missions[0]["id"]

    w = c.post(f"/api/missions/{mid}/warrant").json()
    assert w["status"] == "checked"
    assert [x["capability"] for x in w["can"]] == ["portal.read.announcements", "portal.read.assignments"]
    assert c.post(f"/api/missions/{mid}/runs", json={}).status_code == 409  # not approved yet

    approved = c.post(f"/api/warrants/{w['id']}/approve").json()
    assert approved["status"] == "approved" and approved["decided_by"] == "owner"
    policy = c.get(f"/api/warrants/{w['id']}/policy").text
    assert "enforcement: enforce" in policy and approved["fingerprint"] in policy


def test_owner_token_required_when_configured(settings):
    c = _client(replace(settings, admin_token="x" * 32), Scripted([]))
    mid = c.get("/api/missions").json()[0]["id"]
    assert c.post(f"/api/missions/{mid}/warrant").status_code == 401
    assert c.post("/api/missions", json={"title": "t", "text": "do a thing"}).status_code == 401
    ok = c.post(
        "/api/missions", json={"title": "t", "text": "do a thing"}, headers={"Authorization": "Bearer " + "x" * 32}
    )
    assert ok.status_code == 201


def test_writing_mission_needs_per_run_approval(settings):
    backend = Scripted([json_reply({"capabilities": [{"id": "portal.write.submit", "reason": "submit lab"}]})])
    c = _client(settings, backend)
    mid = c.get("/api/missions").json()[2]["id"]
    w = c.post(f"/api/missions/{mid}/warrant").json()
    assert w["per_run_approval"] is True
    c.post(f"/api/warrants/{w['id']}/approve")
    refused = c.post(f"/api/missions/{mid}/runs", json={"approve_this_run": False})
    assert refused.status_code == 409 and "approval for this run" in refused.json()["detail"]


def test_run_records_blocked_requests(settings, monkeypatch):
    """End to end with a scripted agent: one allowed page read, one request outside the warrant."""
    backend = Scripted(
        [
            json_reply({"capabilities": [{"id": "portal.read.announcements", "reason": "news"}]}),
            {
                "role": "assistant",
                "content": "",
                "tool_calls": [
                    {
                        "id": "1",
                        "type": "function",
                        "function": {
                            "name": "open_page",
                            "arguments": '{"url": "http://portal.test:8201/announcements"}',
                        },
                    }
                ],
            },
            {
                "role": "assistant",
                "content": "",
                "tool_calls": [
                    {
                        "id": "2",
                        "type": "function",
                        "function": {"name": "open_page", "arguments": '{"url": "http://unlisted.test/ping"}'},
                    }
                ],
            },
            {
                "role": "assistant",
                "content": "",
                "tool_calls": [
                    {
                        "id": "3",
                        "type": "function",
                        "function": {"name": "finish", "arguments": '{"answer": "- Midterm moved to Hall B"}'},
                    }
                ],
            },
        ]
    )

    real_client = httpx.Client

    def fake_client(*args, **kwargs):
        kwargs["transport"] = httpx.MockTransport(
            lambda req: httpx.Response(
                200, html="<html><title>Announcements</title><body>Midterm moved to Hall B</body></html>"
            )
        )
        return real_client(*args, **kwargs)

    monkeypatch.setattr("warrant.enforce.client.httpx.Client", fake_client)
    c = _client(settings, backend)
    mid = c.get("/api/missions").json()[0]["id"]
    w = c.post(f"/api/missions/{mid}/warrant").json()
    c.post(f"/api/warrants/{w['id']}/approve")
    rid = c.post(f"/api/missions/{mid}/runs", json={}).json()["run_id"]

    for _ in range(100):
        run = c.get(f"/api/runs/{rid}").json()
        if run["status"] != "running":
            break
        time.sleep(0.05)
    assert run["status"] == "completed"
    assert run["result"]["blocked"] == 1
    net = [e for e in run["events"] if e["kind"] == "network"]
    assert [e["decision"] for e in net] == ["allowed", "blocked"]
    assert net[1]["host"] == "unlisted.test"
    assert run["usage"]["model_calls"] == 3
