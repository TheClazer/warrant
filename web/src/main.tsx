import { AnimatePresence, motion, MotionConfig } from 'motion/react'
import { StrictMode, useCallback, useEffect, useState } from 'react'
import { createRoot } from 'react-dom/client'
import { api, Status, token } from './api'
import { Landing } from './Landing'
import './styles.css'
import { UseIt } from './UseIt'
import { Evidence, Missions, RunPage, Sites } from './Workspace'

type Route = { view: 'landing' | 'app' | 'run' | 'sites' | 'evidence' | 'use'; run?: string }

function readHash(): Route {
  const h = location.hash.replace(/^#\/?/, '')
  if (h.startsWith('run/')) return { view: 'run', run: h.slice(4) }
  if (h === 'app' || h === 'missions') return { view: 'app' }
  if (h === 'sites') return { view: 'sites' }
  if (h === 'evidence') return { view: 'evidence' }
  if (h === 'use') return { view: 'use' }
  return { view: 'landing' }
}

const NAV: [Route['view'], string, string][] = [
  ['app', 'Try it', '#/app'],
  ['use', 'Use it yourself', '#/use'],
  ['sites', 'Reviewed sites', '#/sites'],
  ['evidence', 'Evidence', '#/evidence'],
]

function App() {
  const [route, setRoute] = useState(readHash)
  useEffect(() => {
    const on = () => {
      const next = readHash()
      setRoute(next)
      if (location.hash === '' || location.hash.startsWith('#/')) window.scrollTo({ top: 0 })
    }
    addEventListener('hashchange', on)
    return () => removeEventListener('hashchange', on)
  }, [])
  return (
    <MotionConfig reducedMotion="user">
      {route.view === 'landing' ? <Landing /> : <Shell route={route} />}
    </MotionConfig>
  )
}

function Shell({ route }: { route: Route }) {
  const [status, setStatus] = useState<Status | null>(null)
  const [slow, setSlow] = useState(false)
  const [toast, setToast] = useState('')
  const [askToken, setAskToken] = useState(false)

  useEffect(() => {
    const timer = setTimeout(() => setSlow(true), 3000)
    api.status().then(setStatus).catch(() => setStatus(null)).finally(() => { clearTimeout(timer); setSlow(false) })
    return () => clearTimeout(timer)
  }, [route.view])

  const notify = useCallback((msg: string) => {
    setToast(msg)
    if (/token/i.test(msg)) setAskToken(true)
    setTimeout(() => setToast(t => (t === msg ? '' : t)), 4500)
  }, [])
  const active = route.view === 'run' ? 'app' : route.view

  return (
    <div className="shell">
      <aside className="side">
        <a className="mark" href="#/">WARRANT</a>
        <nav aria-label="Workspace">
          {NAV.map(([v, label, href]) => (
            <a key={v} href={href} className={active === v ? 'on' : ''} aria-current={active === v ? 'page' : undefined}>
              {active === v && <motion.i layoutId="side-mark" />}{label}
            </a>
          ))}
        </nav>
        <dl className="side-sys">
          <div><dt>Model</dt><dd><span className={`dot ${status?.live_model ? 'live' : ''}`} />{status ? (status.live_model ? 'Nemotron 3 Super' : 'Offline') : 'Connecting…'}</dd></div>
          <div><dt>Enforcer</dt><dd>{status ? (status.enforcer === 'openshell' ? 'NVIDIA OpenShell' : 'Built-in') : '…'}</dd></div>
          <div><dt>Portal</dt><dd>Fictional demo</dd></div>
        </dl>
        {status?.auth_required && <button className="text-btn on-dark" onClick={() => setAskToken(true)}>{token.get() ? 'Owner signed in' : 'Owner sign-in'}</button>}
      </aside>
      <main className="main">
        {slow && !status && <p className="waking mono">Waking the demo server. This can take up to a minute on the free plan.</p>}
        <div key={route.view + (route.run ?? '')} className="enter">
          {route.view === 'app' && <Missions notify={notify} />}
          {route.view === 'run' && route.run && <RunPage runId={route.run} portal={status?.portal_url} />}
          {route.view === 'sites' && <Sites />}
          {route.view === 'evidence' && <Evidence />}
          {route.view === 'use' && <UseIt />}
        </div>
      </main>
      <AnimatePresence>
        {toast && <motion.div className="toast" role="status" initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0 }}>{toast}</motion.div>}
      </AnimatePresence>
      <AnimatePresence>{askToken && <TokenDialog close={() => setAskToken(false)} />}</AnimatePresence>
    </div>
  )
}

function TokenDialog({ close }: { close: () => void }) {
  const [value, setValue] = useState(token.get())
  return (
    <motion.div className="scrim" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}
      onMouseDown={e => e.target === e.currentTarget && close()}>
      <form className="dialog" role="dialog" aria-modal="true" aria-labelledby="tok-h"
        onSubmit={e => { e.preventDefault(); token.set(value.trim()); close() }}>
        <h2 id="tok-h">Owner sign-in</h2>
        <p>Drafting, approving and running need the owner token set on the server. It stays in this tab.</p>
        <label htmlFor="tok" className="label">Owner token</label>
        <input id="tok" type="password" autoComplete="off" value={value} onChange={e => setValue(e.target.value)} />
        <div className="row">
          <button className="btn" disabled={value.trim().length < 16}>Sign in</button>
          <button type="button" className="btn ghost" onClick={close}>Cancel</button>
        </div>
      </form>
    </motion.div>
  )
}

createRoot(document.getElementById('root')!).render(<StrictMode><App /></StrictMode>)
