import { useEffect, useState } from 'react'
import { api, EvalSummary } from './api'
import { Preview } from './Preview'
import GradientASCII from './rb/GradientASCII.jsx'
import TechText from './rb/TechText.jsx'
import { Reveal } from './ui'

const REPO = 'https://github.com/TheClazer/warrant'

const STEPS = [
  { n: '01', title: 'Nemotron drafts the minimum', body: 'It reads your mission and picks only what the job needs from a reviewed list. It cannot invent a website or widen a path.' },
  { n: '02', title: 'You read it and decide', body: 'Plain sentences, no YAML. Remove anything you dislike. Missions that post or submit ask you again on every run.' },
  { n: '03', title: 'The sandbox holds the line', body: 'Each run gets a fresh NVIDIA OpenShell sandbox built from your warrant. If the agent reaches further, the request never leaves.' },
]

const LOG = [
  ['ALLOWED', 'GET https://example.com/', 'policy:example_read_home'],
  ['DENIED', 'POST https://example.com/', 'POST / not permitted by policy'],
  ['DENIED', 'GET https://example.com/other', 'GET /other not permitted by policy'],
  ['DENIED', 'www.iana.org', 'policy_dns_ineligible'],
]

export function Landing() {
  const [evalData, setEval] = useState<EvalSummary | null>(null)
  useEffect(() => { api.evalSummary().then(setEval).catch(() => setEval({ available: false })) }, [])
  const setups = evalData?.available ? evalData.setups : null

  return (
    <div className="landing">
      <header className="hero">
        <div className="hero-bg" aria-hidden="true">
          <GradientASCII colors={['#6b4e00', '#FFC629', '#FFE08A', '#FFF6D8']} shape="horizon" cellSize={13} density={0.75}
            glyphOpacity={0.8} gradientOpacity={0.55} glow={0.15} flicker={0.15} flow={0.4} speed={0.6} grain={0.05}
            dpr={1} fontFamily='"Martian Mono", ui-monospace, monospace' clickEffect="wave" />
        </div>
        <nav className="lnav wrap" aria-label="Main">
          <a className="mark" href="#/">WARRANT</a>
          <div className="lnav-links mono">
            <a href="#how" onClick={jump('how')}>How it works</a>
            <a href="#proof" onClick={jump('proof')}>Evidence</a>
            <a href={REPO} target="_blank" rel="noreferrer">GitHub</a>
          </div>
          <a className="btn signal" href="#/app">Open the app</a>
        </nav>
        <div className="hero-copy wrap">
          <div className="hero-word">
            <TechText text="WARRANT" fontFamily="Archivo" fontWeight={800} fontSize={210} letterSpacing={-0.02} align="left"
              color="#EEEFEA" accentColor="#FFC629" reveal="letter" dashLength={5} dashGap={3} specks={10}
              speed={0.7} />
          </div>
          <div className="hero-row">
            <h1>Give your AI agent a warrant, not your keys.</h1>
            <div>
              <p>Before each job, the agent gets a short list of exactly what it may touch. You approve it. NVIDIA OpenShell enforces it. Everything else is blocked and shown to you.</p>
              <div className="row">
                <a className="btn signal" href="#/app">Try the live demo</a>
                <a className="btn ghost-dark" href={REPO} target="_blank" rel="noreferrer">Read the code</a>
              </div>
            </div>
          </div>
        </div>
        <div className="wrap hero-preview"><Preview /></div>
      </header>

      <section id="how" className="wrap sec">
        <Reveal>
          <span className="label">How it works</span>
          <h2>Three steps, and the last one isn't up to the AI.</h2>
          <div className="steps">
            {STEPS.map(s => (
              <article key={s.n}>
                <span className="step-n">{s.n}</span>
                <h3>{s.title}</h3>
                <p>{s.body}</p>
              </article>
            ))}
          </div>
        </Reveal>
      </section>

      <section id="proof" className="band">
        <div className="wrap sec">
          <Reveal>
            <span className="label">Evidence</span>
            <h2>We asked agents to overreach, then counted.</h2>
            <p className="lede">Five missions that ask for more than their approved warrant, run twice each, with real Nemotron calls on a fictional course portal.</p>
            <div className="compare">
              <div>
                <span className="label">Broad access</span>
                <div className="big">{setups ? <>{setups.broad.outside_requests_that_went_through}<small> of {setups.broad.outside_requests_attempted}</small></> : '—'}</div>
                <p>off-warrant requests went through</p>
                <div className="bar"><i style={{ width: '100%' }} /></div>
              </div>
              <div className="hot">
                <span className="label">Under a warrant</span>
                <div className="big">{setups ? <>{setups.warrant.outside_requests_that_went_through}<small> of {setups.warrant.outside_requests_attempted}</small></> : '—'}</div>
                <p>off-warrant requests went through</p>
                <div className="bar"><i style={{ width: '0%' }} /></div>
              </div>
            </div>
            <p className="note">These runs used Warrant's built-in enforcer. The expected fact appeared in 3 of 10 answers in both setups, so agent accuracy still has room to grow. <a href="#/evidence">Full table</a></p>
          </Reveal>
        </div>
      </section>

      <section className="wrap sec split">
        <Reveal>
          <span className="label">Enforced by NVIDIA OpenShell</span>
          <h2>Not a promise from the model. A decision in the log.</h2>
          <p className="lede">Decisions from a real OpenShell 0.1.5 run, condensed from its log, enforcing a policy Warrant generated: one page allowed, everything else denied, each with a reason.</p>
        </Reveal>
        <Reveal className="log">
          <div className="log-h mono"><i />OpenShell decision log</div>
          {LOG.map(([d, target, why]) => (
            <div key={target} className={`log-row ${d === 'DENIED' ? 'deny' : ''}`}>
              <b>{d}</b><span>{target}</span><small>{why}</small>
            </div>
          ))}
        </Reveal>
      </section>

      <section className="wrap stack">
        <span className="label">Built with</span>
        <ul>
          <li><b>NVIDIA Nemotron 3 Super</b><small>Drafts warrants, drives the agent</small></li>
          <li><b>Nebius Token Factory</b><small>Serves every model call</small></li>
          <li><b>NVIDIA OpenShell</b><small>Enforces each warrant</small></li>
        </ul>
      </section>

      <section className="closer">
        <div className="wrap closer-in">
          <h2>Draft a warrant. Remove a permission. Watch the block.</h2>
          <a className="btn signal" href="#/app">Open the app</a>
        </div>
      </section>

      <footer className="wrap lfoot mono">
        <span>Demo portal is fictional. No real accounts.</span>
        <span>The public demo uses the built-in enforcer; OpenShell needs its own Docker host.</span>
        <a href={REPO} target="_blank" rel="noreferrer">Apache-2.0</a>
      </footer>
    </div>
  )
}

function jump(id: string) {
  return (e: React.MouseEvent) => {
    e.preventDefault()
    document.getElementById(id)?.scrollIntoView({ behavior: 'smooth' })
  }
}
