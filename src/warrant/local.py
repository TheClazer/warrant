"""The terminal experience: ``warrant try`` runs the whole flow, ``warrant guard`` wraps a local program."""

from __future__ import annotations

import getpass
import os
import socket
import sys
import threading
import time
from dataclasses import replace
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

from .checker import check
from .compiler import CompileError, compile_warrant, narrow_warrant
from .config import Settings
from .guard import Seen, run_guarded
from .llm import ChatBackend, TokenFactory
from .models import Mission, Warrant
from .policy import render_policy
from .runner import execute
from .sites import build_registry, capability_index
from .store import Store

DEFAULT_JOB = "Brief me on this week's announcements and tell me my latest grades."
EVERY_RUN = " (asks you every run)"


def _paint(code: str, text: str) -> str:
    return f"\033[{code}m{text}\033[0m" if sys.stdout.isatty() and "NO_COLOR" not in os.environ else text


def bold(text: str) -> str:
    return _paint("1", text)


def dim(text: str) -> str:
    return _paint("2", text)


def allowed(text: str) -> str:
    return _paint("32", text)


def blocked(text: str) -> str:
    return _paint("1;33", text)


def _setup_output() -> None:
    reconfigure = getattr(sys.stdout, "reconfigure", None)
    if reconfigure:
        reconfigure(encoding="utf-8", errors="replace")
    if os.name == "nt":
        os.system("")  # switches on ANSI colours in the Windows console


def free_port(bind: str = "127.0.0.1") -> int:
    with socket.socket() as probe:
        probe.bind((bind, 0))
        return probe.getsockname()[1]


def serve(server: Any) -> None:
    """Start a uvicorn server on a background thread and wait until it accepts requests."""
    threading.Thread(target=server.run, daemon=True).start()
    deadline = time.monotonic() + 15
    while not server.started:
        if time.monotonic() > deadline:
            raise RuntimeError("The demo portal did not start.")
        time.sleep(0.05)


def _own_address() -> str:
    """This machine's network address. No packet is sent: connecting a UDP socket only picks a route."""
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as probe:
        probe.connect(("192.0.2.1", 9))
        return probe.getsockname()[0]


def _start_demo_portal(for_sandbox: bool = False) -> str:
    """Serve the fictional portal from this process, on a free port.

    An OpenShell sandbox has its own network, so 127.0.0.1 there is not this machine. For sandboxed runs the
    portal listens on this machine's network address instead.
    """
    import uvicorn

    from .demo.portal import create_portal

    bind = "0.0.0.0" if for_sandbox else "127.0.0.1"
    address = _own_address() if for_sandbox else "127.0.0.1"
    port = free_port(bind)
    serve(uvicorn.Server(uvicorn.Config(create_portal(), host=bind, port=port, log_level="warning")))
    return f"http://{address}:{port}"


def _ask(prompt: str, assume: str | None) -> str:
    if assume is not None:
        print(f"{prompt}{assume}")
        return assume
    return input(prompt).strip()


def _review(warrant: Warrant, catalogue: dict, mission: Mission, remove: list[str], yes: bool) -> Warrant | None:
    """Show the warrant, let the person take things away, and return it approved, or None if they decline."""
    for cid in remove:
        if any(g.capability.id == cid for g in warrant.grants):
            warrant = narrow_warrant(warrant, [cid])
    print(bold("\nThe AI asked for:"))
    for i, grant in enumerate(warrant.grants, 1):
        note = blocked("  asks every run") if grant.capability.writes else ""
        print(f"  {i}. {grant.capability.plain.replace(EVERY_RUN, '')}{note}")
    print(dim("  Everything else on this site, and every other website, stays blocked."))
    if not remove and not yes and len(warrant.grants) > 1:
        answer = input("\nRemove any? Type numbers like 2, or press Enter to keep them all: ").strip()
        picks = {int(n) for n in answer.replace(",", " ").split() if n.isdigit()}
        ids = [g.capability.id for i, g in enumerate(warrant.grants, 1) if i in picks]
        if ids:
            warrant = narrow_warrant(warrant, ids)
            for cid in ids:
                print(f"  Removed {catalogue[cid].plain.replace(EVERY_RUN, '')}")
    verdict = check(warrant, mission, catalogue)
    if not verdict.ok:
        print(blocked("\nThe checker refused this warrant:"))
        for finding in verdict.findings:
            print(f"  {finding}")
        return None
    if _ask("\nApprove and run? [Y/n] ", "y" if yes else None).lower() not in {"", "y", "yes"}:
        return None
    warrant.status = "approved"
    return warrant


