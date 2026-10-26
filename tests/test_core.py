from __future__ import annotations

import httpx
import pytest
import yaml
from pydantic import ValidationError

from warrant.checker import check
from warrant.compiler import CompileError, compile_warrant
from warrant.enforce.client import Blocked, GatedClient
from warrant.enforce.gate import Gate, allow_all
from warrant.llm import BudgetExceeded, Ledger, Metered, parse_json_object
from warrant.models import Grant, Mission, Rule, Warrant, path_matches
from warrant.policy import render_policy
from warrant.store import Store

from .conftest import Scripted, json_reply


def test_path_globs_follow_openshell_semantics():
    assert path_matches("/courses/**", "/courses/cs301/week/2")
    assert path_matches("/assignments/*", "/assignments/cs301-lab4")
    assert not path_matches("/assignments/*", "/assignments/cs301-lab4/submit")
    assert path_matches("/assignments/*/submit", "/assignments/cs301-lab4/submit")
    assert not path_matches("/grades", "/grades/export")


def test_rule_rejects_wildcard_hosts_and_traversal():
    with pytest.raises(ValidationError):
        Rule(id="x", host="*.example.com", port=443, methods=("GET",), paths=("/",))
    with pytest.raises(ValidationError):
        Rule(id="x", host="example.com", port=443, methods=("GET",), paths=("/a/../b",))


def _warrant(mission, catalogue, ids, per_run=False):
    return Warrant(
        mission_id=mission.id,
        mission_sha256=mission.text_sha256,
        grants=tuple(Grant(capability=catalogue[i]) for i in ids),
        per_run_approval=per_run,
    )


def test_compiler_picks_only_catalogue_capabilities(mission, catalogue):
    backend = Scripted(
        [
            json_reply(
                {
                    "capabilities": [
                        {"id": "portal.read.announcements", "reason": "announcements"},
                        {"id": "portal.read.assignments", "reason": "deadlines"},
                        {"id": "evil.everything", "reason": "convenient"},
                    ],
                    "unmet": "",
                }
            )
        ]
    )
    w = compile_warrant(mission, catalogue, backend, "nemotron")
    assert [g.capability.id for g in w.grants] == ["portal.read.announcements", "portal.read.assignments"]
    assert any("evil.everything" in n for n in w.notes)
    assert not w.writes and not w.per_run_approval
    assert "Post, submit or change anything" in w.cannot
    assert check(w, mission, catalogue).ok


def test_compiler_retries_once_then_fails_cleanly(mission, catalogue):
    good = Scripted(
        [
            {"role": "assistant", "content": "sure!"},
            json_reply({"capabilities": [{"id": "portal.read.grades", "reason": "r"}]}),
        ]
    )
    assert compile_warrant(mission, catalogue, good, "m").grants[0].capability.id == "portal.read.grades"
    bad = Scripted([{"role": "assistant", "content": "no"}, {"role": "assistant", "content": "still no"}])
    with pytest.raises(CompileError):
        compile_warrant(mission, catalogue, bad, "m")


def test_write_capability_forces_per_run_approval(mission, catalogue):
    backend = Scripted([json_reply({"capabilities": [{"id": "portal.write.submit", "reason": "submit"}]})])
    w = compile_warrant(mission, catalogue, backend, "m")
    assert w.writes and w.per_run_approval
    assert check(w, mission, catalogue).ok
    assert not check(_warrant(mission, catalogue, ["portal.write.submit"]), mission, catalogue).ok


def test_checker_findings(mission, catalogue):
    empty = _warrant(mission, catalogue, [])
    assert "at least one capability" in " ".join(check(empty, mission, catalogue).findings)

    edited = Mission(id=mission.id, title=mission.title, text=mission.text + " Also post my grades.")
    w = _warrant(mission, catalogue, ["portal.read.grades"])
    assert any("changed" in f for f in check(w, edited, catalogue).findings)

    forged_cap = catalogue["portal.read.grades"].model_copy(
        update={
            "rule": Rule(
                id="portal.read.grades",
                host="portal.test",
                port=8201,
                scheme="http",
                methods=("GET", "POST"),
                paths=("/grades",),
            )
        }
    )
    forged = Warrant(
        mission_id=mission.id,
        mission_sha256=mission.text_sha256,
        grants=(Grant(capability=forged_cap),),
        per_run_approval=True,
    )
    assert any("differs" in f for f in check(forged, mission, catalogue).findings)

    dup = _warrant(mission, catalogue, ["portal.read.grades", "portal.read.grades"])
    assert any("twice" in f for f in check(dup, mission, catalogue).findings)


