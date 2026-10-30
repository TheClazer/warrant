import { useEffect, useState } from 'react'
import { api, EvalSummary } from './api'
import { Playground } from './Playground'
import ClickSpark from './rb/ClickSpark.jsx'
import DecryptedText from './rb/DecryptedText.jsx'
import GradientASCII from './rb/GradientASCII.jsx'
import LogoLoop from './rb/LogoLoop.jsx'
import Magnet from './rb/Magnet.jsx'
import RotatingText from './rb/RotatingText.jsx'
import SpotlightCard from './rb/SpotlightCard.jsx'
import TechText from './rb/TechText.jsx'
import { Scenes } from './Scenes'
import { Terminal } from './Terminal'
import { Code, Reveal } from './ui'

const REPO = 'https://github.com/TheClazer/warrant'

const STEPS = [
  { n: '01', title: 'Nemotron drafts the minimum', body: 'It reads your mission and picks only what the job needs from a reviewed list. It cannot invent a website or widen a path.' },
  { n: '02', title: 'You read it and decide', body: 'Plain sentences, no YAML. Remove anything you dislike. Missions that post or submit ask you again on every run.' },
  { n: '03', title: 'Code holds the line, not the AI', body: 'Every request is checked against your warrant before it is sent. On your machine, NVIDIA OpenShell does this in a fresh sandbox. This website uses the built-in enforcer.' },
]

const LOG = [
  ['ALLOWED', 'GET https://example.com/', 'policy:example_read_home'],
  ['DENIED', 'POST https://example.com/', 'POST / not permitted by policy'],
  ['DENIED', 'GET https://example.com/other', 'GET /other not permitted by policy'],
  ['DENIED', 'www.iana.org', 'policy_dns_ineligible'],
]

const STRIP = [
  ['ALLOWED', 'GET /announcements'], ['BLOCKED', 'GET /grades'], ['BLOCKED', 'POST /forum/t1/reply'],
  ['ALLOWED', 'GET /assignments'], ['BLOCKED', 'www.iana.org'], ['BLOCKED', 'POST /assignments/cs301-lab4/submit'],
].map(([d, r]) => ({
  title: `${d} ${r}`,
  node: <span className={`strip-item ${d === 'BLOCKED' ? 'bad' : ''}`}><b>{d}</b> {r}</span>,
}))

export function Landing() {
  const [evalData, setEval] = useState<EvalSummary | null>(null)
  useEffect(() => { api.evalSummary().then(setEval).catch(() => setEval({ available: false })) }, [])
  const setups = evalData?.available ? evalData.setups : null

  return (
    <div className="landing">
      <ClickSpark sparkColor="#FFC629" sparkSize={12} sparkRadius={26} sparkCount={9} duration={450}>
      <header className="hero">
        <div className="hero-bg" aria-hidden="true">
          <GradientASCII colors={['#2a1f00', '#7a5600', '#D79E10', '#FFC629']} shape="horizon" cellSize={12} density={0.85}
            glyphOpacity={0.8} gradientOpacity={0.6} glow={0.35} flicker={0.2} flow={0.55} speed={0.8} grain={0.05}
            intro={false} dpr={1} fontFamily='"Martian Mono", ui-monospace, monospace' clickEffect="wave" />
        </div>
        <nav className="lnav wrap" aria-label="Main">
          <a className="mark" href="#/">WARRANT</a>
          <div className="lnav-links mono">
            <a href="#examples" onClick={jump('examples')}>Examples</a>
            <a href="#try" onClick={jump('try')}>Try it</a>
            <a href="#how" onClick={jump('how')}>How it works</a>
            <a href="#proof" onClick={jump('proof')}>Evidence</a>
            <a href="#/use">Use it yourself</a>
            <a href={REPO} target="_blank" rel="noreferrer">GitHub</a>
          </div>
          <a className="btn signal" href="#/app">Open the app</a>
        </nav>
        <div className="hero-copy wrap">
          <p className="eyebrow mono">
            <DecryptedText text="Permissions for personal AI agents" animateOn="view" sequential speed={28} characters="#@%&*+=/<>01" />
          </p>
          <div className="hero-word">
            <TechText text="WARRANT" fontFamily="Archivo" fontWeight={800} fontSize={210} letterSpacing={-0.02} align="left"
              color="#EEEFEA" accentColor="#FFC629" reveal="letter" dashLength={5} dashGap={3} specks={10}
              speed={0.7} />
          </div>
          <div className="hero-row">
            <h1>Give your AI agent a warrant, <span className="nowrap">not your{' '}
              <RotatingText texts={['keys.', 'passwords.', 'inbox.', 'wallet.']} rotationInterval={2200} mainClassName="rotator"
                staggerDuration={0.015} staggerFrom="last" splitBy="characters" /></span>
            </h1>
            <div>
              <p>Before each job, your AI agent gets a short list of what it may touch. You approve it. Anything else gets blocked, and you see it happen.</p>
              <div className="row">
                <Magnet padding={70} magnetStrength={4}><a className="btn signal big-btn" href="#/app">Try the live demo</a></Magnet>
                <a className="btn ghost-dark big-btn" href="#try" onClick={jump('try')}>Try to break it</a>
              </div>
            </div>
          </div>
        </div>
        <div className="strip" aria-hidden="true">
          <LogoLoop logos={STRIP} speed={46} gap={44} logoHeight={13} pauseOnHover={false} fadeOut={false} />
        </div>
      </header>

      <section id="examples" className="wrap sec examples">
        <span className="label">How it helps</span>
        <h2>Four ways an agent goes too far, and what happens instead.</h2>
        <Scenes />
      </section>

      <section id="try" className="wrap sec try">
        <Reveal>
          <span className="label">Try it here</span>
          <h2>You hold the warrant. Now try to get past it.</h2>
          <Playground />
        </Reveal>
      </section>

      <section className="band-dark">
        <div className="wrap sec local">
          <Reveal>
            <span className="label on-dark">On your own machine</span>
            <h2>Don't take our word for it. Run the attack yourself.</h2>
            <p className="lede on-dark">One command sends a misbehaving agent after your grades, with and without a warrant. No AI or key needed, and nothing leaves your machine.</p>
            <div className="oneliner"><Code text="uvx --from git+https://github.com/TheClazer/warrant warrant prove" /></div>
            <a className="btn signal" href="#/use">See every command</a>
          </Reveal>
          <Reveal><Terminal /></Reveal>
        </div>
      </section>

      <section id="how" className="wrap sec">
        <Reveal>
          <span className="label">How it works</span>
          <h2>Three steps, and the last one isn't up to the AI.</h2>
          <div className="steps">
            {STEPS.map(s => (
              <SpotlightCard key={s.n} className="step" theme="light" spotlightColor="rgba(255, 198, 41, 0.45)" intensity={0.5} spotlightSize={280}>
                <span className="step-n">{s.n}</span>
                <h3>{s.title}</h3>
                <p>{s.body}</p>
              </SpotlightCard>
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
      </ClickSpark>
    </div>
  )
}

function jump(id: string) {
  return (e: React.MouseEvent) => {
    e.preventDefault()
    document.getElementById(id)?.scrollIntoView({ behavior: 'smooth' })
  }
}