def _follow(store: Store, run_id: str, portal_host: str, worker: threading.Thread) -> list[dict]:
    """Print the run as it happens, and return its events."""
    seen = 0
    events: list[dict] = []
    while True:
        fresh = store.events(run_id, after=seen)
        for event in fresh:
            seen = max(seen, event["seq"])
            events.append(event)
            if event["kind"] == "network":
                host = "" if event["host"] == portal_host else event["host"]
                target = f"{event['method']} {host}{event['path']}"
                if event["decision"] == "blocked":
                    print(f"  {blocked('BLOCKED')}  {target}  {dim('not in this warrant')}")
                else:
                    print(f"  {allowed('ALLOWED')}  {target}")
            elif event["kind"] == "sandbox":
                print(dim(f"  NVIDIA OpenShell sandbox {event['name']}"))
            elif event["kind"] == "error":
                print(blocked(f"  Error: {event.get('error', 'unknown')}"))
        if not worker.is_alive() and not fresh:
            return events
        time.sleep(0.15)


def _report(events: list[dict], portal_host: str) -> None:
    network = [e for e in events if e["kind"] == "network"]
    stopped = [e for e in network if e["decision"] == "blocked"]
    answer = next((e for e in events if e["kind"] == "answer"), None)
    models = [e for e in events if e["kind"] == "model"]
    tokens = sum(int(e.get("prompt_tokens") or 0) + int(e.get("completion_tokens") or 0) for e in models)
    if answer:
        print(bold("\nResult"))
        for line in str(answer.get("text", "")).splitlines():
            if not set(line.strip()) <= {"-", "|", ":", " "} or not line.strip():
                print(f"  {line.replace('**', '').replace('`', '')}")
    print(bold("\nWhat changed because of Warrant"))
    if stopped:
        for event in stopped:
            host = "" if event["host"] == portal_host else event["host"]
            print(f"  Without it: {event['method']} {host}{event['path']} would have gone through.")
        print(f"  With it:    {blocked('stopped before being sent.')} The agent never got that data.")
    else:
        print("  Without it: the agent would have had your full access.")
        print(f"  With it:    it stayed inside its warrant, with {len(network)} allowed requests.")
    print(dim(f"\n  {len(models)} Nemotron calls, {tokens:,} tokens"))


