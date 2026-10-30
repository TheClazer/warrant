from __future__ import annotations

import threading
from dataclasses import replace
from http.server import BaseHTTPRequestHandler, HTTPServer

import httpx
import pytest

from warrant.guard import GuardProxy, HostList, Seen, proxied_env
from warrant.local import run_try

from .conftest import Scripted, json_reply


class Hello(BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        body = b"hello"
        self.send_response(200)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *_: object) -> None:
        pass


@pytest.fixture
def origin():
    server = HTTPServer(("127.0.0.1", 0), Hello)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    yield server.server_address[1]
    server.shutdown()
    server.server_close()


def test_host_list_matches_exact_hosts_and_subdomains_only():
    rules = HostList(["example.com", "*.example.org"])
    assert rules.allows("EXAMPLE.com")
    assert rules.allows("a.example.org")
    assert not rules.allows("example.org")
    assert not rules.allows("evil-example.com")
    assert not rules.allows("example.com.evil.net")


def test_allowed_host_is_forwarded(origin):
    seen: list[Seen] = []
    with GuardProxy(["127.0.0.1"], seen.append) as proxy, httpx.Client(proxy=proxy.url) as client:
        reply = client.get(f"http://127.0.0.1:{origin}/page")
    assert reply.status_code == 200 and reply.text == "hello"
    assert seen == [Seen(True, "GET", "127.0.0.1/page")]


def test_other_host_is_refused_without_contacting_it():
    seen: list[Seen] = []
    with GuardProxy(["example.com"], seen.append) as proxy, httpx.Client(proxy=proxy.url) as client:
        reply = client.get("http://not-allowed.invalid/secret")
    assert reply.status_code == 403
    assert seen == [Seen(False, "GET", "not-allowed.invalid/secret")]


def test_https_to_other_host_is_refused():
    seen: list[Seen] = []
    with (
        GuardProxy(["example.com"], seen.append) as proxy,
        httpx.Client(proxy=proxy.url) as client,
        pytest.raises(httpx.ProxyError),
    ):
        client.get("https://not-allowed.invalid/")
    assert seen == [Seen(False, "CONNECT", "not-allowed.invalid:443")]


def test_proxied_env_sets_both_cases_and_clears_bypass():
    env = proxied_env("http://127.0.0.1:1", {"NO_PROXY": "*", "PATH": "x"})
    assert env["HTTPS_PROXY"] == env["https_proxy"] == "http://127.0.0.1:1"
    assert "NO_PROXY" not in env and env["PATH"] == "x"


def test_try_shows_the_block_and_what_changed(settings, tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("WARRANT_DATA_DIR", str(tmp_path))
    backend = Scripted(
        [
            json_reply(
                {
                    "capabilities": [
                        {"id": "portal.read.announcements", "reason": "needed"},
                        {"id": "portal.read.grades", "reason": "needed"},
                    ],
                    "unmet": "",
                }
            ),
            {
                "role": "assistant",
                "content": None,
                "tool_calls": [
                    {
                        "id": "1",
                        "type": "function",
                        "function": {"name": "open_page", "arguments": '{"url": "PORTAL/grades"}'},
                    }
                ],
            },
            {"role": "assistant", "content": "Could not read grades."},
        ]
    )

    class Backend(Scripted):
        def chat(self, model, messages, **kwargs):
            result = super().chat(model, messages, **kwargs)
            for call in result.message.get("tool_calls") or []:
                start = next(m["content"] for m in messages if m["role"] == "user")
                origin = next(w for w in start.split() if w.startswith("http://127.0.0.1")).split("/announcements")[0]
                call["function"]["arguments"] = call["function"]["arguments"].replace("PORTAL", origin)
            return result

    code = run_try(
        replace(settings, nebius_api_key="test"),
        remove=["portal.read.grades"],
        yes=True,
        backend=Backend(backend.replies),
    )
    out = capsys.readouterr().out
    assert code == 0
    assert "BLOCKED" in out and "GET /grades" in out
    assert "would have gone through" in out and "Could not read grades." in out
