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
    args = parser.parse_args(argv)

    if args.command == "serve":
        import uvicorn

        from .api import create_app

        uvicorn.run(create_app(), host=args.host, port=args.port, log_level="info")
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
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
