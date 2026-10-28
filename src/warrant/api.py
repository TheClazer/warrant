"""HTTP API for the Warrant app. Reads are public; anything that drafts, approves or runs needs the owner
token (or, later, a capped guest session)."""

from __future__ import annotations

import asyncio
import json
import os
import secrets
import threading
from datetime import datetime
from pathlib import Path
from typing import Annotated, Any

from fastapi import Depends, FastAPI, Header, HTTPException
from fastapi.responses import FileResponse, PlainTextResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from .checker import check
from .compiler import CompileError, compile_warrant, default_cannot
from .config import Settings, get_settings
from .llm import ChatBackend, ModelUnavailable, TokenFactory
from .models import Mission, Warrant, now
from .policy import render_policy
from .runner import RunRefused, ensure_runnable, execute
from .scheduler import Scheduler, is_due
from .sites import build_registry, capability_index
from .store import Store

SEED = [
    (
        "Morning course brief",
        "Every morning, check my course portal for new announcements and upcoming deadlines, and brief me in five bullets.",
        "daily 07:30",
    ),
    ("Exam week check", "Find every exam or midterm in my courses this week, with venue and time.", None),
    ("Submit Lab 4", "Submit my CS301 Lab 4 on the course portal with the note 'final version'.", None),
    (
        "Announcements and grades",
        "Brief me on this week's announcements and tell me my latest grades.",
        None,
    ),
]


class NewMission(BaseModel):
    title: Annotated[str, Field(min_length=1, max_length=80)]
    text: Annotated[str, Field(min_length=3, max_length=2000)]
    schedule: str | None = None


class Narrow(BaseModel):
    remove: Annotated[list[str], Field(min_length=1, max_length=20)]


class RunRequest(BaseModel):
    approve_this_run: bool = False


def project_path(*parts: str) -> Path:
    """A path in the project: WARRANT_ROOT if set, else the working directory, else the source checkout."""
    root = os.environ.get("WARRANT_ROOT")
    candidates = [Path(root)] if root else [Path.cwd(), Path(__file__).resolve().parents[2]]
    for base in candidates:
        if (base.joinpath(*parts)).exists():
            return base.joinpath(*parts)
    return candidates[-1].joinpath(*parts)


