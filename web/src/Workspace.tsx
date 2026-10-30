import { AnimatePresence, motion } from 'motion/react'
import { FormEvent, useCallback, useEffect, useMemo, useState } from 'react'
import { api, EvalSummary, Mission, Run, RunEvent, Site, streamRun, Warrant } from './api'
import CallChip from './rb/CallChip.jsx'
import { Answer, ago, Skeleton, Status, Tag } from './ui'

type Notify = (msg: string) => void
const HINT_TITLE = 'Announcements and grades'

/* ---------- Missions ---------- */

export function Missions({ notify }: { notify: Notify }) {
  const [missions, setMissions] = useState<Mission[] | null>(null)
  const [selected, setSelected] = useState<string | null>(null)
  const [composing, setComposing] = useState(false)

  const load = useCallback(async () => {
    const list = await api.missions()
    setMissions(list)
    setSelected(s => s ?? list.find(m => m.title === HINT_TITLE)?.id ?? list[0]?.id ?? null)
  }, [])
  useEffect(() => { load().catch(e => notify(e.message)) }, [load, notify])
  const current = missions?.find(m => m.id === selected) ?? null

  return (
    <div className="split-view">
      <aside className="list">
        <div className="list-h">
          <h2>Missions</h2>
          <button className="text-btn" onClick={() => setComposing(c => !c)}>{composing ? 'Cancel' : '+ New'}</button>
        </div>
        <AnimatePresence initial={false}>
          {composing && <NewMission notify={notify} onDone={async m => { setComposing(false); await load(); setSelected(m.id) }} />}
        </AnimatePresence>
        {!missions && <Skeleton lines={4} />}
        <ul className="cascade">
          {missions?.map(m => (
            <li key={m.id}>
              <button className={`list-row ${m.id === selected ? 'on' : ''}`} onClick={() => setSelected(m.id)}>
                <b>{m.title}</b>
                <Status status={m.warrant?.status ?? 'none'} />
              </button>
            </li>
          ))}
        </ul>
      </aside>
      <section className="detail">
        {current && (
          <div key={current.id} className="enter">
            <MissionDetail mission={current} reload={load} notify={notify} />
          </div>
        )}
      </section>
    </div>
  )
}

function NewMission({ onDone, notify }: { onDone: (m: Mission) => void; notify: Notify }) {
  const [title, setTitle] = useState('')
  const [text, setText] = useState('')
  const [busy, setBusy] = useState(false)
  const ok = title.trim().length > 0 && text.trim().length >= 3
  const submit = async (e: FormEvent) => {
    e.preventDefault()
    if (!ok) return
    setBusy(true)
    try { onDone(await api.createMission({ title: title.trim(), text: text.trim() })) }
    catch (err) { notify((err as Error).message) }
    finally { setBusy(false) }
  }
  return (
    <motion.form className="new" onSubmit={submit} initial={{ height: 0, opacity: 0 }} animate={{ height: 'auto', opacity: 1 }} exit={{ height: 0, opacity: 0 }}>
      <label htmlFor="nm-t" className="label">Name</label>
      <input id="nm-t" value={title} maxLength={80} onChange={e => setTitle(e.target.value)} placeholder="Weekly grades digest" />
      <label htmlFor="nm-x" className="label">What should the agent do?</label>
      <textarea id="nm-x" rows={3} value={text} onChange={e => setText(e.target.value)} placeholder="Read my grades and tell me what changed." />
      <button className="btn" disabled={busy || !ok}>Save mission</button>
    </motion.form>
  )
}

function Stepper({ step }: { step: number }) {
  return (
    <ol className="stepper" aria-label="Progress">
      {['Draft', 'Review', 'Run'].map((name, i) => (
        <li key={name} className={i === step ? 'on' : i < step ? 'past' : ''} aria-current={i === step ? 'step' : undefined}>
          <span>{i + 1}</span>{name}
        </li>
      ))}
    </ol>
  )
}

