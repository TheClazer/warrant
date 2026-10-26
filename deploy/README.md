# Deploying Warrant on a Nebius machine

Target: one Linux VM in Nebius AI Cloud (CPU is enough; no GPU), public IP, DNS names for the app and the
demo portal. Check the hourly price of the machine against your credits before creating it.

## 1. Base packages

```bash
sudo apt-get update && sudo apt-get install -y docker.io caddy git
sudo usermod -aG docker "$USER"   # log out and in again
curl -LsSf https://astral.sh/uv/install.sh | sh
```

Node 20+ is needed only to build the interface (or build it locally and copy `web/dist`).

## 2. NVIDIA OpenShell

Install with the official script from https://github.com/NVIDIA/OpenShell, then confirm the CLI works:

```bash
openshell --help
openshell sandbox create --name hello
openshell sandbox delete hello
```

OpenShell is alpha software. Note the installed version in `FEEDBACK.md`.

## 3. The app

```bash
sudo useradd -r -m -d /opt/warrant warrant
sudo -u warrant git clone <this repository> /opt/warrant
cd /opt/warrant && sudo -u warrant uv sync
cp .env.example .env    # fill in NEBIUS_API_KEY and a random WARRANT_ADMIN_TOKEN
# set WARRANT_PORTAL_URL to the portal's public https URL and WARRANT_ENFORCER=openshell
sudo cp deploy/*.service /etc/systemd/system/ && sudo systemctl daemon-reload
sudo systemctl enable --now warrant warrant-portal
sudo cp deploy/Caddyfile /etc/caddy/Caddyfile   # edit the hostnames first
sudo systemctl reload caddy
```

Generate the admin token with `python3 -c "import secrets; print(secrets.token_urlsafe(32))"`. Keep it in a
password manager, never in the repository or the video.

## 4. The deciding check

Draft and approve a warrant in the interface, then on the host:

```bash
uv run warrant policy <warrant-id>                 # the policy OpenShell will receive
uv run warrant openshell-check <warrant-id> --keep # create a sandbox with it
```

Inside that sandbox, confirm:

| Test | Expected |
|---|---|
| GET an allowed portal path | succeeds |
| POST to the same host | denied |
| GET any host not in the warrant | denied |
| `openshell logs <name> --source sandbox` | shows the denied requests |

Record each result in `FEEDBACK.md`. Then delete the sandbox with `openshell sandbox delete <name>`.

## 5. Hermes Agent inside OpenShell

The OpenShell documentation lists Hermes Agent as supported through NVIDIA NemoClaw. Follow the NemoClaw
instructions for the Hermes blueprint, point Hermes at Nebius Token Factory as an OpenAI-compatible
provider (`https://api.tokenfactory.nebius.com/v1`, model `nvidia/nemotron-3-super-120b-a12b`), and run a
one-shot mission with `hermes -z "<mission>"` inside a sandbox created from a warrant policy.
