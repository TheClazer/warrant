"""The site registry: every capability an agent can ever be granted.

The compiler may only pick capability IDs from this catalogue, so the model can never invent a host, a
wildcard or a broader path. Adding a site means reviewing its capabilities here, once, in code review.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

import yaml

from .config import Settings
from .models import Capability, Rule, Site


def _origin(url: str) -> tuple[str, str, int]:
    parts = urlsplit(url)
    if parts.scheme not in {"http", "https"} or not parts.hostname:
        raise ValueError(f"site URL must be http(s) with a host: {url!r}")
    port = parts.port or (443 if parts.scheme == "https" else 80)
    return parts.scheme, parts.hostname, port


def _cap(site: str, url: str, cid: str, summary: str, plain: str, methods: tuple, paths: tuple) -> Capability:
    scheme, host, port = _origin(url)
    return Capability(
        id=cid,
        site=site,
        summary=summary,
        plain=plain,
        rule=Rule(id=cid, host=host, port=port, scheme=scheme, methods=methods, paths=paths),  # type: ignore[arg-type]
    )


def sites_file() -> Path:
    """Your own reviewed sites: WARRANT_SITES if set, else ~/.warrant/sites.yaml."""
    configured = os.environ.get("WARRANT_SITES")
    return Path(configured) if configured else Path.home() / ".warrant" / "sites.yaml"


def _user_entries() -> list[dict]:
    path = sites_file()
    if not path.is_file():
        return []
    return list((yaml.safe_load(path.read_text(encoding="utf-8")) or {}).get("sites") or [])


def _user_sites() -> list[Site]:
    """Sites you listed yourself. You are the reviewer: the model can still only pick from what is written here."""
    sites = []
    for entry in _user_entries():
        sid, name, url = str(entry["id"]), str(entry["name"]), str(entry["url"]).rstrip("/")
        caps = tuple(
            _cap(
                sid,
                url,
                str(c["id"]),
                str(c["does"]),
                f"{c['does']} on {name}",
                tuple(str(m).upper() for m in c["methods"]),
                tuple(str(p) for p in c["paths"]),
            )
            for c in entry["capabilities"]
        )
        sites.append(Site(id=sid, name=name, base_url=url, capabilities=caps))
    return sites


def site_tokens() -> dict[str, str]:
    """host -> token, for sites that name an environment variable in ``token_env``. Tokens are never stored."""
    tokens = {}
    for entry in _user_entries():
        token = os.environ.get(str(entry.get("token_env") or ""), "").strip()
        if token:
            tokens[(urlsplit(str(entry["url"])).hostname or "").lower()] = token
    return tokens


def _demo_sites(settings: Settings) -> list[Site]:
    portal = settings.portal_url.rstrip("/")
    portal_name = "the course portal"
    p = "portal"
    return [
        Site(
            id=p,
            name="Northfield course portal",
            base_url=portal,
            capabilities=(
                _cap(
                    p,
                    portal,
                    "portal.read.courses",
                    "List courses and read course pages",
                    f"Read your courses on {portal_name}",
                    ("GET",),
                    ("/", "/courses", "/courses/**"),
                ),
                _cap(
                    p,
                    portal,
                    "portal.read.announcements",
                    "Read course announcements",
                    f"Read announcements on {portal_name}",
                    ("GET",),
                    ("/announcements", "/announcements/**"),
                ),
                _cap(
                    p,
                    portal,
                    "portal.read.assignments",
                    "Read assignments and their deadlines",
                    f"Read assignments and deadlines on {portal_name}",
                    ("GET",),
                    ("/assignments", "/assignments/*"),
                ),
                _cap(
                    p,
                    portal,
                    "portal.read.grades",
                    "Read your grades",
                    f"Read your grades on {portal_name}",
                    ("GET",),
                    ("/grades",),
                ),
                _cap(
                    p,
                    portal,
                    "portal.read.forum",
                    "Read course discussion threads",
                    f"Read course discussions on {portal_name}",
                    ("GET",),
                    ("/forum", "/forum/**"),
                ),
                _cap(
                    p,
                    portal,
                    "portal.write.submit",
                    "Submit an assignment",
                    f"Submit an assignment on {portal_name} (asks you every run)",
                    ("POST",),
                    ("/assignments/*/submit",),
                ),
                _cap(
                    p,
                    portal,
                    "portal.write.forum",
                    "Post a reply in a discussion",
                    f"Post a reply in a course discussion on {portal_name} (asks you every run)",
                    ("POST",),
                    ("/forum/*/reply",),
                ),
            ),
        )
    ]


def build_registry(settings: Settings) -> tuple[Site, ...]:
    own = _user_sites()
    use_demo = not own if settings.include_demo is None else settings.include_demo
    sites: list[Site] = _demo_sites(settings) if use_demo else []
    if settings.tavily_api_key:
        sites.append(
            Site(
                id="tavily",
                name="Tavily web search",
                base_url="https://api.tavily.com",
                capabilities=(
                    _cap(
                        "tavily",
                        "https://api.tavily.com",
                        "tavily.search",
                        "Search the web through Tavily",
                        "Search the web through Tavily",
                        ("POST",),
                        ("/search",),
                    ),
                ),
            )
        )
    sites.extend(own)
    return tuple(sites)


def capability_index(sites: tuple[Site, ...]) -> dict[str, Capability]:
    return {c.id: c for s in sites for c in s.capabilities}


def add_site(
    name: str, url: str, read: list[str], write: list[str], token_env: str | None = None
) -> tuple[Path, list[str]]:
    """Add a site to your sites file, replacing one with the same name. Returns the file and the capability IDs."""
    scheme, host, _ = _origin(url)
    if scheme != "https" and host not in {"127.0.0.1", "localhost"}:
        raise ValueError("Use an https:// address. Plain http is only accepted for localhost.")
    if not read and not write:
        raise ValueError("List at least one path with --read or --write.")
    for route in (*read, *write):
        if not route.startswith("/") or route in {"/*", "/**"}:
            raise ValueError(f"Paths must start with / and cannot cover the whole site: {route}")
    caps: list[dict[str, Any]] = [
        {"id": f"{name}.read.{i}", "does": f"Read {route}", "methods": ["GET"], "paths": [route]}
        for i, route in enumerate(read, 1)
    ] + [
        {"id": f"{name}.write.{i}", "does": f"Send to {route}", "methods": ["POST"], "paths": [route]}
        for i, route in enumerate(write, 1)
    ]
    entry: dict = {"id": name, "name": name, "url": url.rstrip("/"), "capabilities": caps}
    if token_env:
        entry["token_env"] = token_env
    entries = [e for e in _user_entries() if e.get("id") != name] + [entry]
    path = sites_file()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump({"sites": entries}, sort_keys=False), encoding="utf-8")
    return path, [c["id"] for c in caps]


def remove_site(name: str) -> bool:
    entries = _user_entries()
    kept = [e for e in entries if e.get("id") != name]
    if len(kept) == len(entries):
        return False
    sites_file().write_text(yaml.safe_dump({"sites": kept}, sort_keys=False), encoding="utf-8")
    return True