function MissionDetail({ mission, reload, notify }: { mission: Mission; reload: () => Promise<void>; notify: Notify }) {
  const [warrant, setWarrant] = useState<Warrant | null>(mission.warrant)
  const [drafting, setDrafting] = useState(false)
  const [busy, setBusy] = useState(false)
  const [confirmWrite, setConfirmWrite] = useState(false)
  const [runs, setRuns] = useState<Run[]>([])
  useEffect(() => { setWarrant(mission.warrant); setConfirmWrite(false) }, [mission])
  useEffect(() => { api.mission(mission.id).then(m => setRuns(m.runs ?? [])).catch(() => setRuns([])) }, [mission.id, warrant?.status])

  const act = async (fn: () => Promise<Warrant>) => {
    setBusy(true)
    try { setWarrant(await fn()); await reload() } catch (e) { notify((e as Error).message) } finally { setBusy(false) }
  }
  const draft = async () => {
    setDrafting(true)
    try { setWarrant(await api.draft(mission.id)); await reload() }
    catch (e) { notify((e as Error).message) }
    finally { setDrafting(false) }
  }
  const run = async () => {
    setBusy(true)
    try { location.hash = `#/run/${(await api.startRun(mission.id, confirmWrite)).run_id}` }
    catch (e) { notify((e as Error).message) }
    finally { setBusy(false) }
  }

  const status = warrant?.status
  const step = status === 'approved' ? 2 : status === 'checked' || status === 'rejected_by_checker' ? 1 : 0
  const canRun = status === 'approved' && (!warrant?.per_run_approval || confirmWrite)

  return (
    <div className="mission">
      <Stepper step={step} />
      <h1>{mission.title}</h1>
      <p className="mission-text">{mission.text}</p>
      {mission.schedule && <p className="sched mono">Runs on schedule: {mission.schedule}</p>}

      {drafting ? (
        <div className="card pending"><span className="beam" aria-hidden="true" />
          <p className="next"><b className="shimmer">Nemotron is drafting the smallest warrant for this mission.</b></p>
          <Skeleton lines={4} />
        </div>
      ) : !warrant || status === 'rejected' || status === 'expired' ? (
        <div className="card">
          <p className="next"><b>Start here.</b> Nemotron drafts the minimum access this mission needs. Nothing runs until you approve it.</p>
          <button className="btn signal" onClick={draft}>Draft warrant</button>
        </div>
      ) : (
        <WarrantCard warrant={warrant} busy={busy}
          onApprove={() => act(() => api.approve(warrant.id))}
          onReject={() => act(() => api.reject(warrant.id))}
          onNarrow={cap => act(() => api.narrow(warrant.id, [cap]))}
          onRedraft={draft} />
      )}

      {status === 'approved' && (
        <div className="run-bar">
          {warrant?.per_run_approval && (
            <label className="confirm">
              <input type="checkbox" checked={confirmWrite} onChange={e => setConfirmWrite(e.target.checked)} />
              I approve the write in this run
            </label>
          )}
          <button className="btn signal" disabled={!canRun || busy} onClick={run}>Run mission</button>
        </div>
      )}

      {runs.length > 0 && (
        <div className="history">
          <span className="label">Recent runs</span>
          {runs.slice(0, 5).map(r => (
            <a key={r.id} className="history-row" href={`#/run/${r.id}`}>
              <Status status={r.status} />
              <span>{r.result?.blocked ? `${r.result.blocked} blocked` : 'Nothing blocked'}</span>
              <span className="mono dim">{ago(r.started_at)}</span>
            </a>
          ))}
        </div>
      )}
    </div>
  )
}

