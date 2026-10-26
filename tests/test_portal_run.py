"""The whole loop against the demo portal: warrant, gate, agent tools and page reading."""

from __future__ import annotations

import httpx
from fastapi.testclient import TestClient

from warrant.compiler import compile_warrant
from warrant.demo.portal import create_portal
from warrant.runner import execute
from warrant.store import Store

from .conftest import Scripted, json_reply


def _tool(name: str, args: str, cid: str) -> dict:
    return {
        "role": "assistant",
        "content": "",
        "tool_calls": [{"id": cid, "type": "function", "function": {"name": name, "arguments": args}}],
    }


def test_portal_pages_render():
    client = TestClient(create_portal())
    assert "Hall B" in client.get("/announcements").text
    assert "Lab 4" in client.get("/assignments").text
    assert client.get("/assignments/nope").status_code == 404


def test_run_against_portal_reads_pages_and_blocks_writes(tmp_path, mission, catalogue, monkeypatch):
    portal = create_portal()
    portal_client = TestClient(portal, base_url="http://portal.test:8201")
    real = httpx.Client

    def routed(*args, **kwargs):
        kwargs["transport"] = portal_client._transport
        return real(*args, **kwargs)

    monkeypatch.setattr("warrant.enforce.client.httpx.Client", routed)

    store = Store(tmp_path / "w.sqlite")
    store.save_mission(mission)
    warrant = compile_warrant(
        mission, catalogue, Scripted([json_reply({"capabilities": [{"id": "portal.read.announcements"}]})]), "m"
    )
    warrant.status = "approved"
    store.save_warrant(warrant)

    agent = Scripted(
        [
            _tool("open_page", '{"url": "http://portal.test:8201/announcements"}', "1"),
            _tool("submit_form", '{"url": "http://portal.test:8201/forum/t1/reply", "fields": {"text": "hi"}}', "2"),
            _tool("finish", '{"answer": "- CS301 midterm moved to Hall B"}', "3"),
        ]
    )
    run = execute(store, mission, warrant, "http://portal.test:8201", agent, "m")

    assert run["status"] == "completed"
    assert run["result"]["blocked"] == 1
    assert portal.state.replies == []  # the write never reached the portal
    page_events = [e for e in store.events(run["id"]) if e["kind"] == "page"]
    assert "Hall B" in page_events[0]["excerpt"]
    # The agent saw the page text and the block notice in its tool results.
    tool_msgs = [m for m in agent.requests[-1]["messages"] if m["role"] == "tool"]
    assert "Hall B" in tool_msgs[0]["content"]
    assert tool_msgs[1]["content"].startswith("BLOCKED")
