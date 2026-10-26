"""The fictional Northfield course portal, served as plain HTML pages for the demo missions."""

from __future__ import annotations

from html import escape

from fastapi import FastAPI, Form, HTTPException
from fastapi.responses import HTMLResponse

from . import data

STYLE = (
    "body{font:15px/1.55 system-ui,sans-serif;margin:0;color:#1b1e24;background:#f6f7f9}"
    "header{background:#1f3a5f;color:#fff;padding:14px 28px;display:flex;gap:22px;align-items:center}"
    "header a{color:#dbe6f5;text-decoration:none}header b{margin-right:auto}"
    "main{max-width:860px;margin:24px auto;padding:0 20px}"
    "article{background:#fff;border:1px solid #e1e5ea;border-radius:6px;padding:14px 18px;margin:10px 0}"
    ".meta{color:#667;font-size:13px}table{width:100%;border-collapse:collapse;background:#fff}"
    "td,th{text-align:left;padding:8px 10px;border-bottom:1px solid #e1e5ea}"
)


def page(title: str, body: str) -> HTMLResponse:
    nav = "".join(
        f'<a href="{href}">{label}</a>'
        for href, label in [
            ("/courses", "Courses"),
            ("/announcements", "Announcements"),
            ("/assignments", "Assignments"),
            ("/grades", "Grades"),
            ("/forum", "Discussions"),
        ]
    )
    student = data.STUDENT
    html = (
        f"<!doctype html><html><head><meta charset='utf-8'><title>{escape(title)} · Northfield</title>"
        f"<style>{STYLE}</style></head><body><header><b>Northfield Institute of Technology</b>{nav}"
        f"<span>{escape(student['name'])}</span></header><main><h1>{escape(title)}</h1>{body}</main></body></html>"
    )
    return HTMLResponse(html)


