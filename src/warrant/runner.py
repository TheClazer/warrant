"""Run one mission under its approved warrant and record everything that happened."""

from __future__ import annotations

from typing import Any, Literal

from .agent.reader import run_agent
from .enforce.client import GatedClient
from .enforce.gate import Decision, Gate, allow_all
from .llm import ChatBackend, Ledger, Metered, Usage
from .models import Mission, Warrant
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
    http = GatedClient(gate, on_decision)
    status = "failed"
    result: dict[str, Any] = {}
    try:
        starts = "\n".join(entry_points(warrant if setup == "warrant" else None, start_url))
        outcome = run_agent(
            mission.text, starts, Metered(backend, ledger), model, http, emit, resist_prompt=setup == "broad_resist"
        )
        status = outcome.status
        result = {"answer": outcome.answer, "steps": outcome.steps, "blocked": outcome.blocked}
    except Exception as exc:  # recorded, never swallowed silently
        result = {"error": f"{type(exc).__name__}: {exc}"[:400]}
        emit("error", result)
    finally:
        http.close()
        usage = ledger.summary()
        store.finish_run(rid, status, result, usage)
        emit("done", {"status": status, **usage})
    return store.run(rid)
