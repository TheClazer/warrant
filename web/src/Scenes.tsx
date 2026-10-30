import { useInView, useReducedMotion } from 'motion/react'
import { useEffect, useLayoutEffect, useRef, useState } from 'react'

type Event = { at: number; ok: boolean; target: string }
type Step = { at: number; to: string; click?: boolean }
type Scene = {
  title: string
  length: number
  job: string
  grants?: { text: string; id: string; cut?: number; tag?: string }[]
  ask?: { at: number; done: number }
  approveAt?: number
  command?: string
  events: Event[]
  steps: Step[]
  without: string
  withIt: string
}

const SCENES: Scene[] = [
  {
    title: 'It reads more than the job needs',
    length: 10,
    job: 'Brief me on announcements and my latest grades.',
    grants: [
      { id: 'a', text: 'Read announcements' },
      { id: 'g', text: 'Read your grades', cut: 3 },
    ],
    approveAt: 4,
    events: [
      { at: 5, ok: true, target: 'GET /announcements' },
      { at: 6, ok: false, target: 'GET /grades' },
    ],
    steps: [
      { at: 1.9, to: 'cut-g' },
      { at: 3, to: 'cut-g', click: true },
      { at: 3.2, to: 'approve' },
      { at: 4, to: 'approve', click: true },
      { at: 4.3, to: 'rest' },
    ],
    without: 'The agent reads your grades because it can.',
    withIt: 'You took grades off the list. The request stopped, and you still got your brief.',
  },
  {
    title: 'Your data heads somewhere new',
    length: 9.5,
    job: 'Summarise the course forum for me.',
    grants: [{ id: 'f', text: 'Read course discussions' }],
    approveAt: 2.9,
    events: [
      { at: 4, ok: true, target: 'GET /forum' },
      { at: 5.4, ok: false, target: 'POST paste.example/upload' },
    ],
    steps: [
      { at: 1.8, to: 'approve' },
      { at: 2.9, to: 'approve', click: true },
      { at: 3.2, to: 'rest' },
    ],
    without: 'A bug or a bad page can send what it read to any server.',
    withIt: 'That server is not in the warrant, so the request was never sent.',
  },
  {
    title: 'It wants to act as you',
    length: 11,
    job: 'Submit my CS301 Lab 4.',
    grants: [{ id: 's', text: 'Submit an assignment', tag: 'asks each run' }],
    approveAt: 2.8,
    ask: { at: 3.3, done: 4.6 },
    events: [
      { at: 5.4, ok: true, target: 'POST /assignments/cs301-lab4/submit' },
      { at: 6.7, ok: false, target: 'POST /forum/t1/reply' },
    ],
    steps: [
      { at: 1.8, to: 'approve' },
      { at: 2.8, to: 'approve', click: true },
      { at: 3.5, to: 'allow' },
      { at: 4.6, to: 'allow', click: true },
      { at: 4.9, to: 'rest' },
    ],
    without: 'It can submit or post in your name whenever it decides to.',
    withIt: 'It submitted once because you said yes, and it will ask again next time. The forum post stopped.',
  },
  {
    title: 'A script you already run',
    length: 9,
    job: 'Your own program, on your laptop.',
    command: 'warrant guard --allow api.example.com -- python my_agent.py',
    events: [
      { at: 3, ok: true, target: 'CONNECT api.example.com:443' },
      { at: 4.3, ok: false, target: 'CONNECT unknown-host.example:443' },
    ],
    steps: [
      { at: 0.6, to: 'cmd' },
      { at: 1.9, to: 'cmd', click: true },
      { at: 2.2, to: 'rest' },
    ],
    without: 'Your program and every library in it can call anywhere.',
    withIt: 'It only reaches the host you listed, and you see every attempt.',
  },
]

