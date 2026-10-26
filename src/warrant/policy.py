"""Render a warrant as an NVIDIA OpenShell sandbox policy.

Schema per the OpenShell policy reference (version 1, ``network_policies`` with REST endpoints in
``enforce`` mode). Enforcement mode matters: OpenShell's default is ``audit``, which logs but allows.
"""

from __future__ import annotations

from urllib.parse import urlsplit

import yaml

from .models import Warrant

# OpenShell matches binaries by path glob. ``/**`` lets any process in the sandbox use the endpoint, which
# is what we want: the warrant restricts destinations, not which program inside the box makes the call.
ANY_BINARY = [{"path": "/**"}]


def _rest_endpoint(host: str, port: int, rules: list[dict]) -> dict:
    return {"host": host, "port": port, "protocol": "rest", "enforcement": "enforce", "rules": rules}


def render_policy(warrant: Warrant, *, inference_url: str | None = None, workdir: bool = True) -> str:
    network: dict[str, dict] = {}
    for grant in warrant.grants:
        rule = grant.capability.rule
        allow = [{"allow": {"method": m, "path": p}} for m in rule.methods for p in rule.paths]
        name = rule.id.replace(".", "_").replace("-", "_")
        network[name] = {"endpoints": [_rest_endpoint(rule.host, rule.port, allow)], "binaries": ANY_BINARY}

    if inference_url:
        parts = urlsplit(inference_url)
        base = parts.path.rstrip("/")
        network["nemotron_inference"] = {
            "endpoints": [
                _rest_endpoint(
                    parts.hostname or "",
                    parts.port or 443,
                    [{"allow": {"method": "POST", "path": f"{base}/chat/completions"}}],
                )
            ],
            "binaries": ANY_BINARY,
        }

    # Filesystem and process sections are left to OpenShell's driver defaults: the default image has no
    # dedicated "sandbox" user (verified on OpenShell 0.1.5), and the workdir is included when
    # filesystem_policy is omitted. A warrant governs network reach, which is what this policy pins down.
    policy: dict = {"version": 1, "network_policies": network}
    if not workdir:
        policy["filesystem_policy"] = {"include_workdir": False}
    header = (
        f"# Warrant {warrant.id} for mission {warrant.mission_id}\n"
        f"# fingerprint sha256:{warrant.fingerprint}\n"
        "# Generated from reviewed capabilities. Do not edit by hand; draft a new warrant instead.\n"
    )
    return header + yaml.safe_dump(policy, sort_keys=False, default_flow_style=False)
