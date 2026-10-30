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

## OpenShell 0.1.5 on Windows 11 + WSL 2 (Ubuntu 26.04) + Docker Desktop, 2026-10-26
- The gateway failed at first start with "no compute driver configured and auto-detection found no suitable
  installed driver". Cause: the user's systemd session predated being added to the `docker` group. Setting
  `OPENSHELL_COMPUTE_DRIVER=docker` and restarting WSL fixed it. The error message could mention group
  membership and the socket permission check.
- A policy with `process.run_as_user: sandbox` fails on the default image (`nvcr.io/nvidia/base/ubuntu:24.04`)
  with `IdentityResolutionFailed: workload user 'sandbox' does not exist`. The schema page suggests `sandbox`
  as a value, so the default image and the docs disagree.
- With Docker Desktop as the engine, sandboxes fail with `ControlSupervisorStartFailed`: the Docker driver
  starts the supervisor with host networking and endpoint `https://127.0.0.1:17670`, but Docker Desktop's
  "host" is its own VM, not the WSL distro running the gateway. The installer notes recommend Docker Engine
  from a system package; a clear error for Docker Desktop would save time.
- Sandbox names are limited to 19 characters (`name exceeds maximum length (24 > 19)`); the docs examples do not
  mention the limit.
- The default image `nvcr.io/nvidia/base/ubuntu:24.04` has no curl or Python, so even a connectivity check needs
  a custom image. A documented "tools" image would make first-run checks easier.
- Positive: the OCSF decision lines are excellent. Each line carries ALLOWED/DENIED, the method and URL, the
  policy name and a human-readable reason. This made a user-facing security feed straightforward.
- Positive: L7 enforcement on HTTPS (method and path) worked exactly as documented once `enforcement: enforce` was set.
- `openshell sandbox exec -- ARGS` passes the arguments through a shell: an argument containing a newline
  split the command. Quoting every argument fixed it. Documenting this (or passing argv verbatim) would help.
- Decision log lines arrive shortly after the HTTP response, so a client must wait for the matching line.
- On WSL, the VM shuts down when no Windows process is attached, which stops the gateway user service.
  Users need `loginctl enable-linger` and something keeping WSL alive; worth a note in the WSL docs.

## Nebius Token Factory, 2026-10-30
- Positive: the OpenAI-compatible API meant no model server to run. The same client worked on a laptop, on a free hosted demo and in the evaluation, and Nemotron 3 Super handled tool calling and JSON replies well enough for the agent loop.
- A live run failed once with HTTP 529 (overloaded). It is not in the set of status codes clients commonly retry, so it surfaced as a hard failure until we added it. Documenting retryable codes and a recommended backoff would help.
- We did not use Nebius AI Cloud, because OpenShell ran on our own machine within our budget. We cannot comment on it.

## NVIDIA OpenShell, 2026-10-30
- With `FORCE_COLOR` set in the environment, our status check on `openshell sandbox get` stopped matching, and a healthy sandbox was reported as not ready. Parsing human-readable output is fragile: a `--output json` option on `sandbox get` and on logs would remove this class of bug.
- Positive: an over-reach evaluation with one fresh sandbox per run (10 runs) worked reliably, and it blocked all 17 off-warrant requests.
- Positive: the same generated policy enforced method and path rules against a live public API (`api.github.com`).
- It would be useful to have a documented way to give a sandboxed process a secret for one host only, so an agent can use an API token without being able to read it.
