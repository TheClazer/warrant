import { useState } from 'react'
import { GuardFlow, Terminal } from './Terminal'

const REPO = 'https://github.com/TheClazer/warrant'

const TRY = `uvx --from git+https://github.com/TheClazer/warrant warrant try`
const TRY_OWN = `uvx --from git+https://github.com/TheClazer/warrant warrant try "Find every exam in my courses this week"`
const GUARD = `uv tool install git+https://github.com/TheClazer/warrant
warrant guard --allow api.example.com -- python my_agent.py`
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
WARRANT_ENFORCER=openshell uv run warrant try`

function Code({ text }: { text: string }) {
  const [copied, setCopied] = useState(false)
  const copy = async () => {
    try {
      await navigator.clipboard.writeText(text)
      setCopied(true)
      setTimeout(() => setCopied(false), 1500)
    } catch { /* clipboard blocked: the text can still be selected */ }
  }
  return (
    <div className="code">
      <button onClick={copy}>{copied ? 'Copied' : 'Copy'}</button>
      <pre>{text}</pre>
    </div>
  )
}

export function UseIt() {
  return (
    <div className="page use">
      <h1>Use it on your own machine</h1>
      <p className="lede">Warrant runs in your terminal. Try the full flow in one command, or put a limit on a script you already have.</p>

      <div className="use-term"><Terminal /></div>

      <section className="use-step">
        <span className="step-n">01</span>
        <div>
          <h2>Try the whole flow</h2>
          <p>Starts a fictional portal on your machine, asks Nemotron what the job needs, lets you remove permissions, then runs the agent and shows what got blocked. Needs <a href="https://docs.astral.sh/uv/" target="_blank" rel="noreferrer">uv</a> and a Nebius Token Factory key, which it asks for and doesn't save.</p>
          <Code text={TRY} />
          <p>Give it your own job on the same portal:</p>
          <Code text={TRY_OWN} />
        </div>
      </section>

      <section className="use-step">
        <span className="step-n">02</span>
        <div>
          <h2>Guard a script you already have</h2>
          <p>No AI needed. Your program runs as normal, and its web traffic can only reach the hosts you list. Each request shows up as allowed or blocked. Works with programs that respect the standard proxy settings, including curl and most HTTP libraries.</p>
          <GuardFlow />
          <Code text={GUARD} />
        </div>
      </section>

      <section className="use-step">
        <span className="step-n">03</span>
        <div>
          <h2>Add a site you use</h2>
          <p>List what an agent may ever do on it. Nemotron can only pick from this list, so it can't invent a site or a broader path. Then <code>warrant try</code> or <code>warrant serve</code> can use it.</p>
          <Code text={SITE} />
        </div>
      </section>

      <section className="use-step">
        <span className="step-n">04</span>
        <div>
          <h2>Make it unskippable with NVIDIA OpenShell</h2>
          <p>Each run gets a fresh sandbox built from its warrant, so the agent can't opt out and rules apply per path and method.</p>
          <Code text={OPENSHELL} />
        </div>
      </section>

      <section className="limits">
        <h2>What it can't do yet</h2>
        <ul>
          <li>The agent has no login handling, so it can't sign in to your real accounts yet.</li>
          <li><code>warrant guard</code> is cooperative: a program can ignore proxy settings. For HTTPS it limits hosts, not individual pages. OpenShell has neither gap.</li>
          <li>OpenShell enforcement has been tested with Warrant's own agent and with curl, not yet with other agents such as Hermes.</li>
          <li>A warrant limits where requests can go. It doesn't stop a page from misleading the agent's answer.</li>
        </ul>
      </section>
    </div>
  )
}
