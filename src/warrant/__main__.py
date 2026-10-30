"""Command line: ``warrant serve`` runs the API and the built interface; ``warrant policy`` prints a policy."""

from __future__ import annotations

import argparse
import sys


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="warrant", description="Per-mission warrants for personal AI agents.")
    sub = parser.add_subparsers(dest="command", required=True)
    serve = sub.add_parser("serve", help="run the API and web interface")
    serve.add_argument("--host", default="127.0.0.1")
    serve.add_argument("--port", type=int, default=8090)
    pol = sub.add_parser("policy", help="print the OpenShell policy for a stored warrant")
    pol.add_argument("warrant_id")
    sub.add_parser("status", help="show configuration (no secrets)")
    tri = sub.add_parser("try", help="run the whole flow in your terminal against the fictional portal")
    tri.add_argument("job", nargs="?", help="what the agent should do on the portal")
    tri.add_argument("--remove", action="append", default=[], help="capability ID to take away, for example portal.read.grades")
    tri.add_argument("--yes", action="store_true", help="approve without asking")
    tri.add_argument("--save-as", metavar="NAME", help="save this job and its warrant as a reusable skill")
    rem = sub.add_parser("remember", help="add a note the agent gets as background (grants no permissions)")
    rem.add_argument("text")
    mem = sub.add_parser("memory", help="list what Warrant remembers")
    mem.add_argument("--forget", metavar="ID", help="remove one entry")
    sit = sub.add_parser("site", help="add, list or remove the real sites an agent may ever be granted")
    sit.add_argument("action", choices=["add", "list", "remove"])
    sit.add_argument("name", nargs="?")
    sit.add_argument("url", nargs="?")
    sit.add_argument("--read", action="append", default=[], metavar="PATH", help="a path it may GET; repeat as needed")
    sit.add_argument("--write", action="append", default=[], metavar="PATH", help="a path it may POST to; asks every run")
    sit.add_argument("--token-env", metavar="VAR", help="environment variable holding a token for this site")
    skl = sub.add_parser("skill", help="list, run or delete saved skills")
    skl.add_argument("action", choices=["list", "run", "delete"])
    skl.add_argument("name", nargs="?")
    skl.add_argument("--yes", action="store_true", help="allow a skill that changes something, for this run")
    sub.add_parser("prove", help="show a misbehaving agent with and without a warrant (no AI, no key)")
    guard = sub.add_parser("guard", help="run a local program with its web traffic limited to hosts you allow")
    guard.add_argument("--allow", action="append", default=[], metavar="HOST", help="allowed host, or *.example.com")
    guard.add_argument("command_", nargs=argparse.REMAINDER, metavar="-- COMMAND", help="the program and its arguments")
    portal = sub.add_parser("portal", help="run the fictional demo course portal")
    portal.add_argument("--host", default="127.0.0.1")
    portal.add_argument("--port", type=int, default=8201)
    osc = sub.add_parser(
        "openshell-check", help="on the Linux host: create a sandbox from a warrant, show policy and logs"
    )
    osc.add_argument("warrant_id")
    osc.add_argument("--keep", action="store_true", help="leave the sandbox running for manual tests")
    ev = sub.add_parser("eval", help="run the frozen evaluation scenarios against the demo portal")
    ev.add_argument("--scenarios", default="eval/scenarios.yaml")
    ev.add_argument("--out", default="eval/results")
    ev.add_argument("--repeats", type=int, default=2)
    args = parser.parse_args(argv)

    if args.command == "serve":
        import uvicorn

        from .api import create_app

        uvicorn.run(create_app(start_scheduler=True), host=args.host, port=args.port, log_level="info")
        return 0

    if args.command == "portal":
        import uvicorn

        from .demo.portal import create_portal

        uvicorn.run(create_portal(), host=args.host, port=args.port, log_level="warning")
        return 0

    if args.command == "prove":
        from .local import run_prove

        return run_prove()

    if args.command == "site":
        from .local import run_site

        return run_site(args.action, args.name, args.url, args.read, args.write, args.token_env)

    if args.command == "remember":
        from .local import run_remember

        return run_remember(args.text)

    if args.command == "memory":
        from .local import run_memory

        return run_memory(args.forget)

    if args.command == "guard":
        from .local import run_guard

        return run_guard(args.allow, args.command_)

    from .config import get_settings

    settings = get_settings()
    if args.command == "try":
        from .local import run_try

        return run_try(settings, args.job, args.remove, args.yes, save_as=args.save_as)
    if args.command == "skill":
        from .local import run_skill

        return run_skill(settings, args.action, args.name, args.yes)
    if args.command == "status":
        import json

        print(json.dumps(settings.public(), indent=2))
        return 0
    if args.command == "policy":
        from .policy import render_policy
        from .store import Store

        store = Store(settings.data_dir / "warrant.sqlite")
        sys.stdout.write(render_policy(store.warrant(args.warrant_id), inference_url=settings.token_factory_url))
        return 0
    if args.command == "eval":
        import json
        from pathlib import Path

        from .evaluation import run_evaluation
        from .llm import TokenFactory
        from .sites import build_registry, capability_index
        from .store import Store

        summary = run_evaluation(
            Path(args.scenarios),
            Path(args.out),
            Store(settings.data_dir / "eval.sqlite"),
            capability_index(build_registry(settings)),
            TokenFactory(settings),
            settings.agent_model,
            settings.portal_url,
            repeats=args.repeats,
            enforcer=settings.enforcer,
            inference_url=settings.token_factory_url,
        )
        print(json.dumps(summary["setups"], indent=2))
        return 0
    if args.command == "openshell-check":
        from .enforce import openshell
        from .store import Store

        warrant = Store(settings.data_dir / "warrant.sqlite").warrant(args.warrant_id)
        box = openshell.create(warrant, settings.token_factory_url)
        print(f"Created sandbox {box.name} with policy {box.policy_path}")
        try:
            print(openshell._run(["policy", "get", box.name, "--full"]).stdout)
            for e in openshell.decisions(box):
                print(e["decision"], e.get("method"), e["host"], e.get("path"), e["reason"])
        finally:
            if not args.keep:
                openshell.delete(box)
                print(f"Deleted sandbox {box.name}")
        return 0
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
