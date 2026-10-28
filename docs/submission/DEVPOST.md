# Devpost submission draft

Fill the bracketed parts only with measured values. Everything else is accurate as of 28 October 2026.

**Project name:** Warrant

**Tagline:** Per-mission permissions for personal AI agents, enforced by NVIDIA OpenShell.

**Track:** Personal AI

## Inspiration

Personal agents became real in 2026: OpenAI Dots and xAI Grok Bot act for you around the clock, using your
own accounts. That is exactly what makes them risky. A page the agent reads can carry instructions, and a
security audit of ClawHub, the plug-in store for the open-source agent OpenClaw, found 341 malicious skills
among 2,857. We wanted an agent you could safely give real accounts to, running on infrastructure you control.

## What it does

You give Warrant a mission, for example "every morning, check my course portal for new announcements and
deadlines and brief me". Before it runs, NVIDIA Nemotron drafts a **warrant**: the smallest set of requests the
mission needs, chosen only from a reviewed catalogue and written in plain language. Plain code checks the
draft, and you approve it. Each run then happens inside a fresh **NVIDIA OpenShell** sandbox whose policy is
generated from that warrant. Anything outside it (another site, a different page, a post the mission did not
ask for) is blocked by OpenShell, and the interface shows each decision with OpenShell's own reason.

Missions that write (submit an assignment, post a reply) ask for approval on every run.

## How we built it

- **NVIDIA Nemotron 3 Super** (`nvidia/nemotron-3-super-120b-a12b`) on **Nebius Token Factory** drafts warrants
  and drives the agent. Every call is recorded with tokens and latency.
- **NVIDIA OpenShell 0.1.5** enforces each warrant: we render the warrant as an OpenShell policy (REST
  endpoints with method and path rules, `enforcement: enforce`), create one sandbox per run, fetch every page
  from inside it, and parse OpenShell's OCSF decision log into the live security feed.
- **Nebius AI Cloud** hosts the app, the sandbox host and the demo portal [on a CPU VM].
- Python (FastAPI, Pydantic, SQLite) for the service; React, TypeScript and Motion for the interface.

The model can only choose capability IDs from a reviewed catalogue, so it cannot invent a website, a wildcard
or a broader path. A deterministic checker has the final word on every draft.

## What we verified

- Nemotron drafted minimal warrants for four missions, marking the two that write as "ask every run".
- In a real OpenShell sandbox, a warrant allowing only `GET` on one page returned 200 for that page and denied
  a `POST`, a different path and a different site, each with OpenShell's own reason.
- A full mission ran end to end: fresh sandbox, the agent read only the two pages in its warrant, Nemotron
  wrote a correct brief, the sandbox was deleted. 3 Nemotron calls, 4,442 tokens.
- Over-reach evaluation (5 frozen scenarios x 2 repeats, Nemotron 3 Super): each mission asks for more than
  its approved warrant. With broad access, 26 of 26 off-warrant requests went through; under the warrant,
  0 of 15 did. The expected fact appeared in 3 of 10 answers in both setups, so the warrant did not reduce
  task success. These runs used Warrant's built-in enforcer; the OpenShell path is verified separately above.

## Challenges

OpenShell is alpha software and we ran into several real issues, all documented in `FEEDBACK.md`: Docker
Desktop cannot act as the engine on WSL, the default image has no `sandbox` user, sandbox names are limited
to 19 characters, `sandbox exec` passes arguments through a shell, and decision log lines arrive just after
the response.

## Accomplishments

- Warrants are enforced by NVIDIA's sandbox, not by our own code.
- Every claim in this submission comes from a recorded run.

## What's next

Hermes Agent inside the sandbox as the long-running agent, scheduled missions, more reviewed sites, and a
published evaluation on a standard prompt-injection benchmark.

## Built with

nvidia-nemotron, nebius-token-factory, nvidia-openshell, nebius-ai-cloud, python, fastapi, react, typescript

## New this submission period

Warrant was built during the submission period. The evaluation habits and the interface style come from our
earlier project, Morph.

## Links

- Repository: https://github.com/TheClazer/warrant
- Demo: [public URL] (built-in enforcer; OpenShell runs are shown in the video)
- Video: [YouTube URL]