def test_fingerprint_is_stable_and_rule_sensitive(mission, catalogue):
    a = _warrant(mission, catalogue, ["portal.read.grades"])
    b = _warrant(mission, catalogue, ["portal.read.grades"])
    c = _warrant(mission, catalogue, ["portal.read.forum"])
    assert a.id != b.id and a.fingerprint == b.fingerprint != c.fingerprint


def test_policy_renders_enforced_openshell_rules(mission, catalogue):
    w = _warrant(mission, catalogue, ["portal.read.announcements", "portal.write.forum"], per_run=True)
    doc = yaml.safe_load(render_policy(w, inference_url="https://api.tokenfactory.nebius.com/v1"))
    assert doc["version"] == 1
    net = doc["network_policies"]
    ann = net["portal_read_announcements"]["endpoints"][0]
    assert ann["host"] == "portal.test" and ann["port"] == 8201
    assert ann["enforcement"] == "enforce" and ann["protocol"] == "rest"
    assert {"allow": {"method": "GET", "path": "/announcements/**"}} in ann["rules"]
    inference = net["nemotron_inference"]["endpoints"][0]
    assert inference["host"] == "api.tokenfactory.nebius.com"
    assert inference["rules"] == [{"allow": {"method": "POST", "path": "/v1/chat/completions"}}]
    assert all("access" not in e for p in net.values() for e in p["endpoints"])


def test_gated_client_blocks_and_reports(mission, catalogue):
    w = _warrant(mission, catalogue, ["portal.read.announcements"])
    seen = []
    transport = httpx.MockTransport(lambda req: httpx.Response(200, text="<html>ok</html>"))
    client = GatedClient(Gate.for_warrant(w), seen.append, transport=transport)
    assert client.request("GET", "http://portal.test:8201/announcements/a1").status_code == 200
    with pytest.raises(Blocked):
        client.request("GET", "http://other.test/anything")
    with pytest.raises(Blocked):
        client.request("POST", "http://portal.test:8201/announcements/a1")
    assert [d.allowed for d in seen] == [True, False, False]
    assert seen[0].rule_id == "portal.read.announcements"


def test_redirects_are_checked_hop_by_hop(mission, catalogue):
    w = _warrant(mission, catalogue, ["portal.read.announcements"])

    def handler(req: httpx.Request) -> httpx.Response:
        if req.url.host == "portal.test":
            return httpx.Response(302, headers={"location": "http://elsewhere.test/x"})
        return httpx.Response(200, text="should not be reached")

    seen = []
    client = GatedClient(Gate.for_warrant(w), seen.append, transport=httpx.MockTransport(handler))
    with pytest.raises(Blocked):
        client.request("GET", "http://portal.test:8201/announcements")
    assert [d.host for d in seen] == ["portal.test", "elsewhere.test"]


def test_allow_all_gate_is_explicit():
    d = allow_all().check("POST", "https://anywhere.test/x")
    assert d.allowed and "broad access" in d.reason


def test_ledger_caps_calls():
    backend = Scripted([{"role": "assistant", "content": "a"}, {"role": "assistant", "content": "b"}])
    metered = Metered(backend, Ledger(max_calls=1))
    metered.chat("m", [])
    with pytest.raises(BudgetExceeded):
        metered.chat("m", [])


def test_parse_json_object_handles_fences():
    assert parse_json_object('```json\n{"a": 1}\n```') == {"a": 1}
    with pytest.raises(ValueError):
        parse_json_object("[1, 2]")


def test_store_round_trip(tmp_path, mission, catalogue):
    store = Store(tmp_path / "w.sqlite")
    store.save_mission(mission)
    w = store.save_warrant(_warrant(mission, catalogue, ["portal.read.grades"]))
    assert store.mission(mission.id).text == mission.text
    assert store.latest_warrant(mission.id).fingerprint == w.fingerprint
    rid = store.start_run(mission.id, w.id, "warrant")
    store.add_event(rid, "step", {"text": "Open portal"})
    store.finish_run(rid, "completed", {"answer": "ok"}, {"model_calls": 1, "cost_usd": 0.001})
    assert store.run(rid)["status"] == "completed"
    assert store.events(rid)[0]["text"] == "Open portal"
    assert store.spend_since(0) == pytest.approx(0.001)
