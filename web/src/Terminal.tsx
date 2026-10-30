import { useInView, useReducedMotion } from 'motion/react'
import { useEffect, useRef, useState } from 'react'
import { CopyButton } from './ui'

type Line = { text: string; kind?: 'cmd' | 'input' | 'dim' | 'head' | 'ok' | 'bad' | 'gap'; wait?: number }

/* Replayed from real runs of these commands. Only the long answer is shortened, and that line says so. */
const SCRIPTS: Record<string, { label: string; lines: Line[] }> = {
  prove: {
    label: 'See the difference',
    lines: [
      { kind: 'cmd', text: 'uvx --from git+https://github.com/TheClazer/warrant warrant prove' },
      { kind: 'head', text: 'WARRANT PROVE  no AI, no key, and nothing leaves this machine', wait: 500 },
      { kind: 'gap', text: '' },
      { text: 'A scripted agent is given one job: read the announcements.' },
      { text: 'It also tries to do three things nobody asked for, first with broad access, then under a warrant.', wait: 900 },
      { kind: 'gap', text: '' },
      { kind: 'head', text: '                                    Without Warrant   With Warrant', wait: 500 },
      { kind: 'ok', text: '  Read the announcements (its job)  read              read', wait: 700 },
      { kind: 'bad', text: '  Read your grades                  read              BLOCKED', wait: 700 },
      { kind: 'bad', text: '  Submit Lab 4 as you               submitted         BLOCKED', wait: 700 },
      { kind: 'bad', text: '  Send your data to a stranger      sent              BLOCKED', wait: 900 },
      { kind: 'gap', text: '' },
      { kind: 'head', text: '  Checked at the receiving end' },
      { text: '  Submissions the portal recorded           1         0', wait: 400 },
      { text: '  Messages the stranger received            1         0', wait: 700 },
      { kind: 'gap', text: '' },
      { kind: 'ok', text: 'Same agent, same attempts. The warrant is the only difference.' },
    ],
  },
  try: {
    label: 'Try the whole flow',
    lines: [
      { kind: 'cmd', text: 'uvx --from git+https://github.com/TheClazer/warrant warrant try' },
      { kind: 'head', text: 'WARRANT  permissions for personal AI agents', wait: 500 },
      { kind: 'dim', text: 'Fictional course portal running at http://127.0.0.1:58838. No real accounts are involved.' },
      { kind: 'gap', text: '' },
      { text: "Job  Brief me on this week's announcements and tell me my latest grades." },
      { kind: 'dim', text: 'Without Warrant, an agent with your access could do 7 things here and reach any website.' },
      { kind: 'gap', text: '' },
      { text: 'Asking NVIDIA Nemotron what this job needs...', wait: 1100 },
      { kind: 'head', text: 'The AI asked for:', wait: 900 },
      { text: '  1. Read announcements on the course portal' },
      { text: '  2. Read your grades on the course portal' },
      { kind: 'dim', text: '  Everything else on this site, and every other website, stays blocked.' },
      { kind: 'input', text: 'Remove any? Type numbers like 2, or press Enter to keep them all: |2', wait: 500 },
      { text: '  Removed Read your grades on the course portal' },
      { kind: 'input', text: 'Approve and run? [Y/n] |y', wait: 300 },
      { kind: 'gap', text: '' },
      { kind: 'head', text: 'Running the agent', wait: 300 },
      { kind: 'ok', text: '  ALLOWED  GET /announcements', wait: 900 },
      { kind: 'bad', text: '  BLOCKED  GET /grades  not in this warrant', wait: 1000 },
      { kind: 'gap', text: '' },
      { kind: 'dim', text: '  (answer shortened here) The CS301 midterm moves to Hall B. Grades: blocked.', wait: 700 },
      { kind: 'head', text: 'What changed because of Warrant', wait: 300 },
      { text: '  Without it: GET /grades would have gone through.' },
      { kind: 'bad', text: '  With it:    stopped before being sent. The agent never got that data.' },
    ],
  },
  openshell: {
    label: 'With NVIDIA OpenShell',
    lines: [
      { kind: 'cmd', text: 'WARRANT_ENFORCER=openshell warrant try --remove portal.read.grades --yes' },
      { kind: 'head', text: 'The AI asked for:', wait: 1300 },
      { text: '  1. Read announcements on the course portal' },
      { kind: 'dim', text: '  Everything else on this site, and every other website, stays blocked.' },
      { kind: 'input', text: 'Approve and run? [Y/n] |y', wait: 400 },
      { kind: 'gap', text: '' },
      { kind: 'head', text: 'Running the agent', wait: 500 },
      { kind: 'dim', text: '  NVIDIA OpenShell sandbox wrt-680ef393c0e9', wait: 1400 },
      { kind: 'ok', text: '  ALLOWED  GET /announcements', wait: 900 },
      { kind: 'bad', text: '  BLOCKED  GET /grades  not in this warrant', wait: 1000 },
      { kind: 'gap', text: '' },
      { kind: 'head', text: 'What changed because of Warrant' },
      { text: '  Without it: GET /grades would have gone through.' },
      { kind: 'bad', text: '  With it:    stopped before being sent. The agent never got that data.' },
      { kind: 'gap', text: '' },
      { kind: 'dim', text: '  3 Nemotron calls, 3,994 tokens' },
    ],
  },
  guard: {
    label: 'Guard your own script',
    lines: [
      { kind: 'cmd', text: 'warrant guard --allow example.com -- curl -s -o /dev/null -w "%{http_code}\\n" https://example.com/' },
      { kind: 'head', text: 'WARRANT GUARD  allowed: example.com', wait: 400 },
      { kind: 'ok', text: '  ALLOWED  CONNECT example.com:443', wait: 600 },
      { text: '200', wait: 300 },
      { kind: 'dim', text: '  1 allowed, 0 blocked' },
      { kind: 'gap', text: '', wait: 700 },
      { kind: 'cmd', text: 'warrant guard --allow example.com -- curl -s -o /dev/null -w "%{http_code}\\n" https://www.iana.org/' },
      { kind: 'head', text: 'WARRANT GUARD  allowed: example.com', wait: 400 },
      { kind: 'bad', text: '  BLOCKED  CONNECT www.iana.org:443', wait: 600 },
      { text: '000', wait: 300 },
      { kind: 'dim', text: '  0 allowed, 1 blocked' },
    ],
  },
}

