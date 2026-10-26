import { AnimatePresence, motion, MotionConfig } from 'motion/react'
import { StrictMode, useCallback, useEffect, useState } from 'react'
import { createRoot } from 'react-dom/client'
import { api, Status, token } from './api'
import { Catalogue, Evidence } from './Catalogue'
import { Missions } from './Missions'
import { RunView } from './RunView'
import './styles.css'

type View = 'missions' | 'run' | 'sites' | 'evidence'
const NAV: [View, string][] = [['missions', 'Missions'], ['sites', 'Reviewed sites'], ['evidence', 'Evidence']]

function readHash(): { view: View; run?: string } {
  const h = location.hash.slice(1)
  if (h.startsWith('run-')) return { view: 'run', run: h.slice(4) }
  return { view: (['missions', 'sites', 'evidence'].includes(h) ? h : 'missions') as View }
}

function App() {
  const [route, setRoute] = useState(readHash)
  const [status, setStatus] = useState<Status | null>(null)
  const [toast, setToast] = useState('')
  const [askToken, setAskToken] = useState(false)

  useEffect(() => {
    const on = () => { setRoute(readHash()); window.scrollTo({ top: 0 }) }
    addEventListener('hashchange', on)
    return () => removeEventListener('hashchange', on)
  }, [])
  useEffect(() => { api.status().then(setStatus).catch(() => setStatus(null)) }, [route.view])

  const go = (view: View, run?: string) => { location.hash = run ? `run-${run}` : view }
  const notify = useCallback((msg: string) => {
    setToast(msg)
    if (/token/i.test(msg)) setAskToken(true)
    setTimeout(() => setToast(t => (t === msg ? '' : t)), 4200)
  }, [])

  return (
    <MotionConfig reducedMotion="user">
      <header className="top">
        <div className="top-in">
          <a className="word" href="#missions">WARRANT</a>
          <nav aria-label="Sections">
            {NAV.map(([v, label]) => (
              <a key={v} href={`#${v}`} className={route.view === v || (v === 'missions' && route.view === 'run') ? 'on' : ''}>
                {label}
                {(route.view === v || (v === 'missions' && route.view === 'run')) && <motion.i layoutId="nav-mark" className="nav-mark" />}
              </a>
            ))}
          </nav>
          <div className="sys mono">
            {status ? <>
              <span className={`dot ${status.live_model ? 'ok' : ''}`} />
              <span>{status.live_model ? 'Nemotron live' : 'Model offline'}</span>
              <span className="sep" />
              <span>{status.enforcer === 'openshell' ? 'OpenShell enforcing' : 'Local enforcer'}</span>
            </> : <span>Connecting…</span>}
            {status?.auth_required && (
              <button className="link" onClick={() => setAskToken(true)}>{token.get() ? 'Owner' : 'Sign in'}</button>
            )}
          </div>
        </div>
      </header>

      <main className="shell">
        <AnimatePresence mode="wait">
          <motion.div key={route.view + (route.run ?? '')} initial={{ opacity: 0 }} animate={{ opacity: 1 }}
            exit={{ opacity: 0 }} transition={{ duration: 0.15 }}>
            {route.view === 'missions' && <Missions onOpenRun={id => go('run', id)} notify={notify} />}
            {route.view === 'run' && route.run && <RunView runId={route.run} onBack={() => go('missions')} />}
            {route.view === 'sites' && <Catalogue />}
            {route.view === 'evidence' && <Evidence />}
          </motion.div>
        </AnimatePresence>
      </main>

      <footer className="foot mono">
        <span>Planner {status?.planner_model ?? '…'} · agent {status?.agent_model ?? '…'} · {status?.provider ?? 'Nebius Token Factory'}</span>
        <span>Fictional demo portal. No real accounts.</span>
      </footer>

      <AnimatePresence>
        {toast && (
          <motion.div className="toast" role="status" initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: 12 }}>
            {toast}
          </motion.div>
        )}
      </AnimatePresence>
      <AnimatePresence>{askToken && <TokenDialog close={() => setAskToken(false)} />}</AnimatePresence>
    </MotionConfig>
  )
}

function TokenDialog({ close }: { close: () => void }) {
  const [value, setValue] = useState(token.get())
  return (
    <motion.div className="scrim" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}
      onMouseDown={e => e.target === e.currentTarget && close()}>
      <motion.form className="dialog" role="dialog" aria-modal="true" aria-labelledby="tok-h"
        initial={{ y: 12, opacity: 0 }} animate={{ y: 0, opacity: 1 }}
        onSubmit={e => { e.preventDefault(); token.set(value.trim()); close() }}>
        <h2 id="tok-h">Owner sign-in</h2>
        <p>Drafting, approving and running missions needs the owner token set on the server. It stays in this tab only.</p>
        <label htmlFor="tok" className="eyebrow">Owner token</label>
        <input id="tok" type="password" autoComplete="off" value={value} onChange={e => setValue(e.target.value)} />
        <div className="row"><button className="btn" disabled={value.trim().length < 16}>Sign in</button>
          <button type="button" className="btn ghost" onClick={close}>Cancel</button></div>
      </motion.form>
    </motion.div>
  )
}

createRoot(document.getElementById('root')!).render(<StrictMode><App /></StrictMode>)
