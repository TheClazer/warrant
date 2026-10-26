"""Turn an HTML page into the compact text view an agent reads: title, readable text and numbered links."""

from __future__ import annotations

from dataclasses import dataclass, field

from bs4 import BeautifulSoup

MAX_TEXT = 6000


@dataclass
class PageView:
    url: str
    status: int
    title: str
    text: str
    links: list[tuple[str, str]] = field(default_factory=list)

    def render(self) -> str:
        lines = [f"URL: {self.url}", f"Status: {self.status}", f"Title: {self.title}", "", self.text]
        if self.links:
            lines += ["", "Links:"] + [f"[{i}] {label} -> {href}" for i, (label, href) in enumerate(self.links, 1)]
        return "\n".join(lines)


def read_html(url: str, status: int, html: str, join) -> PageView:
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style", "noscript", "template"]):
        tag.decompose()
    title = soup.title.get_text(strip=True) if soup.title else ""
    links = []
    for a in soup.find_all("a", href=True):
        label = " ".join(a.get_text(" ", strip=True).split())[:80]
        href = str(a["href"])
        links.append((label or href, str(join(href))))
    body = soup.body or soup
    text = "\n".join(line.strip() for line in body.get_text("\n").splitlines() if line.strip())
    if len(text) > MAX_TEXT:
        text = text[:MAX_TEXT] + "\n[page truncated]"
    return PageView(url=url, status=status, title=title, text=text, links=links[:60])
