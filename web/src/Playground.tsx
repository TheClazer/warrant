import { useRef, useState } from 'react'
import CallChip from './rb/CallChip.jsx'
import StarBorder from './rb/StarBorder.jsx'

type Grant = 'announcements' | 'grades' | 'forum'
type Attempt = { label: string; method: string; path: string; needs: Grant | null }
type Entry = { id: number; attempt: Attempt; state: 'running' | 'done' | 'error' }

const GRANTS: { id: Grant; text: string }[] = [
  { id: 'announcements', text: 'Read announcements' },
  { id: 'grades', text: 'Read your grades' },
  { id: 'forum', text: 'Reply on the course forum' },
]
const ATTEMPTS: Attempt[] = [
  { label: 'Check the announcements', method: 'GET', path: '/announcements', needs: 'announcements' },
  { label: 'Peek at your grades', method: 'GET', path: '/grades', needs: 'grades' },
  { label: 'Post a forum reply as you', method: 'POST', path: '/forum/t1/reply', needs: 'forum' },
  { label: 'Upload your data to a stranger', method: 'POST', path: 'paste.example/upload', needs: null },
]
const CHIP = {
  icon: 'terminal', size: 32, radius: 3, surfaceColor: '#fff', color: '#141518', progressColor: '#141518',
  doneColor: '#1F7A4D', errorColor: '#B27700', showTimer: false, expectedMs: 420,
}

/** A browser-only taste of the rule check: flip permissions, then make the agent reach. */
export function Playground() {
  const [grants, setGrants] = useState<Record<Grant, boolean>>({ announcements: true, grades: false, forum: false })
  const [log, setLog] = useState<Entry[]>([])
  const nextId = useRef(0)

  const attempt = (a: Attempt) => {
    const id = nextId.current++
    const allowed = a.needs !== null && grants[a.needs]
    setLog(l => [{ id, attempt: a, state: 'running' as const }, ...l].slice(0, 5))
    setTimeout(() => setLog(l => l.map(e => (e.id === id ? { ...e, state: allowed ? 'done' : 'error' } : e))), 420)
  }
  const blocked = log.filter(e => e.state === 'error').length

  return (
    <div className="play">
      <div className="play-col">
        <span className="label">1. Your warrant</span>
        <h3>What may it touch?</h3>
        <ul>
          {GRANTS.map(g => (
            <li key={g.id}>
              <button className={`switch ${grants[g.id] ? 'on' : ''}`} role="switch" aria-checked={grants[g.id]}
                onClick={() => setGrants(s => ({ ...s, [g.id]: !s[g.id] }))}>
                <i /><span>{g.text}</span>
              </button>
            </li>
          ))}
        </ul>
        <p className="play-fixed">Every other website: <b>never</b></p>
      </div>
      <div className="play-col">
        <span className="label">2. The agent tries</span>
        <h3>Make it reach.</h3>
        <div className="reach">
          {ATTEMPTS.map(a => (
            <button key={a.path} onClick={() => attempt(a)}>
              {a.label}<code>{a.method} {a.path}</code>
            </button>
          ))}
        </div>
      </div>
      <div className="play-col feed-side">
        <span className="label">3. What happened{log.length > 0 && ` · ${blocked} blocked`}</span>
        <ol className="play-log" aria-live="polite">
          {log.length === 0 && <li className="play-empty">Press one of the buttons.</li>}
          {log.map(e => (
            <li key={e.id} className={`enter ${e.state === 'error' ? 'bad' : ''}`}>
              <CallChip {...CHIP} name={e.attempt.method} argument={e.attempt.path} status={e.state} />
              {e.state === 'error' && <small>Blocked. Not in this warrant.</small>}
              {e.state === 'done' && <small>Allowed by your warrant.</small>}
            </li>
          ))}
        </ol>
        <StarBorder as="a" href="#/app" className="play-cta" theme="light" color="#FFC629" radius={0} thickness={2} duration={3} backgroundColor="#141518" textColor="#EEEFEA" borderColor="#141518">
          Now run it with the real agent →
        </StarBorder>
        <p className="play-note mono">This box is a simulation in your browser. The app runs real Nemotron calls.</p>
      </div>
    </div>
  )
}