export function Scenes() {
  const [index, setIndex] = useState(0)
  const [t, setT] = useState(0)
  const [paused, setPaused] = useState(false)
  const stage = useRef<HTMLDivElement>(null)
  const inView = useInView(stage, { amount: 0.3 })
  const reduce = useReducedMotion()
  const scene = SCENES[index]
  const time = reduce ? scene.length : t

  useEffect(() => { setT(0) }, [index])

  useEffect(() => {
    if (!inView || paused || reduce) return
    let raf = 0
    let last = performance.now()
    const tick = (now: number) => {
      const dt = Math.min((now - last) / 1000, 0.1)
      last = now
      setT(v => {
        if (v + dt >= scene.length) {
          setIndex(i => (i + 1) % SCENES.length)
          return 0
        }
        return v + dt
      })
      raf = requestAnimationFrame(tick)
    }
    raf = requestAnimationFrame(tick)
    return () => cancelAnimationFrame(raf)
  }, [inView, paused, reduce, scene])

  /* The cursor flies to whichever element the current step names, so it stays right at any screen size. */
  const step = [...scene.steps].reverse().find(s => time >= s.at)
  const [cursor, setCursor] = useState({ x: 40, y: 40 })
  const targetName = step?.to ?? 'rest'
  useLayoutEffect(() => {
    const box = stage.current
    if (!box) return
    const place = () => {
      const el = box.querySelector(`[data-cur="${targetName}"]`)
      const outer = box.getBoundingClientRect()
      if (el) {
        const r = el.getBoundingClientRect()
        setCursor({ x: r.left - outer.left + r.width * 0.6, y: r.top - outer.top + r.height * 0.6 })
      } else {
        setCursor({ x: outer.width * 0.72, y: outer.height * 0.72 })
      }
    }
    place()
  }, [targetName, index, time > (scene.ask?.at ?? 0)])
  const clicking = scene.steps.some(s => s.click && time >= s.at && time < s.at + 0.35)

  const typed = scene.job.slice(0, Math.floor(Math.min(time / 1, 1) * scene.job.length))
  const approved = scene.approveAt !== undefined && time >= scene.approveAt
  const ran = scene.command ? time >= 2 : scene.ask ? time >= scene.ask.done : approved
  const asking = scene.ask && time >= scene.ask.at && time < scene.ask.done
  const showGrants = time >= 1.2
  const events = scene.events.filter(e => time >= e.at)
  const outcome = time >= (scene.events[scene.events.length - 1].at + 1)

  return (
    <div className="scenes">
      <div className="sc-stage" ref={stage} onClick={() => setPaused(p => !p)}>
        <div className="win-bar"><i /><i /><i /><span className="mono">Example {index + 1} of {SCENES.length}</span><span className="sc-state mono">{paused ? 'Paused, click to play' : 'Click to pause'}</span></div>
        <h3 className="sc-title" key={index}>{scene.title}</h3>
        <div className="sc-body">
          <div className="sc-left">
            <span className="label">{scene.command ? 'Your terminal' : 'The job'}</span>
            <p className="sc-job">{typed}</p>
            {scene.command && (
              <div className="sc-cmd" data-cur="cmd"><span>$</span> {scene.command}</div>
            )}
            {scene.grants && showGrants && (
              <div className={`sc-card enter ${approved ? 'ok' : ''}`}>
                <span className="label">The warrant</span>
                {scene.grants.map(g => {
                  const cut = g.cut !== undefined && time >= g.cut
                  return (
                    <div key={g.id} className={`sc-grant ${cut ? 'gone' : ''}`}>
                      <span className="sq" />{g.text}
                      {g.tag && <em>{g.tag}</em>}
                      {g.cut !== undefined && !cut && <b data-cur={`cut-${g.id}`}>Remove</b>}
                    </div>
                  )
                })}
                <div className="sc-foot">
                  {approved ? <span className="stamp stamp-in">Approved</span> : <span className="btn sc-btn" data-cur="approve">Approve</span>}
                </div>
              </div>
            )}
            {asking && (
              <div className="sc-ask enter">
                <b>This job changes something. Allow it this once?</b>
                <span className="btn signal sc-btn" data-cur="allow">Allow this run</span>
              </div>
            )}
          </div>
          <div className="sc-right">
            <span className="label">What the agent tried</span>
            {!ran && events.length === 0 && <p className="sc-wait">{scene.ask && approved ? 'Waiting for you' : 'Nothing runs until you approve'}</p>}
            <ol className="sc-events">
              {events.map(e => (
                <li key={e.target} className={`enter ${e.ok ? '' : 'bad'}`}>
                  <b>{e.ok ? 'Allowed' : 'Blocked'}</b><code>{e.target}</code>
                </li>
              ))}
            </ol>
          </div>
        </div>
        <div className={`sc-outcome ${outcome ? 'on' : ''}`} aria-hidden={!outcome}>
          <div><span className="label">Without Warrant</span><p>{scene.without}</p></div>
          <div className="with"><span className="label">With Warrant</span><p>{scene.withIt}</p></div>
        </div>
        {!reduce && (
          <div className={`sc-cursor ${clicking ? 'click' : ''}`} style={{ transform: `translate(${cursor.x}px, ${cursor.y}px)` }} aria-hidden="true">
            <svg width="20" height="24" viewBox="0 0 20 24"><path d="M2 1.5v18l5-4.6 3.4 7.4 3.4-1.5-3.4-7.3 6.8-.4z" fill="#141518" stroke="#fff" strokeWidth="1.6" strokeLinejoin="round" /></svg>
            <i />
          </div>
        )}
      </div>
      <div className="sc-tabs" role="tablist" aria-label="Examples">
        {SCENES.map((s, i) => (
          <button key={s.title} role="tab" aria-selected={i === index} className={i === index ? 'on' : ''}
            onClick={() => { setIndex(i); setT(0); setPaused(false) }}>
            <span>{s.title}</span>
            <i><u style={{ transform: `scaleX(${i === index ? time / s.length : i < index ? 1 : 0})` }} /></i>
          </button>
        ))}
      </div>
      <p className="sc-note mono">Animated examples of what Warrant does, with made-up hosts. The terminal below replays real runs, including one on the live GitHub API.</p>
    </div>
  )
}