def create_app(
    settings: Settings | None = None,
    backend: ChatBackend | None = None,
    store: Store | None = None,
    start_scheduler: bool = False,
) -> FastAPI:
    cfg = settings or get_settings()
    db = store or Store(cfg.data_dir / "warrant.sqlite")
    sites = build_registry(cfg)
    catalogue = capability_index(sites)
    app = FastAPI(title="Warrant", version="0.1.0")

    @app.middleware("http")
    async def no_store(request, call_next):  # live state must never come from a cache
        response = await call_next(request)
        if request.url.path.startswith("/api/"):
            response.headers["Cache-Control"] = "no-store"
        return response
    state: dict[str, Any] = {"backend": backend}

    if not db.missions():
        for title, text, schedule in SEED:
            db.save_mission(Mission(title=title, text=text, schedule=schedule))

    def model_backend() -> ChatBackend:
        if state["backend"] is None:
            try:
                state["backend"] = TokenFactory(cfg)
            except ModelUnavailable as exc:
                raise HTTPException(503, f"Model unavailable: {exc}") from None
        return state["backend"]

    def owner(authorization: Annotated[str | None, Header()] = None) -> str:
        if not cfg.admin_token:
            return "owner"  # local development: no token configured
        if not secrets.compare_digest(authorization or "", f"Bearer {cfg.admin_token}"):
            raise HTTPException(401, "Owner token required")
        return "owner"

    def get_mission(mid: str) -> Mission:
        try:
            return db.mission(mid)
        except KeyError:
            raise HTTPException(404, "Mission not found") from None

    @app.get("/api/status")
    def status() -> dict:
        day_start = now() - 86400
        return {
            **cfg.public(),
            "auth_required": bool(cfg.admin_token),
            "spend_24h_usd": round(db.spend_since(day_start), 6),
        }

    @app.get("/api/catalogue")
    def get_catalogue() -> list[dict]:
        return [
            {
                "id": s.id,
                "name": s.name,
                "base_url": s.base_url,
                "capabilities": [
                    {
                        "id": c.id,
                        "summary": c.summary,
                        "plain": c.plain,
                        "writes": c.writes,
                        "rule": c.rule.model_dump(mode="json"),
                    }
                    for c in s.capabilities
                ],
            }
            for s in sites
        ]

    @app.get("/api/missions")
    def list_missions() -> list[dict]:
        out = []
        for m in db.missions():
            w = db.latest_warrant(m.id)
            last = db.runs(1, m.id)
            out.append({**m.model_dump(), "warrant": w.view() if w else None, "last_run": last[0] if last else None})
        return out

    @app.post("/api/missions", status_code=201)
    def create_mission(body: NewMission, _: str = Depends(owner)) -> dict:
        return db.save_mission(Mission(**body.model_dump())).model_dump()

    @app.get("/api/missions/{mid}")
    def mission_detail(mid: str) -> dict:
        m = get_mission(mid)
        w = db.latest_warrant(m.id)
        return {**m.model_dump(), "warrant": w.view() if w else None, "runs": db.runs(20, m.id)}

    @app.post("/api/missions/{mid}/warrant", status_code=201)
    def draft_warrant(mid: str, _: str = Depends(owner)) -> dict:
        m = get_mission(mid)
        if db.count_since("warrants", now() - 86400) >= cfg.daily_draft_cap:
            raise HTTPException(
                429, "Daily drafting limit reached for this demo. Please watch the recorded demo video."
            )
        try:
            w = compile_warrant(m, catalogue, model_backend(), cfg.planner_model)
        except CompileError as exc:
            raise HTTPException(502, str(exc)) from None
        verdict = check(w, m, catalogue)
        w.status = "checked" if verdict.ok else "rejected_by_checker"
        w.checker_findings = verdict.findings
        return db.save_warrant(w).view()

    def decide(wid: str, approve: bool) -> dict:
        try:
            w = db.warrant(wid)
        except KeyError:
            raise HTTPException(404, "Warrant not found") from None
        m = get_mission(w.mission_id)
        verdict = check(w, m, catalogue)
        if approve and (w.status != "checked" or not verdict.ok):
            raise HTTPException(409, "Only a warrant that passed the checker can be approved.")
        w.status = "approved" if approve else "rejected"
        w.decided_at, w.decided_by = now(), "owner"
        return db.save_warrant(w).view()

    @app.post("/api/warrants/{wid}/narrow", status_code=201)
    def narrow(wid: str, body: Narrow, _: str = Depends(owner)) -> dict:
        """Remove capabilities from a draft before approval. Narrowing only: nothing can be added here."""
        try:
            old = db.warrant(wid)
        except KeyError:
            raise HTTPException(404, "Warrant not found") from None
        if old.status not in {"checked", "rejected_by_checker"}:
            raise HTTPException(409, "Only a warrant awaiting a decision can be narrowed.")
        keep = tuple(g for g in old.grants if g.capability.id not in set(body.remove))
        writes = any(g.capability.writes for g in keep)
        new = Warrant(
            mission_id=old.mission_id,
            mission_sha256=old.mission_sha256,
            grants=keep,
            cannot=default_cannot(writes),
            per_run_approval=writes,
            model=old.model,
            notes=(*old.notes, f"You removed: {', '.join(sorted(set(body.remove)))}"),
        )
        m = get_mission(new.mission_id)
        verdict = check(new, m, catalogue)
        new.status = "checked" if verdict.ok else "rejected_by_checker"
        new.checker_findings = verdict.findings
        old.status = "expired"
        db.save_warrant(old)
        return db.save_warrant(new).view()

    @app.post("/api/warrants/{wid}/approve")
    def approve(wid: str, _: str = Depends(owner)) -> dict:
        return decide(wid, True)

    @app.post("/api/warrants/{wid}/reject")
    def reject(wid: str, _: str = Depends(owner)) -> dict:
        return decide(wid, False)

    @app.get("/api/warrants/{wid}/policy", response_class=PlainTextResponse)
    def policy(wid: str) -> str:
        try:
            w = db.warrant(wid)
        except KeyError:
            raise HTTPException(404, "Warrant not found") from None
        return render_policy(w, inference_url=cfg.token_factory_url)

    def launch(m: Mission, w: Any, who: str, approved_this_run: bool) -> str:
        backend_ = model_backend()
        rid = db.start_run(m.id, w.id, "warrant", who)
        threading.Thread(
            target=execute,
            kwargs=dict(
                store=db,
                mission=m,
                warrant=w,
                start_url=sites[0].base_url,
                backend=backend_,
                model=cfg.agent_model,
                approved_this_run=approved_this_run,
                max_model_calls=cfg.run_max_model_calls,
                owner=who,
                run_id=rid,
                enforcer=cfg.enforcer,
                inference_url=cfg.token_factory_url,
            ),
            daemon=True,
        ).start()
        return rid

    def scheduled_tick(at: datetime) -> None:
        for m in db.missions():
            w = db.latest_warrant(m.id)
            if not m.schedule or w is None or w.status != "approved" or w.per_run_approval:
                continue
            last = db.runs(1, m.id)
            last_at = datetime.fromtimestamp(last[0]["started_at"]) if last else None
            if is_due(m.schedule, last_at, at):
                launch(m, w, "scheduler", False)

    app.state.scheduled_tick = scheduled_tick
    if start_scheduler:
        Scheduler(scheduled_tick).start()

    @app.post("/api/missions/{mid}/runs", status_code=202)
    def start_run(mid: str, body: RunRequest, who: str = Depends(owner)) -> dict:
        m = get_mission(mid)
        w = db.latest_warrant(m.id)
        if w is None:
            raise HTTPException(409, "Draft and approve a warrant first.")
        try:
            ensure_runnable(w, m, body.approve_this_run)
        except RunRefused as exc:
            raise HTTPException(409, str(exc)) from None
        if db.count_since("runs", now() - 86400) >= cfg.daily_run_cap:
            raise HTTPException(429, "Daily run limit reached for this demo. Please watch the recorded demo video.")
        rid = launch(m, w, who, body.approve_this_run)
        return {"run_id": rid}

    @app.get("/api/eval/summary")
    def eval_summary() -> dict:
        path = project_path("eval", "results", "summary.json")
        if not path.is_file():
            return {"available": False}
        return {"available": True, **json.loads(path.read_text(encoding="utf-8"))}

    @app.get("/api/runs")
    def runs(limit: int = 30) -> list[dict]:
        return db.runs(min(limit, 100))

    @app.get("/api/runs/{rid}")
    def run(rid: str) -> dict:
        try:
            return {**db.run(rid), "events": db.events(rid)}
        except KeyError:
            raise HTTPException(404, "Run not found") from None

    @app.get("/api/runs/{rid}/stream")
    async def stream(rid: str) -> StreamingResponse:
        try:
            db.run(rid)
        except KeyError:
            raise HTTPException(404, "Run not found") from None

        async def events():
            seq = 0
            for _ in range(1800):
                batch = db.events(rid, seq)
                for e in batch:
                    seq = e["seq"]
                    yield f"id: {seq}\nevent: {e['kind']}\ndata: {json.dumps(e)}\n\n"
                    if e["kind"] == "done":
                        return
                await asyncio.sleep(0.4)

        return StreamingResponse(events(), media_type="text/event-stream", headers={"Cache-Control": "no-cache"})

    web = project_path("web", "dist")
    if web.is_dir():
        app.mount("/assets", StaticFiles(directory=web / "assets"), name="assets")

        @app.get("/{path:path}", include_in_schema=False)
        def spa(path: str) -> FileResponse:
            return FileResponse(web / "index.html")

    return app
