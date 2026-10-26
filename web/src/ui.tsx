import { animate, motion, useInView, useMotionValue, useReducedMotion, useTransform } from 'motion/react'
import { ReactNode, useEffect, useRef } from 'react'

/** Number that rolls to its value the first time it is seen (cf. Magic UI's number ticker). */
export function Ticker({ value, decimals = 0, prefix = '' }: { value: number; decimals?: number; prefix?: string }) {
  const ref = useRef<HTMLSpanElement>(null)
  const seen = useInView(ref, { once: true })
  const reduce = useReducedMotion()
  const mv = useMotionValue(reduce ? value : 0)
  const text = useTransform(mv, v => prefix + v.toFixed(decimals))
  useEffect(() => {
    if (!seen) return
    if (reduce) { mv.set(value); return }
    const controls = animate(mv, value, { duration: 0.9, ease: [0.16, 1, 0.3, 1] })
    return () => controls.stop()
  }, [seen, value, reduce, mv])
  return <motion.span ref={ref} className="num">{text}</motion.span>
}

/** A slow light travelling along the border, used only on the one card waiting for a decision. */
export function Beam() {
  return <span className="beam" aria-hidden="true" />
}

/** Placeholder lines while the model is drafting. */
export function Skeleton({ lines = 3 }: { lines?: number }) {
  return (
    <div className="skeleton" aria-busy="true" aria-label="Drafting">
      {Array.from({ length: lines }, (_, i) => <i key={i} style={{ width: `${88 - i * 17}%` }} />)}
    </div>
  )
}

export function Shimmer({ children }: { children: ReactNode }) {
  return <span className="shimmer">{children}</span>
}

export const stagger = {
  hidden: {},
  show: { transition: { staggerChildren: 0.06, delayChildren: 0.05 } },
}
export const rise = {
  hidden: { opacity: 0, y: 8 },
  show: { opacity: 1, y: 0, transition: { type: 'spring', stiffness: 380, damping: 32 } },
}

export function Tag({ children, tone }: { children: ReactNode; tone?: 'signal' | 'ink' | 'hazard' | 'ok' }) {
  return <span className={`tag ${tone ?? ''}`}>{children}</span>
}

export function Pill({ status }: { status: string }) {
  const label: Record<string, string> = {
    checked: 'Needs approval', approved: 'Approved', rejected: 'Rejected', rejected_by_checker: 'Failed checks',
    draft: 'Draft', running: 'Running', completed: 'Completed', failed: 'Failed', budget_exceeded: 'Budget reached',
    step_limit: 'Step limit', no_answer: 'No answer', none: 'No warrant',
  }
  return <span className={`pill s-${status}`}><i />{label[status] ?? status}</span>
}

export function ago(t: number) {
  const s = Math.max(0, Date.now() / 1000 - t)
  if (s < 60) return 'just now'
  if (s < 3600) return `${Math.floor(s / 60)} min ago`
  if (s < 86400) return `${Math.floor(s / 3600)} h ago`
  return new Date(t * 1000).toLocaleDateString(undefined, { day: 'numeric', month: 'short' })
}

/** Renders the agent's short Markdown answer: paragraphs and bullet lists, bold, inline code. */
export function Answer({ text }: { text: string }) {
  const blocks = text.split(/\n{2,}/)
  const inline = (s: string) =>
    s.split(/(\*\*[^*]+\*\*|`[^`]+`)/g).map((part, i) =>
      part.startsWith('**') ? <b key={i}>{part.slice(2, -2)}</b>
        : part.startsWith('`') ? <code key={i}>{part.slice(1, -1)}</code> : part)
  return (
    <div className="answer">
      {blocks.map((b, i) => {
        const lines = b.split('\n').filter(Boolean)
        if (lines.every(l => /^\s*[-*•]\s+/.test(l))) {
          return <ul key={i}>{lines.map((l, j) => <li key={j}>{inline(l.replace(/^\s*[-*•]\s+/, ''))}</li>)}</ul>
        }
        return <p key={i}>{inline(b)}</p>
      })}
    </div>
  )
}
