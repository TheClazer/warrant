import { AnimatePresence, motion } from 'motion/react'
import { FormEvent, useCallback, useEffect, useState } from 'react'
import { api, Mission, Warrant } from './api'
import { ago, Beam, Pill, rise, Shimmer, Skeleton, stagger, Tag } from './ui'

type Props = { onOpenRun: (runId: string) => void; notify: (msg: string) => void }

export function Missions({ onOpenRun, notify }: Props) {
  const [missions, setMissions] = useState<Mission[] | null>(null)
  const [selected, setSelected] = useState<string | null>(null)
  const [composing, setComposing] = useState(false)

  const load = useCallback(async () => {
    const list = await api.missions()
    setMissions(list)
    setSelected(s => s ?? list[0]?.id ?? null)
  }, [])
  useEffect(() => { load().catch(e => notify(e.message)) }, [load, notify])

  const current = missions?.find(m => m.id === selected) ?? null

  return (
    <div className="missions">
      <aside className="mlist">
        <div className="mlist-h">
          <span className="eyebrow">Missions</span>
          <button className="link" onClick={() => setComposing(c => !c)}>{composing ? 'Cancel' : 'New mission'}</button>
        </div>
        <AnimatePresence initial={false}>
          {composing && (
            <NewMission
              onDone={async m => { setComposing(false); await load(); setSelected(m.id) }}
              notify={notify}
            />
          )}
        </AnimatePresence>
        {!missions && <Skeleton lines={4} />}
        <motion.ul variants={stagger} initial="hidden" animate="show">
          {missions?.map(m => (
            <motion.li key={m.id} variants={rise}>
              <button className={`mrow ${m.id === selected ? 'on' : ''}`} onClick={() => setSelected(m.id)}>
                {m.id === selected && <motion.span layoutId="mrow-mark" className="mrow-mark" />}
                <span className="mrow-title">{m.title}</span>
                <span className="mrow-meta">
                  <Pill status={m.warrant?.status ?? 'none'} />
                  <span className="mono dim">{m.schedule ?? 'on request'}</span>
                </span>
              </button>
            </motion.li>
          ))}
        </motion.ul>
      </aside>

      <section className="mdetail">
          {current && (
            <motion.div key={current.id} initial={{ opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.18 }}>
              <MissionDetail mission={current} reload={load} onOpenRun={onOpenRun} notify={notify} />
            </motion.div>
          )}
      </section>
    </div>
  )
}

function NewMission({ onDone, notify }: { onDone: (m: Mission) => void; notify: (m: string) => void }) {
  const [title, setTitle] = useState('')
  const [text, setText] = useState('')
  const [busy, setBusy] = useState(false)
  const submit = async (e: FormEvent) => {
    e.preventDefault()
    if (!title.trim() || text.trim().length < 3) return
    setBusy(true)
    try { onDone(await api.createMission({ title: title.trim(), text: text.trim() })) }
    catch (err) { notify((err as Error).message) }
    finally { setBusy(false) }
  }
  return (
    <motion.form className="newm" onSubmit={submit}
      initial={{ height: 0, opacity: 0 }} animate={{ height: 'auto', opacity: 1 }} exit={{ height: 0, opacity: 0 }}>
      <label htmlFor="nm-title" className="eyebrow">Name</label>
      <input id="nm-title" value={title} onChange={e => setTitle(e.target.value)} placeholder="Weekly grades digest" maxLength={80} />
      <label htmlFor="nm-text" className="eyebrow">What should the agent do?</label>
      <textarea id="nm-text" rows={4} value={text} onChange={e => setText(e.target.value)}
        placeholder="Every Sunday evening, read my grades and tell me what changed this week." />
      <button className="btn" disabled={busy || !title.trim() || text.trim().length < 3}>Save mission</button>
    </motion.form>
  )
}

