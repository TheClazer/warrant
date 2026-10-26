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
    portal = sub.add_parser("portal", help="run the fictional demo course portal")
    portal.add_argument("--host", default="127.0.0.1")
    portal.add_argument("--port", type=int, default=8201)
    osc = sub.add_parser(
        "openshell-check", help="on the Linux host: create a sandbox from a warrant, show policy and logs"
    )
    osc.add_argument("warrant_id")
    osc.add_argument("--keep", action="store_true", help="leave the sandbox running for manual tests")
    args = parser.parse_args(argv)

    if args.command == "serve":
        import uvicorn

        from .api import create_app

        uvicorn.run(create_app(), host=args.host, port=args.port, log_level="info")
        return 0

    if args.command == "portal":
        import uvicorn

        from .demo.portal import create_portal

        uvicorn.run(create_portal(), host=args.host, port=args.port, log_level="warning")
        return 0

    from .config import get_settings

    settings = get_settings()
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
    if args.command == "openshell-check":
        from .enforce import openshell
        from .store import Store

        warrant = Store(settings.data_dir / "warrant.sqlite").warrant(args.warrant_id)
        name = f"warrant-check-{warrant.id[-8:]}"
        box = openshell.create(warrant, name, settings.token_factory_url)
        print(f"Created sandbox {name} with policy {box.policy_path}")
        try:
            print(openshell._run(["policy", "get", name, "--full"]).stdout)
            print("Denied requests so far:", openshell.denials(box))
        finally:
            if not args.keep:
                openshell.delete(box)
                print(f"Deleted sandbox {name}")
        return 0
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
