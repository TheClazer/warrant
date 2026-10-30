# Evaluation records, 31 October 2026

Five frozen over-reach scenarios (`eval/scenarios.yaml`), twice each, with broad access and under a warrant.
Real Nemotron 3 Super calls through Nebius Token Factory, against the fictional portal. NVIDIA OpenShell 0.1.5
enforced each warrant run in its own sandbox.

| | Off-warrant requests tried | Enforcer let through | Portal's log shows arrived |
|---|---|---|---|
| Broad access | 19 | 19 | 19 |
| Warrant | 15 | 0 | 0 |

The expected fact appeared in 4 of 10 answers in both setups.

## Files

- `portal-access.jsonl`: the portal's own log of every request it received. It is written by the portal, so it does not depend on the enforcer. The first line is the startup check, before any run.
- `records/<run id>.json`: one run. It holds OpenShell's raw log lines, the policy it enforced, the decisions Warrant recorded, the portal requests in that run's time window, and the agent's answer.
- `summary.json`, `runs.jsonl`: the totals Warrant calculated.
- `verify.py`: recounts from the raw files, using no Warrant code.

```bash
python eval/evidence/verify.py
```

## Rerun it

You need Linux or WSL 2, Docker Engine, OpenShell 0.1.5, the sandbox image from the main README, and a Nebius
Token Factory key. Numbers will vary, because the model does. Replace `HOST_IP` with this machine's address, which
the sandbox must be able to reach. The portal log must be empty or new.

```bash
WARRANT_PORTAL_ACCESS_LOG=/tmp/access.jsonl warrant portal --host 0.0.0.0 --port 8203
```

```bash
NEBIUS_API_KEY=... WARRANT_PORTAL_URL=http://HOST_IP:8203 WARRANT_ENFORCER=openshell WARRANT_RUN_MAX_MODEL_CALLS=12 \
  warrant eval --scenarios eval/scenarios.yaml --out /tmp/out --portal-log /tmp/access.jsonl
```

## What this does not prove

- We ran this ourselves. Nobody independent watched it, and committing files does not prove they were not edited first. Rerunning it is the stronger check.
- The portal is fictional and the sample is small.
- Off-warrant attempts depend on what the model chose to do, so the two setups tried different numbers of requests.
- It tests over-reach, not pages planted to mislead the agent.
- The earlier run in `eval/results` and the video (24 of 24, 0 of 17) has only summaries. Its raw logs were not kept.
