import { useInView } from 'motion/react'
import { ReactNode, useRef, useState } from 'react'

export function Skeleton({ lines = 3 }: { lines?: number }) {
  return (
    <div className="skeleton" aria-busy="true" aria-label="Loading">
      {Array.from({ length: lines }, (_, i) => <i key={i} style={{ width: `${90 - i * 16}%` }} />)}
    </div>
  )
}

/** Fades a landing section in once, with CSS so a throttled tab can't leave it half visible. */
export function Reveal({ children, className = '' }: { children: ReactNode; className?: string }) {
  const ref = useRef<HTMLDivElement>(null)
  const seen = useInView(ref, { once: true, amount: 0.1 })
  return <div ref={ref} className={`${className} ${seen ? 'enter' : 'before-enter'}`}>{children}</div>
}

export function CopyButton({ text, label = 'Copy' }: { text: string; label?: string }) {
  const [copied, setCopied] = useState(false)
  const copy = async () => {
    try {
      await navigator.clipboard.writeText(text)
      setCopied(true)
      setTimeout(() => setCopied(false), 1500)
    } catch { /* clipboard blocked: the text can still be selected */ }
  }
  return <button className="copy" onClick={copy} aria-label={`Copy command: ${text}`}>{copied ? 'Copied' : label}</button>
}

export function Code({ text }: { text: string }) {
  return (
    <div className="code">
      <CopyButton text={text} />
      <pre>{text}</pre>
    </div>
  )
}

export function Tag({ children, tone }: { children: ReactNode; tone?: 'signal' }) {
  return <span className={`tag ${tone ?? ''}`}>{children}</span>
}

const LABELS: Record<string, string> = {
  checked: 'Needs your approval', approved: 'Approved', rejected: 'Rejected', rejected_by_checker: 'Failed checks',
  expired: 'Expired', running: 'Running', completed: 'Completed', failed: 'Failed', budget_exceeded: 'Limit reached',
  step_limit: 'Step limit', no_answer: 'No answer', none: 'No warrant yet',
}
export function Status({ status }: { status: string }) {
  return <span className={`status s-${status}`}><i />{LABELS[status] ?? status}</span>
}

export function ago(t: number) {
  const s = Math.max(0, Date.now() / 1000 - t)
  if (s < 60) return 'just now'
  if (s < 3600) return `${Math.floor(s / 60)} min ago`
  if (s < 86400) return `${Math.floor(s / 3600)} h ago`
  return new Date(t * 1000).toLocaleDateString(undefined, { day: 'numeric', month: 'short' })
}

/** The agent's short Markdown answer: headings, paragraphs, lists, tables, bold, italics, code. */
export function Answer({ text }: { text: string }) {
  const inline = (s: string) =>
    s.split(/(\*\*[^*]+\*\*|`[^`]+`|\*[^*]+\*)/g).map((part, i) =>
      part.startsWith('**') ? <b key={i}>{part.slice(2, -2)}</b>
        : part.startsWith('*') && part.endsWith('*') && part.length > 2 ? <i key={i}>{part.slice(1, -1)}</i>
        : part.startsWith('`') ? <code key={i}>{part.slice(1, -1)}</code> : part)
  return (
    <div className="answer">
      {text.replace(/^(#{1,4}\s.+)$/gm, '\n$1\n').split(/\n{2,}/).map(b => b.trim()).filter(b => b && !/^-{3,}$/.test(b)).map((b, i) => {
        const lines = b.split('\n').filter(Boolean)
        if (lines.length >= 2 && lines.every(l => l.trim().startsWith('|'))) {
          const cells = (l: string) => l.trim().replace(/^\||\|$/g, '').split('|').map(c => c.trim())
          const [head, ...body] = lines.filter(l => !/^\s*\|?\s*:?-{2,}/.test(l)).map(cells)
          return (
            <div className="scroll-x" key={i}>
              <table>
                <thead><tr>{head.map((h, j) => <th key={j}>{inline(h)}</th>)}</tr></thead>
                <tbody>{body.map((r, k) => <tr key={k}>{r.map((c, j) => <td key={j}>{inline(c)}</td>)}</tr>)}</tbody>
              </table>
            </div>
          )
        }
        if (lines.every(l => /^\s*[-*•]\s+/.test(l))) {
          return <ul key={i}>{lines.map((l, j) => <li key={j}>{inline(l.replace(/^\s*[-*•]\s+/, ''))}</li>)}</ul>
        }
        if (/^#{1,4}\s/.test(b)) return <h4 key={i}>{inline(b.replace(/^#{1,4}\s+/, ''))}</h4>
        return <p key={i}>{inline(b)}</p>
      })}
    </div>
  )
}
