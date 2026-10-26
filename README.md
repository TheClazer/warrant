# Warrant

**Per-mission permissions for personal AI agents, enforced by NVIDIA OpenShell.**

Personal agents are most useful when they can act as you: read your portals, check your accounts, submit
things on your behalf. That also makes them dangerous. A page the agent reads can contain instructions,
and a plug-in can ask for more than it needs.

Warrant gives every mission a *warrant*: the smallest set of network requests the mission needs, written
in plain language, approved by you, and enforced at the network layer by an
[NVIDIA OpenShell](https://github.com/NVIDIA/OpenShell) sandbox. If the agent is fooled into reaching
anywhere else, the request is blocked, logged and shown to you, and the mission carries on.

Built for the Nebius × NVIDIA Global AI Hackathon (Personal AI track).

## How it works

1. **You write a mission.** "Every morning, check my course portal for announcements and deadlines and brief me."
2. **Nemotron drafts the warrant.** NVIDIA Nemotron 3 Super, served by Nebius Token Factory, chooses the
   smallest set of capabilities from a **reviewed catalogue**. It cannot invent hosts, wildcards or paths:
   rules come only from the catalogue.
3. **Code checks it.** A plain-code checker rejects anything too broad: unknown or altered capabilities,
   whole-site access, more than five sites, mission text changed since drafting, writes without per-run approval.
4. **You approve it** in plain words. Writing missions ask again on every run.
5. **OpenShell enforces it.** The warrant becomes an OpenShell policy (`network_policies`, REST endpoints,
   `enforcement: enforce`). Each run gets its own sandbox.
6. **You see everything.** Allowed and blocked requests, Nemotron calls, tokens and cost stream to the
   interface while the agent works.

```
mission ──► Nemotron (Token Factory) ──► draft warrant ──► checker ──► you approve
                                                                         │
                         security feed ◄── OpenShell sandbox per run ◄───┘
                                              └─ agent (Hermes on the host)
```

## What is in this repository

| Path | What it is |
|---|---|
| `src/warrant/models.py` | Missions, capabilities, rules, warrants and their fingerprints |
| `src/warrant/sites.py` | The reviewed capability catalogue |
| `src/warrant/compiler.py` | Nemotron drafts a warrant from the catalogue |
| `src/warrant/checker.py` | Fixed rules with the final word |
| `src/warrant/policy.py` | Warrant → NVIDIA OpenShell policy YAML |
| `src/warrant/enforce/` | Request gate, local development enforcer, OpenShell CLI backend |
| `src/warrant/agent/` | Tool-using agent used for local development and repeatable runs |
| `src/warrant/runner.py` | Runs a mission under its warrant and records every event |
| `src/warrant/api.py` | FastAPI service, including a live event stream |
| `web/` | React interface (missions, warrant approval, live run view, reviewed sites) |
| `FEEDBACK.md` | Notes on Nebius and NVIDIA tools gathered while building |

## Run it locally

Requires Python 3.11, [uv](https://docs.astral.sh/uv/) and Node 20+.

```bash
uv sync
cd web && npm install && npm run build && cd ..
export NEBIUS_API_KEY=...            # Nebius Token Factory key
uv run warrant serve --port 8090
```

Open http://127.0.0.1:8090. Without `NEBIUS_API_KEY` the interface works, but drafting and running are
disabled and say so.

On a laptop without Docker, requests are enforced by the in-process development enforcer, which applies
the same decision logic as the OpenShell policy. On the Linux host, set `WARRANT_ENFORCER=openshell`.

## Tests

```bash
uv run pytest
uv run ruff check src tests
uv run mypy
```

## How we use NVIDIA and Nebius

- **NVIDIA Nemotron 3 Super** (`nvidia/nemotron-3-super-120b-a12b`) drafts warrants and drives the agent.
- **Nebius Token Factory** serves Nemotron through its OpenAI-compatible API. Every call is recorded with
  tokens and latency; cost is shown when prices are configured from the Token Factory price page.
- **NVIDIA OpenShell** enforces each warrant as a sandbox policy on the Nebius host.
- **Hermes Agent** (Nous Research) is the agent run inside OpenShell on the host.

## Honesty

The demo portal is fictional. Numbers shown in the interface come from recorded runs only. Warrant blocks
requests outside a mission's warrant; it does not stop a page from misleading the agent's answer, and it
does not stop misuse of access the warrant grants. Writing capabilities therefore ask on every run.

## Licence

Apache-2.0. Hermes Agent, OpenShell and Nemotron are the work of their respective authors.