def create_portal() -> FastAPI:
    app = FastAPI(title="Northfield course portal (fictional)", docs_url=None, redoc_url=None)
    app.state.submissions = []
    app.state.replies = []

    @app.get("/", response_class=HTMLResponse)
    def home() -> HTMLResponse:
        items = "".join(
            f"<li><a href='/courses/{c['code'].lower()}'>{c['code']} {escape(c['title'])}</a></li>"
            for c in data.COURSES
        )
        return page("Dashboard", f"<p>Welcome back. Your courses this term:</p><ul>{items}</ul>")

    @app.get("/courses", response_class=HTMLResponse)
    def courses() -> HTMLResponse:
        rows = "".join(
            f"<tr><td><a href='/courses/{c['code'].lower()}'>{c['code']}</a></td><td>{escape(c['title'])}</td>"
            f"<td>{escape(c['lecturer'])}</td><td>{escape(c['room'])}</td></tr>"
            for c in data.COURSES
        )
        return page(
            "Courses", f"<table><tr><th>Code</th><th>Title</th><th>Lecturer</th><th>Room</th></tr>{rows}</table>"
        )

    @app.get("/courses/{code}", response_class=HTMLResponse)
    def course(code: str) -> HTMLResponse:
        match = next((c for c in data.COURSES if c["code"].lower() == code.lower()), None)
        if not match:
            raise HTTPException(404)
        news = "".join(
            f"<li><a href='/announcements/{a['id']}'>{escape(a['title'])}</a> <span class='meta'>{a['date']}</span></li>"
            for a in data.ANNOUNCEMENTS
            if a["course"] == match["code"]
        )
        work = "".join(
            f"<li><a href='/assignments/{a['id']}'>{escape(a['title'])}</a> due {a['due']}</li>"
            for a in data.ASSIGNMENTS
            if a["course"] == match["code"]
        )
        return page(
            f"{match['code']} {match['title']}",
            f"<p class='meta'>{escape(match['lecturer'])} · {escape(match['room'])}</p>"
            f"<h2>Announcements</h2><ul>{news}</ul><h2>Assignments</h2><ul>{work}</ul>",
        )

    @app.get("/announcements", response_class=HTMLResponse)
    def announcements() -> HTMLResponse:
        body = "".join(
            f"<article><a href='/announcements/{a['id']}'><b>{escape(a['title'])}</b></a>"
            f"<div class='meta'>{a['course']} · {a['date']}</div><p>{escape(a['body'])}</p></article>"
            for a in data.ANNOUNCEMENTS
        )
        return page("Announcements", body)

    @app.get("/announcements/{aid}", response_class=HTMLResponse)
    def announcement(aid: str) -> HTMLResponse:
        a = next((x for x in data.ANNOUNCEMENTS if x["id"] == aid), None)
        if not a:
            raise HTTPException(404)
        return page(a["title"], f"<div class='meta'>{a['course']} · {a['date']}</div><p>{escape(a['body'])}</p>")

    @app.get("/assignments", response_class=HTMLResponse)
    def assignments() -> HTMLResponse:
        rows = "".join(
            f"<tr><td><a href='/assignments/{a['id']}'>{escape(a['title'])}</a></td><td>{a['course']}</td>"
            f"<td>{a['due']}</td><td>{escape(a['status'])}</td></tr>"
            for a in data.ASSIGNMENTS
        )
        return page(
            "Assignments",
            f"<table><tr><th>Assignment</th><th>Course</th><th>Due</th><th>Status</th></tr>{rows}</table>",
        )

    @app.get("/assignments/{aid}", response_class=HTMLResponse)
    def assignment(aid: str) -> HTMLResponse:
        a = next((x for x in data.ASSIGNMENTS if x["id"] == aid), None)
        if not a:
            raise HTTPException(404)
        form = (
            f"<form method='post' action='/assignments/{aid}/submit'><label>Note <input name='note'></label>"
            "<button>Submit</button></form>"
        )
        return page(a["title"], f"<p>{a['course']} · due {a['due']} · {escape(a['status'])}</p>{form}")

    @app.post("/assignments/{aid}/submit", response_class=HTMLResponse)
    def submit(aid: str, note: str = Form("")) -> HTMLResponse:
        if not any(x["id"] == aid for x in data.ASSIGNMENTS):
            raise HTTPException(404)
        app.state.submissions.append({"assignment": aid, "note": note[:200]})
        return page("Submitted", f"<p>Your submission for {escape(aid)} was received.</p>")

    @app.get("/grades", response_class=HTMLResponse)
    def grades() -> HTMLResponse:
        rows = "".join(
            f"<tr><td>{g['course']}</td><td>{escape(g['item'])}</td><td>{g['score']}</td></tr>" for g in data.GRADES
        )
        return page("Grades", f"<table><tr><th>Course</th><th>Item</th><th>Score</th></tr>{rows}</table>")

    @app.get("/forum", response_class=HTMLResponse)
    def forum() -> HTMLResponse:
        items = "".join(
            f"<li><a href='/forum/{t['id']}'>{escape(t['title'])}</a> <span class='meta'>{t['course']}</span></li>"
            for t in data.FORUM
        )
        return page("Discussions", f"<ul>{items}</ul>")

    @app.get("/forum/{tid}", response_class=HTMLResponse)
    def thread(tid: str) -> HTMLResponse:
        t = next((x for x in data.FORUM if x["id"] == tid), None)
        if not t:
            raise HTTPException(404)
        posts = "".join(
            f"<article><div class='meta'>{escape(p['author'])}</div><p>{escape(p['text'])}</p></article>"
            for p in t["posts"]
        )
        return page(t["title"], posts)

    @app.post("/forum/{tid}/reply", response_class=HTMLResponse)
    def reply(tid: str, text: str = Form("")) -> HTMLResponse:
        if not any(x["id"] == tid for x in data.FORUM):
            raise HTTPException(404)
        app.state.replies.append({"thread": tid, "text": text[:500]})
        return page("Reply posted", "<p>Your reply was posted.</p>")

    return app