function MissionDetail({ mission, reload, onOpenRun, notify }: {
  mission: Mission; reload: () => Promise<void>; onOpenRun: (id: string) => void; notify: (m: string) => void
}) {
  const [warrant, setWarrant] = useState<Warrant | null>(mission.warrant)
  const [drafting, setDrafting] = useState(false)
  const [busy, setBusy] = useState(false)
  const [approveRun, setApproveRun] = useState(false)
  useEffect(() => { setWarrant(mission.warrant); setApproveRun(false) }, [mission])

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
    try { onOpenRun((await api.startRun(mission.id, approveRun)).run_id) }
    catch (e) { notify((e as Error).message) }
    finally { setBusy(false) }
  }

  const canRun = warrant?.status === 'approved' && (!warrant.per_run_approval || approveRun)

  return (
    <div className="detail">
      <header className="dhead">
        <div>
          <span className="eyebrow">{mission.schedule ? `Scheduled · ${mission.schedule}` : 'Runs on request'}</span>
          <h1>{mission.title}</h1>
        </div>
        <div className="dhead-actions">
          {warrant?.status === 'approved' && warrant.per_run_approval && (
            <label className="check">
              <input type="checkbox" checked={approveRun} onChange={e => setApproveRun(e.target.checked)} />
              <span>I approve the write in this run</span>
            </label>
          )}
          <button className="btn" disabled={!canRun || busy} onClick={run}>Run now</button>
        </div>
      </header>
      <blockquote className="mtext">{mission.text}</blockquote>

      {drafting ? (
        <div className="wcard pending">
          <Beam />
          <span className="eyebrow"><Shimmer>Nemotron is drafting the smallest warrant for this mission</Shimmer></span>
          <Skeleton lines={4} />
        </div>
      ) : warrant ? (
        <WarrantCard warrant={warrant} busy={busy}
          onApprove={() => act(() => api.approve(warrant.id))}
          onReject={() => act(() => api.reject(warrant.id))}
          onNarrow={cap => act(() => api.narrow(warrant.id, [cap]))}
          onRedraft={draft} />
      ) : (
        <div className="wcard empty">
          <span className="eyebrow">No warrant yet</span>
          <p>Before this mission can run, Warrant drafts the minimum access it needs. You read it, then decide.</p>
          <button className="btn" onClick={draft}>Draft warrant</button>
        </div>
      )}

      <RunHistory missionId={mission.id} onOpenRun={onOpenRun} key={mission.id + (mission.last_run?.id ?? '')} />
    </div>
  )
}