function WarrantCard({ warrant, busy, onApprove, onReject, onNarrow, onRedraft }: {
  warrant: Warrant; busy: boolean; onApprove: () => void; onReject: () => void; onNarrow: (cap: string) => void; onRedraft: () => void
}) {
  const [open, setOpen] = useState(false)
  const [policy, setPolicy] = useState<string | null>(null)
  const pending = warrant.status === 'checked'
  const failed = warrant.status === 'rejected_by_checker'
  useEffect(() => { setPolicy(null); setOpen(false) }, [warrant.id])
  const toggle = async () => {
    setOpen(o => !o)
    if (!policy) setPolicy(await api.policy(warrant.id).catch(() => '# policy unavailable'))
  }
  return (
    <div className={`card ${pending ? 'pending' : ''}`}>
      {pending && <span className="beam" aria-hidden="true" />}
      {pending && <p className="next"><b>Read this, remove anything you don't want, then approve.</b></p>}
      <div className="grants">
        <div>
          <span className="label">This mission can</span>
          <ul className="cascade">
            {warrant.can.map(g => (
              <li key={g.capability} className="grant">
                <span className={`sq ${g.writes ? 'w' : ''}`} />
                <div><span>{g.text}</span>{g.reason && <small>{g.reason}</small>}</div>
                {g.writes && <Tag tone="signal">asks each run</Tag>}
                {pending && warrant.can.length > 1 && (
                  <button className="remove" disabled={busy} onClick={() => onNarrow(g.capability)} aria-label={`Remove: ${g.text}`}>Remove</button>
                )}
              </li>
            ))}
          </ul>
        </div>
        <div>
          <span className="label">It cannot</span>
          <ul>{warrant.cannot.map(c => <li key={c} className="grant muted"><span className="sq o" /><div>{c}</div></li>)}</ul>
        </div>
      </div>
      {warrant.notes.map(n => <p key={n} className="card-note">{n}</p>)}
      {failed && (
        <div className="findings">
          <b>The checker refused this draft.</b>
          <ul>{warrant.checker_findings.map(f => <li key={f}>{f}</li>)}</ul>
        </div>
      )}
      <div className="card-foot">
        {pending && <>
          <button className="btn" disabled={busy} onClick={onApprove}>Approve</button>
          <button className="btn ghost" disabled={busy} onClick={onReject}>Reject</button>
        </>}
        {failed && <button className="btn" onClick={onRedraft}>Draft again</button>}
        {warrant.status === 'approved' && <span className="stamp">Approved {warrant.decided_at ? ago(warrant.decided_at) : ''}</span>}
        <button className="text-btn push" onClick={toggle} aria-expanded={open}>{open ? 'Hide' : 'Show'} technical rules</button>
      </div>
      <AnimatePresence initial={false}>
        {open && (
          <motion.div className="rules" initial={{ height: 0, opacity: 0 }} animate={{ height: 'auto', opacity: 1 }} exit={{ height: 0, opacity: 0 }} transition={{ duration: 0.2 }}>
            <p className="mono dim">OpenShell policy generated from this warrant · sha256 {warrant.fingerprint.slice(0, 16)}</p>
            <pre>{policy ?? 'Loading policy…'}</pre>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  )
}

/* ---------- Run ---------- */

function pathOf(url: string) {
  try { return new URL(url).pathname } catch { return url }
}

function whyBlocked(e: RunEvent) {
  const reason = String(e.reason ?? '')
  return reason.startsWith('OpenShell') ? reason : 'Not in this mission’s warrant.'
}

export function RunPage({ runId, portal }: { runId: string; portal?: string }) {
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
  const answer = events.find(e => e.kind === 'answer')
  const sandbox = events.find(e => e.kind === 'sandbox')
  const done = events.some(e => e.kind === 'done')
  const status = done ? (run?.status === 'running' ? 'completed' : run?.status ?? 'completed') : 'running'
  const tokens = useMemo(() => models.reduce((s, e) => s + Number(e.prompt_tokens ?? 0) + Number(e.completion_tokens ?? 0), 0), [models])

  const calls = useMemo(() => {
    const steps = events.filter(e => e.kind === 'step' && e.url)
    return steps.map(s => {
      const path = pathOf(String(s.url))
      const hit = network.find(n => n.seq > s.seq && (n.url === s.url || n.path === path))
      return { seq: s.seq, method: String(s.method ?? 'GET'), path, status: hit ? (hit.decision === 'blocked' ? 'error' : 'done') : done ? 'error' : 'running' }
    })
  }, [events, network, done])

  const host = (e: RunEvent) => {
    const here = portal ? (() => { try { return new URL(portal).hostname } catch { return '' } })() : ''
    return e.host && e.host !== here ? String(e.host) : ''
  }

  if (error) return <div className="page"><p className="findings">{error}</p></div>
  if (!run) return <div className="page"><Skeleton lines={5} /></div>

  return (
    <div className="page run">
      <a className="text-btn" href="#/app">← Missions</a>
      <header className="run-head">
        <div>
          <span className="label">{sandbox ? `NVIDIA OpenShell sandbox ${String(sandbox.name)}` : 'Built-in enforcer'} · {ago(run.started_at)}</span>
          <h1>{status === 'running' ? <span className="shimmer">Agent is working</span> : blocked.length ? `Finished, ${blocked.length} request${blocked.length === 1 ? '' : 's'} blocked` : 'Finished, nothing blocked'}</h1>
        </div>
        <Status status={status} />
      </header>

      <div className="run-grid">
        <section className="run-main">
          <span className="label">What the agent did</span>
          <div className="calls">
            {calls.map(c => (
              <CallChip key={c.seq} icon="file" name={c.method} argument={c.path} status={c.status} size={34} radius={3}
                surfaceColor="#fff" color="#141518" progressColor="#141518" doneColor="#1F7A4D" errorColor="#B27700" showTimer={false} expectedMs={1800} />
            ))}
            {!calls.length && <Skeleton lines={2} />}
          </div>
          <AnimatePresence>
            {answer && (
              <motion.div className="result" initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }}>
                <span className="label">Result</span>
                <Answer text={String(answer.text ?? '')} />
              </motion.div>
            )}
          </AnimatePresence>
          {run.result?.error && <p className="findings">{run.result.error}</p>}
        </section>

        <aside className="feed-col">
          <span className="label">Security feed</span>
          <ol className="feed">
            <AnimatePresence initial={false}>
              {[...network].reverse().map(e => (
                <motion.li key={e.seq} layout initial={{ opacity: 0, y: -10 }} animate={{ opacity: 1, y: 0 }}
                  transition={{ type: 'spring', stiffness: 420, damping: 30 }} className={`event ${e.decision === 'blocked' ? 'bad' : ''}`}>
                  <div className="event-h mono"><b>{e.decision === 'blocked' ? 'Blocked' : 'Allowed'}</b><span>{new Date(Number(e.t) * 1000).toLocaleTimeString()}</span></div>
                  <code>{String(e.method)} {host(e)}{String(e.path)}</code>
                  {e.decision === 'blocked' && <small>{whyBlocked(e)}</small>}
                </motion.li>
              ))}
            </AnimatePresence>
            {!network.length && <li className="dim">No requests yet.</li>}
          </ol>
          <dl className="meters">
            <div><dt>Nemotron calls</dt><dd>{models.length}</dd></div>
            <div><dt>Tokens</dt><dd>{tokens.toLocaleString()}</dd></div>
          </dl>
        </aside>
      </div>
    </div>
  )
}

/* ---------- Reviewed sites ---------- */

export function Sites() {
  const [sites, setSites] = useState<Site[] | null>(null)
  useEffect(() => { api.catalogue().then(setSites).catch(() => setSites([])) }, [])
  return (
    <div className="page">
      <h1>Reviewed sites</h1>
      <p className="lede">Everything an agent could ever be granted. Nemotron can only choose from this list, and adding to it is a code change a person reviews.</p>
      {!sites && <Skeleton lines={6} />}
      {sites?.map(site => (
        <section key={site.id} className="site">
          <h2>{site.name}</h2>
          <div className="scroll-x">
            <table>
              <thead><tr><th>You would read</th><th>Request</th><th>Paths</th></tr></thead>
              <tbody>
                {site.capabilities.map(c => (
                  <tr key={c.id}>
                    <td>{c.plain}</td>
                    <td>{c.rule.methods.map(m => <Tag key={m} tone={c.writes ? 'signal' : undefined}>{m}</Tag>)}</td>
                    <td className="mono">{c.rule.paths.join('  ')}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      ))}
    </div>
  )
}

/* ---------- Evidence ---------- */

export function Evidence() {
  const [data, setData] = useState<EvalSummary | null>(null)
  useEffect(() => { api.evalSummary().then(setData).catch(() => setData({ available: false })) }, [])
  const rows: [string, string][] = [['broad', 'Broad access'], ['warrant', 'Warrant']]
  const ready = data?.available ? data : null
  return (
    <div className="page">
      <h1>Evidence</h1>
      <p className="lede">Each mission asks for more than its approved warrant, so a faithful agent tries to reach further. The same missions run with broad access and under the warrant. Every number comes from recorded runs.</p>
      <div className="scroll-x">
        <table className="ev-table">
          <thead><tr><th>Setup</th><th>Runs</th><th>Off-warrant tried</th><th>Went through</th><th>Expected fact found</th><th>Nemotron calls</th><th>Tokens</th></tr></thead>
          <tbody>
            {rows.map(([key, label]) => {
              const r = ready?.setups[key]
              return (
                <tr key={key} className={key === 'warrant' ? 'mine' : ''}>
                  <td><b>{label}</b></td>
                  <td>{r?.runs ?? '—'}</td>
                  <td>{r?.outside_requests_attempted ?? '—'}</td>
                  <td className="strong">{r ? r.outside_requests_that_went_through : '—'}</td>
                  <td>{r ? `${r.missions_completed} / ${r.runs}` : '—'}</td>
                  <td>{r?.model_calls ?? '—'}</td>
                  <td>{r ? r.tokens.toLocaleString() : '—'}</td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>
      {ready && <p className="mono dim ev-meta">{ready.scenarios} frozen scenarios × {ready.repeats} repeats · {ready.model} · warrant runs enforced by {ready.enforcer_for_warrant_setup === 'openshell' ? 'NVIDIA OpenShell' : 'the built-in enforcer'} · scenarios sha256 {ready.scenarios_sha256.slice(0, 12)}</p>}
      <div className="limits">
        <h2>What this does not show</h2>
        <ul>
          <li>These runs used the built-in enforcer. OpenShell was verified separately, with a real sandbox and its own logs.</li>
          <li>The portal is fictional, and the test covers over-reach, not planted prompt-injection pages.</li>
          <li>The expected fact appeared in 3 of 10 answers in both setups. That is an agent-quality limit, on a small sample.</li>
          <li>A warrant stops requests. It does not stop a page from misleading the agent's answer.</li>
        </ul>
      </div>
    </div>
  )
}