export function Terminal() {
  const [tab, setTab] = useState<keyof typeof SCRIPTS>('prove')
  const [count, setCount] = useState(0)
  const [typed, setTyped] = useState(0)
  const ref = useRef<HTMLDivElement>(null)
  const body = useRef<HTMLDivElement>(null)
  const inView = useInView(ref, { amount: 0.25 })
  const reduce = useReducedMotion()
  const lines = SCRIPTS[tab].lines

  useEffect(() => { setCount(0); setTyped(0) }, [tab])

  useEffect(() => {
    if (reduce) { setCount(lines.length); return }
    if (!inView) return
    let timer: ReturnType<typeof setTimeout>
    if (count >= lines.length) {
      timer = setTimeout(() => { setCount(0); setTyped(0) }, 5000)
    } else {
      const line = lines[count]
      const toType = line.kind === 'cmd' ? line.text.length : 0
      if (typed < toType) {
        timer = setTimeout(() => setTyped(n => Math.min(n + 3, toType)), 28)
      } else {
        timer = setTimeout(() => { setCount(c => c + 1); setTyped(0) }, line.wait ?? 140)
      }
    }
    return () => clearTimeout(timer)
  }, [count, typed, inView, reduce, lines])

  useEffect(() => {
    if (body.current) body.current.scrollTop = body.current.scrollHeight
  }, [count])

  const current = count < lines.length && lines[count].kind === 'cmd' ? lines[count] : null

  return (
    <div className="term" ref={ref}>
      <div className="term-tabs" role="tablist">
        {Object.entries(SCRIPTS).map(([id, s]) => (
          <button key={id} role="tab" aria-selected={tab === id} className={tab === id ? 'on' : ''} onClick={() => setTab(id)}>{s.label}</button>
        ))}
        <span className="term-copy"><CopyButton text={lines.find(l => l.kind === 'cmd')?.text ?? ''} label="Copy command" /></span>
      </div>
      <div className="term-body" ref={body} aria-label="Terminal replay">
        {lines.slice(0, count).map((line, i) => <Row key={`${tab}-${i}`} line={line} />)}
        {current && <div className="t-cmd"><span className="t-prompt">$ </span>{current.text.slice(0, typed)}<i className="t-caret" /></div>}
      </div>
    </div>
  )
}

function Row({ line }: { line: Line }) {
  if (line.kind === 'gap') return <div className="t-gap" />
  if (line.kind === 'cmd') return <div className="t-cmd"><span className="t-prompt">$ </span>{line.text}</div>
  if (line.kind === 'input') {
    const [prompt, answer] = line.text.split('|')
    return <div>{prompt}<b className="t-input">{answer}</b></div>
  }
  return <div className={line.kind ? `t-${line.kind}` : undefined}>{line.text}</div>
}

/** How `warrant guard` sits between a local program and the internet. */
export function GuardFlow() {
  return (
    <div className="flow" role="img" aria-label="Your program's requests pass through Warrant on your laptop. Allowed hosts go through. Everything else stops.">
      <div className="flow-node"><span className="label">Your laptop</span><b>Your agent or script</b></div>
      <div className="flow-lanes" aria-hidden="true">
        <div className="lane"><i className="packet pass" /></div>
        <div className="lane"><i className="packet stop" /></div>
      </div>
      <div className="flow-node gate"><span className="label">Your laptop</span><b>Warrant</b></div>
      <div className="flow-lanes" aria-hidden="true">
        <div className="lane"><i className="packet pass late" /></div>
        <div className="lane dead"><span>×</span></div>
      </div>
      <div className="flow-ends">
        <div className="flow-node ok"><b>Sites you allowed</b></div>
        <div className="flow-node no"><b>Everything else</b></div>
      </div>
    </div>
  )
}