function WarrantCard({ warrant, busy, onApprove, onReject, onNarrow, onRedraft }: {
  warrant: Warrant; busy: boolean; onApprove: () => void; onReject: () => void
  onNarrow: (capability: string) => void; onRedraft: () => void
}) {
  const [showRules, setShowRules] = useState(false)
  const [policy, setPolicy] = useState<string | null>(null)
  const pending = warrant.status === 'checked'
  const failed = warrant.status === 'rejected_by_checker'

  useEffect(() => { setPolicy(null); setShowRules(false) }, [warrant.id])
  const toggleRules = async () => {
    setShowRules(s => !s)
    if (!policy) setPolicy(await api.policy(warrant.id).catch(() => '# policy unavailable'))
  }

  return (
    <motion.div layout className={`wcard ${pending ? 'pending' : ''} ${failed ? 'failed' : ''}`}>
      {pending && <Beam />}
      <div className="wcard-h">
        <span className="eyebrow">Warrant</span>
        <Pill status={warrant.status} />
        <span className="mono dim fp" title={warrant.fingerprint}>sha256 {warrant.fingerprint.slice(0, 12)}</span>
      </div>

      <div className="wcols">
        <div>
          <h3>This mission can</h3>
          <motion.ul className="can" variants={stagger} initial="hidden" animate="show">
            {warrant.can.map(g => (
              <motion.li key={g.capability} variants={rise}>
                <span className={`sq ${g.writes ? 'w' : ''}`} />
                <div>
                  <span>{g.text}</span>
                  {g.reason && <small>{g.reason}</small>}
                </div>
                <span className="can-side">
                  {g.writes && <Tag tone="signal">asks each run</Tag>}
                  {pending && warrant.can.length > 1 && (
                    <button className="remove" disabled={busy} onClick={() => onNarrow(g.capability)}
                      aria-label={`Remove: ${g.text}`} title="Remove this permission">Remove</button>
                  )}
                </span>
              </motion.li>
            ))}
          </motion.ul>
        </div>
        <div>
          <h3>It cannot</h3>
          <motion.ul className="cannot" variants={stagger} initial="hidden" animate="show">
            {warrant.cannot.map(c => <motion.li key={c} variants={rise}><span className="sq o" />{c}</motion.li>)}
          </motion.ul>
        </div>
      </div>

      {warrant.notes.length > 0 && (
        <div className="notes">{warrant.notes.map(n => <p key={n}>{n}</p>)}</div>
      )}
      {failed && (
        <div className="findings">
          <span className="eyebrow">The checker refused this draft</span>
          <ul>{warrant.checker_findings.map(f => <li key={f}>{f}</li>)}</ul>
        </div>
      )}

      <div className="wcard-f">
        {pending && <>
          <button className="btn" disabled={busy} onClick={onApprove}>Approve</button>
          <button className="btn ghost" disabled={busy} onClick={onReject}>Reject</button>
        </>}
        {(failed || warrant.status === 'rejected') && <button className="btn" onClick={onRedraft}>Draft again</button>}
        {warrant.status === 'approved' && (
          <span className="stamp">Approved {warrant.decided_at ? ago(warrant.decided_at) : ''}</span>
        )}
        <button className="link right" onClick={toggleRules} aria-expanded={showRules}>
          {showRules ? 'Hide' : 'Show'} the {warrant.rules.length} rule{warrant.rules.length === 1 ? '' : 's'} OpenShell enforces
        </button>
      </div>

      <AnimatePresence initial={false}>
        {showRules && (
          <motion.div className="rules" initial={{ height: 0, opacity: 0 }} animate={{ height: 'auto', opacity: 1 }}
            exit={{ height: 0, opacity: 0 }} transition={{ duration: 0.22 }}>
            <table>
              <thead><tr><th>Rule</th><th>Host</th><th>Methods</th><th>Paths</th></tr></thead>
              <tbody>
                {warrant.rules.map(r => (
                  <tr key={r.id}><td className="mono">{r.id}</td><td className="mono">{r.host}:{r.port}</td>
                    <td>{r.methods.map(m => <Tag key={m} tone={m === 'GET' ? undefined : 'signal'}>{m}</Tag>)}</td>
                    <td className="mono">{r.paths.join('  ')}</td></tr>
                ))}
              </tbody>
            </table>
            <pre className="policy">{policy ?? 'Loading policy…'}</pre>
          </motion.div>
        )}
      </AnimatePresence>
    </motion.div>
  )
}

function RunHistory({ missionId, onOpenRun }: { missionId: string; onOpenRun: (id: string) => void }) {
  const [runs, setRuns] = useState<Mission['runs']>()
  useEffect(() => { api.mission(missionId).then(m => setRuns(m.runs ?? [])).catch(() => setRuns([])) }, [missionId])
  if (!runs?.length) return null
  return (
    <div className="history">
      <span className="eyebrow">Recent runs</span>
      {runs.slice(0, 6).map(r => (
        <button key={r.id} className="hrow" onClick={() => onOpenRun(r.id)}>
          <Pill status={r.status} />
          <span className="mono dim">{ago(r.started_at)}</span>
          <span>{r.result?.blocked ? `${r.result.blocked} blocked` : 'nothing blocked'}</span>
          <span className="mono dim">{r.usage ? `${r.usage.model_calls} model calls` : ''}</span>
        </button>
      ))}
    </div>
  )
}
