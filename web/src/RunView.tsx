import { AnimatePresence, motion } from 'motion/react'
import { useEffect, useMemo, useState } from 'react'
import { api, Run, RunEvent, streamRun } from './api'
import { Answer, ago, Pill, Shimmer, Skeleton, Ticker } from './ui'

export function RunView({ runId, onBack }: { runId: string; onBack: () => void }) {
  const [run, setRun] = useState<Run | null>(null)
  const [events, setEvents] = useState<RunEvent[]>([])
  const [error, setError] = useState('')

  useEffect(() => {
    let stop = () => {}
    setEvents([])
    api.run(runId).then(r => {
      setRun(r)
      setEvents(r.events)
      if (r.status === 'running') {
        const seen = new Set(r.events.map(e => e.seq))
        stop = streamRun(runId, e => {
          if (seen.has(e.seq)) return
          seen.add(e.seq)
          setEvents(prev => [...prev, e])
          if (e.kind === 'done') api.run(runId).then(setRun).catch(() => {})
        })
      }
    }).catch(e => setError(e.message))
    return () => stop()
  }, [runId])

  const network = events.filter(e => e.kind === 'network')
  const blocked = network.filter(e => e.decision === 'blocked')
  const models = events.filter(e => e.kind === 'model')
  const activity = events.filter(e => ['step', 'answer', 'error'].includes(e.kind))
  const page = [...events].reverse().find(e => e.kind === 'page')
  const answer = events.find(e => e.kind === 'answer')
  const done = events.some(e => e.kind === 'done')
  const status = done ? (run?.status === 'running' ? 'completed' : run?.status ?? 'completed') : 'running'
  const tokens = useMemo(
    () => models.reduce((s, e) => s + Number(e.prompt_tokens ?? 0) + Number(e.completion_tokens ?? 0), 0),
    [models],
  )
  const cost = models.every(e => e.cost_usd != null) && models.length
    ? models.reduce((s, e) => s + Number(e.cost_usd), 0) : null

  if (error) return <div className="runview"><p className="err">{error}</p></div>
  if (!run) return <div className="runview"><Skeleton lines={5} /></div>

  return (
    <div className="runview">
      <header className="rhead">
        <button className="link" onClick={onBack}>← Missions</button>
        <div className="rhead-title">
          <span className="eyebrow">Run · {ago(run.started_at)} · {run.setup === 'warrant' ? 'under warrant' : run.setup}</span>
          <h1>{status === 'running' ? <Shimmer>Agent is working</Shimmer> : 'Run finished'}</h1>
        </div>
        <Pill status={status} />
      </header>

      <div className="counters">
        <div><span className="eyebrow">Requests allowed</span><Ticker value={network.length - blocked.length} /></div>
        <div className={blocked.length ? 'hot' : ''}><span className="eyebrow">Requests blocked</span><Ticker value={blocked.length} /></div>
        <div><span className="eyebrow">Nemotron calls</span><Ticker value={models.length} /></div>
        <div><span className="eyebrow">Tokens</span><Ticker value={tokens} /></div>
        <div><span className="eyebrow">Cost</span>{cost == null ? <span className="num dim">—</span> : <Ticker value={cost} decimals={5} prefix="$" />}</div>
      </div>

      <div className="rgrid">
        <section className="panel">
          <span className="eyebrow">What the agent is reading</span>
          <AnimatePresence mode="wait">
            {page ? (
              <motion.div key={page.seq} className="reader" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}>
                <div className="reader-url mono">{String(page.url)}</div>
                <h3>{String(page.title || 'Untitled page')}</h3>
                <pre>{String(page.excerpt ?? '')}</pre>
              </motion.div>
            ) : (
              <motion.div key="none" className="reader empty"><Skeleton lines={5} /></motion.div>
            )}
          </AnimatePresence>
          <span className="eyebrow" style={{ marginTop: 18 }}>Steps</span>
          <ol className="activity">
            <AnimatePresence initial={false}>
              {activity.map(e => (
                <motion.li key={e.seq} initial={{ opacity: 0, x: -6 }} animate={{ opacity: 1, x: 0 }}
                  className={`act k-${e.kind}`}>
                  <span className="sq" />
                  <span>{e.kind === 'answer' ? 'Wrote the answer' : String(e.text ?? e.error ?? '')}</span>
                </motion.li>
              ))}
            </AnimatePresence>
          </ol>
        </section>

        <section className="panel">
          <span className="eyebrow">Security feed</span>
          <ol className="feed">
            <AnimatePresence initial={false}>
              {[...network].reverse().map(e => (
                <motion.li key={e.seq} layout
                  initial={{ opacity: 0, y: -10, scale: 0.98 }} animate={{ opacity: 1, y: 0, scale: 1 }}
                  transition={{ type: 'spring', stiffness: 420, damping: 30 }}
                  className={`ev ${e.decision === 'blocked' ? 'bad' : ''}`}>
                  <div className="ev-h mono">
                    <span>{e.decision === 'blocked' ? 'Blocked' : 'Allowed'}</span>
                    <span>{new Date(Number(e.t) * 1000).toLocaleTimeString()}</span>
                  </div>
                  <div className="ev-target"><b>{String(e.method)}</b> {String(e.host)}{e.port && ![80, 443].includes(Number(e.port)) ? `:${e.port}` : ''}{String(e.path)}</div>
                  <div className="ev-why">{e.decision === 'blocked' ? 'Not in this mission’s warrant.' : `Matches ${String(e.rule ?? 'the warrant')}`}</div>
                </motion.li>
              ))}
            </AnimatePresence>
            {!network.length && <li className="dim">No requests yet.</li>}
          </ol>
        </section>
      </div>

      <AnimatePresence>
        {answer && (
          <motion.section className="panel answer-panel" initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }}>
            <span className="eyebrow">Result</span>
            <Answer text={String(answer.text ?? '')} />
          </motion.section>
        )}
      </AnimatePresence>
      {run.result?.error && <p className="err">{run.result.error}</p>}
    </div>
  )
}
