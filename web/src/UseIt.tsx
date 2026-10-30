import { GuardFlow, Terminal } from './Terminal'
import { Code } from './ui'

const REPO = 'https://github.com/TheClazer/warrant'

const PROVE = `uvx --from git+https://github.com/TheClazer/warrant warrant prove`
const TEST = `git clone https://github.com/TheClazer/warrant && cd warrant
uv run pytest tests/test_prove.py -v`
const TRY = `uvx --from git+https://github.com/TheClazer/warrant warrant try`
const TRY_OWN = `uvx --from git+https://github.com/TheClazer/warrant warrant try "Find every exam in my courses this week"`
const GUARD = `uv tool install git+https://github.com/TheClazer/warrant
warrant guard --allow api.example.com -- python my_agent.py`
const INSTALL = `pip install git+https://github.com/TheClazer/warrant   # Python 3.11 or 3.12`
const IMPORT = `import httpx
from warrant import guard

with guard(allow=["example.com"]) as report:
    httpx.get("https://example.com/")          # goes through
    httpx.get("https://www.iana.org/")         # raises httpx.ProxyError

print(report.blocked)`
const SITE = `git clone ${REPO} && cd warrant

# src/warrant/sites.py: add your site to build_registry()
Site(
    id="wiki",
    name="Team wiki",
    base_url="https://wiki.example.com",
    capabilities=(
        _cap("wiki", "https://wiki.example.com", "wiki.read.pages",
             "Read wiki pages", "Read pages on the team wiki",
             ("GET",), ("/pages", "/pages/**")),
    ),
)`
const OPENSHELL = `# Linux or WSL 2, with Docker Engine and NVIDIA OpenShell installed
docker build -t warrant-sandbox:dev -f deploy/sandbox.Dockerfile deploy
WARRANT_ENFORCER=openshell uvx --from git+https://github.com/TheClazer/warrant warrant try`

export function UseIt() {
  return (
    <div className="page use">
      <h1>Use it on your own machine</h1>
      <p className="lede">Warrant runs in your terminal and from Python. Everything below can be copied and run. Only the app on this website runs on our server.</p>

      <div className="use-term"><Terminal /></div>

      <section className="use-step">
        <span className="step-n">01</span>
        <div>
          <h2>See the difference first</h2>
          <p>A scripted agent tries to read your grades, submit your lab and send your data to a stranger, once with broad access and once under a warrant. The result is read from the portal and the stranger's server, not from the agent. No AI or key needed, and nothing leaves your machine. It uses Warrant's built-in enforcer.</p>
          <Code text={PROVE} />
          <p>Or read and run the test yourself:</p>
          <Code text={TEST} />
        </div>
      </section>

      <section className="use-step">
        <span className="step-n">02</span>
        <div>
          <h2>Try the whole flow</h2>
          <p>Starts a fictional portal on your machine, asks Nemotron what the job needs, lets you remove permissions, then runs the agent and shows what got blocked. Needs <a href="https://docs.astral.sh/uv/" target="_blank" rel="noreferrer">uv</a> and a Nebius Token Factory key, which it asks for and doesn't save.</p>
          <Code text={TRY} />
          <p>Give it your own job on the same portal:</p>
          <Code text={TRY_OWN} />
        </div>
      </section>

      <section className="use-step">
        <span className="step-n">03</span>
        <div>
          <h2>Guard a script you already have</h2>
          <p>No AI needed. Your program runs as normal, and its web traffic can only reach the hosts you list. Each request shows up as allowed or blocked. Works with programs that respect the standard proxy settings, including curl and most HTTP libraries.</p>
          <GuardFlow />
          <Code text={GUARD} />
          <p>Or import it and wrap the part of your Python code that should be limited. Covers clients created inside the block, such as httpx and requests.</p>
          <Code text={INSTALL} />
          <Code text={IMPORT} />
        </div>
      </section>

      <section className="use-step">
        <span className="step-n">04</span>
        <div>
          <h2>Add a site you use</h2>
          <p>List what an agent may ever do on it. Nemotron can only pick from this list, so it can't invent a site or a broader path. Then <code>warrant try</code> or <code>warrant serve</code> can use it.</p>
          <Code text={SITE} />
        </div>
      </section>

      <section className="use-step">
        <span className="step-n">05</span>
        <div>
          <h2>Make it unskippable with NVIDIA OpenShell</h2>
          <p>Each run gets a fresh sandbox built from its warrant, so the agent can't opt out and rules apply per path and method. This is the only part that needs OpenShell, and it runs on your machine, not on this website.</p>
          <Code text={OPENSHELL} />
        </div>
      </section>

      <section className="limits">
        <h2>What it can't do yet</h2>
        <ul>
          <li>The app on this website uses Warrant's built-in enforcer on our server, because OpenShell needs its own Docker host. Its portal is fictional.</li>
          <li>The agent has no login handling, so it can't sign in to your real accounts yet.</li>
          <li><code>warrant guard</code> is cooperative: a program can ignore proxy settings. For HTTPS it limits hosts, not individual pages. OpenShell has neither gap.</li>
          <li>OpenShell enforcement has been tested with Warrant's own agent and with curl, not yet with other agents such as Hermes.</li>
          <li>A warrant limits where requests can go. It doesn't stop a page from misleading the agent's answer.</li>
        </ul>
      </section>
    </div>
  )
}