def run_try(
    settings: Settings,
    job: str | None = None,
    remove: list[str] | None = None,
    yes: bool = False,
    backend: ChatBackend | None = None,
) -> int:
    _setup_output()
    key = settings.nebius_api_key.strip()
    if backend is None and not key:
        if not sys.stdin.isatty():
            print("Set NEBIUS_API_KEY to your Nebius Token Factory key, then run this again.", file=sys.stderr)
            return 2
        key = getpass.getpass("Nebius Token Factory key (used for this run, not saved): ").strip()
        if not key:
            print("A key is needed to call Nemotron.", file=sys.stderr)
            return 2
    data_dir = Path(os.environ["WARRANT_DATA_DIR"]) if "WARRANT_DATA_DIR" in os.environ else Path.home() / ".warrant"
    portal = settings.portal_url if "WARRANT_PORTAL_URL" in os.environ else _start_demo_portal(settings.enforcer == "openshell")
    settings = replace(settings, nebius_api_key=key, portal_url=portal, data_dir=data_dir)
    portal_host = urlsplit(portal).hostname or ""
    catalogue = capability_index(build_registry(settings))
    store = Store(data_dir / "warrant.sqlite")
    model_backend = backend or TokenFactory(settings)

    text = job or DEFAULT_JOB
    print(bold("WARRANT") + dim("  permissions for personal AI agents"))
    print(dim(f"Fictional course portal running at {portal}. No real accounts are involved.\n"))
    print(f"{bold('Job')}  {text}")
    print(dim(f"\nWithout Warrant, an agent with your access could do {len(catalogue)} things here and reach any website."))
    print("\nAsking NVIDIA Nemotron what this job needs...")

    mission = store.save_mission(Mission(title=text[:80], text=text))
    try:
        draft = compile_warrant(mission, catalogue, model_backend, settings.planner_model)
    except CompileError as exc:
        print(blocked(str(exc)), file=sys.stderr)
        return 1
    if not draft.grants:
        print("The AI found nothing on the reviewed sites that can do this job.")
        for note in draft.notes:
            print(dim(f"  {note}"))
        return 1
    draft.status = "checked"
    warrant = _review(draft, catalogue, mission, remove or [], yes)
    if warrant is None:
        print("\nNothing ran.")
        return 0
    store.save_warrant(warrant)

    print(bold("\nRunning the agent"))
    run_id = store.start_run(mission.id, warrant.id, "warrant", "owner")
    worker = threading.Thread(
        target=execute,
        kwargs=dict(
            store=store,
            mission=mission,
            warrant=warrant,
            start_url=portal,
            backend=model_backend,
            model=settings.agent_model,
            approved_this_run=True,
            max_model_calls=settings.run_max_model_calls,
            run_id=run_id,
            enforcer=settings.enforcer,
            inference_url=settings.token_factory_url,
        ),
        daemon=True,
    )
    worker.start()
    _report(_follow(store, run_id, portal_host, worker), portal_host)
    policy_path = data_dir / "policies" / f"{warrant.id}.yaml"
    policy_path.parent.mkdir(parents=True, exist_ok=True)
    policy_path.write_text(render_policy(warrant, inference_url=settings.token_factory_url), encoding="utf-8")
    print(dim(f"  OpenShell policy for this warrant: {policy_path}"))
    return 0


def run_guard(hosts: list[str], command: list[str]) -> int:
    _setup_output()
    if command and command[0] == "--":
        command = command[1:]
    if not command:
        print("Give a command to run, for example: warrant guard --allow example.com -- python my_agent.py", file=sys.stderr)
        return 2
    print(bold("WARRANT GUARD") + dim(f"  allowed: {', '.join(hosts) or 'nothing'}"), file=sys.stderr)
    counts = {"allowed": 0, "blocked": 0}

    def report(seen: Seen) -> None:
        if seen.allowed:
            counts["allowed"] += 1
            print(f"  {allowed('ALLOWED')}  {seen.method} {seen.target}", file=sys.stderr, flush=True)
        else:
            counts["blocked"] += 1
            print(f"  {blocked('BLOCKED')}  {seen.method} {seen.target}", file=sys.stderr, flush=True)

    try:
        code = run_guarded(command, hosts, report)
    except FileNotFoundError:
        print(f"Command not found: {command[0]}", file=sys.stderr)
        return 127
    print(dim(f"  {counts['allowed']} allowed, {counts['blocked']} blocked"), file=sys.stderr)
    return code


def run_prove() -> int:
    from .prove import JOB, held, run_proof

    _setup_output()
    print(bold("WARRANT PROVE") + dim("  no AI, no key, and nothing leaves this machine"))
    print(f"\nA scripted agent is given one job: {JOB.lower()}")
    print("It also tries to do three things nobody asked for, first with broad access, then under a warrant.\n")
    outcomes = run_proof()
    bare, guarded = outcomes["without"], outcomes["with"]
    width = max(len(name) for name in bare.attempts) + 2
    print(bold(f"  {'':<{width}}{'Without Warrant':<18}With Warrant"))
    for name, result in bare.attempts.items():
        after = guarded.attempts[name]
        shown = blocked(f"{after:<10}") if after == "BLOCKED" else allowed(f"{after:<10}")
        print(f"  {name:<{width}}{result:<18}{shown}")
    print(bold("\n  Checked at the receiving end"))
    print(f"  {'Submissions the portal recorded':<{width + 8}}{bare.submissions:<10}{guarded.submissions}")
    print(f"  {'Messages the stranger received':<{width + 8}}{len(bare.stranger_received):<10}{len(guarded.stranger_received)}")
    if not held(outcomes):
        print(blocked("\nThis result is not what Warrant promises. Please report it."))
        return 1
    print(allowed("\nSame agent, same attempts. The warrant is the only difference."))
    return 0
