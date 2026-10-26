"""The site registry: every capability an agent can ever be granted.

The compiler may only pick capability IDs from this catalogue, so the model can never invent a host, a
wildcard or a broader path. Adding a site means reviewing its capabilities here, once, in code review.
"""

from __future__ import annotations

from urllib.parse import urlsplit

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


def build_registry(settings: Settings) -> tuple[Site, ...]:
    portal = settings.portal_url.rstrip("/")
    _, portal_host, _ = _origin(portal)
    p = "portal"
    sites = [
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
                    f"Read your courses on {portal_host}",
                    ("GET",),
                    ("/", "/courses", "/courses/**"),
                ),
                _cap(
                    p,
                    portal,
                    "portal.read.announcements",
                    "Read course announcements",
                    f"Read announcements on {portal_host}",
                    ("GET",),
                    ("/announcements", "/announcements/**"),
                ),
                _cap(
                    p,
                    portal,
                    "portal.read.assignments",
                    "Read assignments and their deadlines",
                    f"Read assignments and deadlines on {portal_host}",
                    ("GET",),
                    ("/assignments", "/assignments/*"),
                ),
                _cap(
                    p,
                    portal,
                    "portal.read.grades",
                    "Read your grades",
                    f"Read your grades on {portal_host}",
                    ("GET",),
                    ("/grades",),
                ),
                _cap(
                    p,
                    portal,
                    "portal.read.forum",
                    "Read course discussion threads",
                    f"Read course discussions on {portal_host}",
                    ("GET",),
                    ("/forum", "/forum/**"),
                ),
                _cap(
                    p,
                    portal,
                    "portal.write.submit",
                    "Submit an assignment",
                    f"Submit an assignment on {portal_host} (asks you every run)",
                    ("POST",),
                    ("/assignments/*/submit",),
                ),
                _cap(
                    p,
                    portal,
                    "portal.write.forum",
                    "Post a reply in a discussion",
                    f"Post a reply in a course discussion on {portal_host} (asks you every run)",
                    ("POST",),
                    ("/forum/*/reply",),
                ),
            ),
        )
    ]
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
    return tuple(sites)


def capability_index(sites: tuple[Site, ...]) -> dict[str, Capability]:
    return {c.id: c for s in sites for c in s.capabilities}
