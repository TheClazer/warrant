# Feedback on Nebius and NVIDIA tools

Notes kept while building, for the hackathon feedback submission. Facts only; each entry has a date.

## NVIDIA OpenShell
- 2026-10-26: The policy schema reference is clear about `enforcement` defaulting to `audit`. That default is easy to miss: a policy without `enforcement: enforce` logs violations but lets them through. A warning when a policy contains only audit endpoints would help.
- 2026-10-26: The docs do not show a documented catch-all for `binaries`; we use the glob `/**` and will confirm on the host.
- 2026-10-26: There is no separate command or documented format for denied requests; the guidance is to read `openshell logs NAME --source sandbox`. A structured denial stream (JSON lines) would make it much easier to build user-facing security feeds.

## Nebius Token Factory
- 2026-10-26: The fine-tuning model list does not include any Nemotron model, so per-user adaptation on Nemotron is not available through Token Factory today.

## Hermes Agent
- 2026-10-26: `hermes -z PROMPT` gives a one-shot mode, which is what a scheduled mission needs.
