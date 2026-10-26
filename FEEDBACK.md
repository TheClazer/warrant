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
