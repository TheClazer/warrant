"""Run one mission under its approved warrant and record everything that happened."""

from __future__ import annotations

from typing import Any, Literal

from .agent.reader import run_agent
from .enforce.client import GatedClient
from .enforce.gate import Decision, Gate, allow_all
from .llm import ChatBackend, Ledger, Metered, Usage
from .models import Mission, Warrant
from .sites import site_tokens
from .store import Store

Setup = Literal["warrant", "broad", "broad_resist"]


class RunRefused(RuntimeError):
    pass


def entry_points(warrant: Warrant | None, fallback: str) -> list[str]:
    """Concrete pages the warrant allows the agent to GET, used as starting points."""
    if warrant is None:
        return [fallback]
    urls = []
    for rule in warrant.rules:
        if "GET" not in rule.methods:
            continue
        default = 443 if rule.scheme == "https" else 80
        origin = f"{rule.scheme}://{rule.host}" + ("" if rule.port == default else f":{rule.port}")
        urls += [origin + p for p in rule.paths if "*" not in p]
    return urls or [fallback]


def ensure_runnable(warrant: Warrant, mission: Mission, approved_this_run: bool) -> None:
    if warrant.mission_id != mission.id or warrant.mission_sha256 != mission.text_sha256:
        raise RunRefused("The warrant does not match the current mission text.")
    if warrant.status != "approved":
        raise RunRefused("The warrant has not been approved.")
    if warrant.per_run_approval and not approved_this_run:
        raise RunRefused("This mission writes, so it needs your approval for this run.")


def execute(
    store: Store,
    mission: Mission,
    warrant: Warrant | None,
    start_url: str,
    backend: ChatBackend,
    model: str,
    *,
    setup: Setup = "warrant",
    approved_this_run: bool = False,
    max_model_calls: int = 40,
    max_usd: float | None = None,
    owner: str = "owner",
    run_id: str | None = None,
    enforcer: str = "local",
    inference_url: str | None = None,
    use_memory: bool = False,
) -> dict[str, Any]:
    if setup == "warrant":
        if warrant is None:
            raise RunRefused("No warrant for this mission.")
        ensure_runnable(warrant, mission, approved_this_run)
        gate = Gate.for_warrant(warrant)
    else:
        gate = allow_all()

    rid = run_id or store.start_run(mission.id, warrant.id if warrant else None, setup, owner)

    def emit(kind: str, body: dict[str, Any]) -> None:
        store.add_event(rid, kind, body)

    def on_decision(d: Decision) -> None:
        emit("network", d.event())

    def on_usage(u: Usage) -> None:
        emit(
            "model",
            {
                "model": u.model,
                "prompt_tokens": u.prompt_tokens,
                "completion_tokens": u.completion_tokens,
                "latency_s": u.latency_s,
                "cost_usd": u.cost_usd,
                "purpose": u.purpose,
            },
        )

    ledger = Ledger(max_calls=max_model_calls, max_usd=max_usd, on_record=on_usage)
    emit(
        "start",
        {
            "setup": setup,
            "warrant": warrant.view() if warrant and setup == "warrant" else None,
            "start_url": start_url,
            "model": model,
        },
    )
    status = "failed"
    result: dict[str, Any] = {}
    box = None
    http: Any = None
    try:
        if enforcer == "openshell" and setup == "warrant" and warrant is not None:
            from .enforce import openshell
            from .enforce.sandbox_client import SandboxClient

            emit("step", {"text": "Creating an NVIDIA OpenShell sandbox for this warrant"})
            box = openshell.create(warrant, inference_url, workdir=store.path.parent / "policies")
            emit("sandbox", {"name": box.name, "fingerprint": warrant.fingerprint, "enforcer": "openshell"})
            http = SandboxClient(box, on_decision)
        else:
            http = GatedClient(gate, on_decision, tokens=site_tokens() if setup == "warrant" else None)
        starts = "\n".join(entry_points(warrant, start_url))
        background = ""
        if use_memory:
            from .memory import briefing

            background, used = briefing(store, mission, writes=bool(warrant and warrant.writes))
            if background:
                emit("memory", used)
        outcome = run_agent(
            mission.text + background, starts, Metered(backend, ledger), model, http, emit, resist_prompt=use_memory or setup == "broad_resist"
        )
        status = outcome.status
        result = {"answer": outcome.answer, "steps": outcome.steps, "blocked": outcome.blocked}
        if use_memory and status == "completed":
            from .memory import record_result

            record_result(store, mission, outcome.answer)
    except Exception as exc:  # recorded, never swallowed silently
        result = {"error": f"{type(exc).__name__}: {exc}"[:400]}
        emit("error", result)
    finally:
        if http is not None:
            http.close()
        if box is not None:
            from .enforce import openshell

            openshell.delete(box)
            emit("step", {"text": f"Deleted sandbox {box.name}"})
        usage = ledger.summary()
        store.finish_run(rid, status, result, usage)
        emit("done", {"status": status, **usage})
    return store.run(rid)
