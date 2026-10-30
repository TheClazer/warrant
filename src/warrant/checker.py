"""The checker: plain code with the final word on every warrant.

The model drafts; this module decides. It has no network access and no model calls, so a prompt
injection cannot argue with it.
"""

from __future__ import annotations

from dataclasses import dataclass

from .models import Capability, Mission, Warrant, covers_whole_site

MAX_HOSTS = 5
MAX_GRANTS = 8


@dataclass(frozen=True)
class CheckResult:
    ok: bool
    findings: tuple[str, ...]


def check(warrant: Warrant, mission: Mission, catalogue: dict[str, Capability]) -> CheckResult:
    findings: list[str] = []

    if warrant.mission_id != mission.id:
        findings.append("Warrant belongs to a different mission.")
    if warrant.mission_sha256 != mission.text_sha256:
        findings.append("Mission text changed after this warrant was drafted. Draft a new warrant.")
    if not warrant.grants:
        findings.append("A warrant must grant at least one capability.")
    if len(warrant.grants) > MAX_GRANTS:
        findings.append(f"More than {MAX_GRANTS} capabilities. Split the mission into smaller missions.")

    seen: set[str] = set()
    for grant in warrant.grants:
        cap = grant.capability
        if cap.id in seen:
            findings.append(f"Capability {cap.id} is granted twice.")
        seen.add(cap.id)
        reviewed = catalogue.get(cap.id)
        if reviewed is None:
            findings.append(f"Capability {cap.id} is not in the reviewed site registry.")
        elif reviewed != cap:
            findings.append(f"Capability {cap.id} differs from the reviewed registry entry.")
        rule = cap.rule
        if "*" in rule.host:
            findings.append(f"Wildcard host in {cap.id}.")
        if any(covers_whole_site(p) for p in rule.paths):
            findings.append(f"Capability {cap.id} covers a whole site; registry entries must be narrower.")
        if not cap.plain.strip():
            findings.append(f"Capability {cap.id} has no plain-language line.")

    if len(warrant.hosts) > MAX_HOSTS:
        findings.append(f"More than {MAX_HOSTS} sites. Split the mission.")
    if warrant.writes and not warrant.per_run_approval:
        findings.append("Warrants that write must require approval on every run.")

    return CheckResult(ok=not findings, findings=tuple(findings))
