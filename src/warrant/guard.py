"""``warrant guard``: run a local program with its web traffic limited to what you allow.

The program is pointed at a small proxy through the standard proxy environment variables. This is
cooperative: a program can ignore those variables, and HTTPS can only be limited by host, because the proxy
does not read inside the encrypted connection. For enforcement a program cannot opt out of, use NVIDIA OpenShell.
"""

from __future__ import annotations

import os
import select
import socket
import subprocess
import threading
from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from http.client import HTTPConnection
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlsplit

HOP_BY_HOP = {
    "connection",
    "keep-alive",
    "proxy-authenticate",
    "proxy-authorization",
    "proxy-connection",
    "te",
    "trailer",
    "transfer-encoding",
    "upgrade",
}


@dataclass(frozen=True)
class Seen:
    allowed: bool
    method: str
    target: str


@dataclass
class HostList:
    """Exact hosts, or ``*.example.com`` for its subdomains."""

    hosts: Iterable[str]
    _exact: set[str] = field(init=False)
    _suffixes: tuple[str, ...] = field(init=False)

    def __post_init__(self) -> None:
        names = [h.strip().lower() for h in self.hosts if h.strip()]
        self._exact = {h for h in names if not h.startswith("*.")}
        self._suffixes = tuple(h[1:] for h in names if h.startswith("*."))

    def allows(self, host: str) -> bool:
        host = host.lower()
        return host in self._exact or (bool(self._suffixes) and host.endswith(self._suffixes))


def _handler(rules: HostList, on_seen: Callable[[Seen], None]) -> type[BaseHTTPRequestHandler]:
    class Handler(BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1"

        def log_message(self, format: str, *args: object) -> None:  # decisions are reported through on_seen
            pass

        def _refuse(self, target: str) -> None:
            on_seen(Seen(False, self.command, target))
            body = f"Blocked by warrant guard: {self.command} {target} is not allowed.\n".encode()
            self.send_response(403)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Connection", "close")
            self.end_headers()
            self.wfile.write(body)
            self.close_connection = True

        def do_CONNECT(self) -> None:
            host, _, port = self.path.rpartition(":")
            if not host or not port.isdigit() or not rules.allows(host):
                self._refuse(self.path)
                return
            try:
                upstream = socket.create_connection((host, int(port)), timeout=15)
            except OSError:
                self.send_error(502, "Could not reach the host")
                return
            on_seen(Seen(True, "CONNECT", self.path))
            self.send_response(200, "Connection established")
            self.end_headers()
            self.close_connection = True
            with upstream:
                while True:
                    ready, _, _ = select.select([self.connection, upstream], [], [], 60)
                    if not ready:
                        return
                    for source in ready:
                        data = source.recv(65536)
                        if not data:
                            return
                        (upstream if source is self.connection else self.connection).sendall(data)

        def _forward(self) -> None:
            parts = urlsplit(self.path)
            target = f"{parts.hostname}{parts.path or '/'}"
            if parts.scheme != "http" or not parts.hostname or not rules.allows(parts.hostname):
                self._refuse(target)
                return
            on_seen(Seen(True, self.command, target))
            length = int(self.headers.get("Content-Length") or 0)
            body = self.rfile.read(length) if length else None
            headers = {k: v for k, v in self.headers.items() if k.lower() not in HOP_BY_HOP}
            path = parts.path or "/"
            if parts.query:
                path += f"?{parts.query}"
            upstream = HTTPConnection(parts.hostname, parts.port or 80, timeout=30)
            try:
                upstream.request(self.command, path, body=body, headers=headers)
                reply = upstream.getresponse()
                data = reply.read()
            except OSError:
                self.send_error(502, "Could not reach the host")
                return
            finally:
                upstream.close()
            self.send_response(reply.status, reply.reason)
            for key, value in reply.getheaders():
                if key.lower() not in HOP_BY_HOP and key.lower() != "content-length":
                    self.send_header(key, value)
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            if self.command != "HEAD":
                self.wfile.write(data)

        do_GET = do_POST = do_PUT = do_PATCH = do_DELETE = do_HEAD = do_OPTIONS = _forward

    return Handler


class GuardProxy:
    def __init__(self, hosts: Iterable[str], on_seen: Callable[[Seen], None]):
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), _handler(HostList(hosts), on_seen))
        self.server.daemon_threads = True
        self.url = f"http://127.0.0.1:{self.server.server_address[1]}"

    def __enter__(self) -> GuardProxy:
        threading.Thread(target=self.server.serve_forever, daemon=True).start()
        return self

    def __exit__(self, *_: object) -> None:
        self.server.shutdown()
        self.server.server_close()


def proxied_env(proxy_url: str, base: dict[str, str] | None = None) -> dict[str, str]:
    env = dict(os.environ if base is None else base)
    for name in ("HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY"):
        env[name] = proxy_url
        env[name.lower()] = proxy_url
    env.pop("NO_PROXY", None)
    env.pop("no_proxy", None)
    return env


def run_guarded(command: list[str], hosts: list[str], on_seen: Callable[[Seen], None]) -> int:
    with GuardProxy(hosts, on_seen) as proxy:
        return subprocess.call(command, env=proxied_env(proxy.url))
