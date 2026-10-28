import { motion } from 'motion/react'
import { useEffect, useState } from 'react'
import { api, EvalSummary, Site } from './api'
import { rise, Skeleton, stagger, Tag, Ticker } from './ui'

export function Catalogue() {
  const [sites, setSites] = useState<Site[] | null>(null)
  useEffect(() => { api.catalogue().then(setSites).catch(() => setSites([])) }, [])
  return (
    <div className="page">
      <header className="phead">
        <span className="eyebrow">Reviewed sites</span>
        <h1>Everything an agent could ever be granted</h1>
        <p className="lede">The planner can only choose from this list. It cannot invent a website, a wildcard or a broader
          path. Adding a capability is a code change that a person reviews.</p>
      </header>
      {!sites && <Skeleton lines={6} />}
      {sites?.map(site => (
        <section key={site.id} className="site">
          <div className="site-h"><h2>{site.name}</h2><span className="mono dim">{site.base_url}</span></div>
          <motion.table variants={stagger} initial="hidden" animate="show">
            <thead><tr><th>Capability</th><th>What you will read</th><th>Request</th><th>Paths</th></tr></thead>
            <tbody>
              {site.capabilities.map(c => (
                <motion.tr key={c.id} variants={rise}>
                  <td className="mono">{c.id}</td>
                  <td>{c.plain}</td>
                  <td>{c.rule.methods.map(m => <Tag key={m} tone={c.writes ? 'signal' : undefined}>{m}</Tag>)}</td>
                  <td className="mono">{c.rule.paths.join('  ')}</td>
                </motion.tr>
              ))}
            </tbody>
          </motion.table>
        </section>
      ))}
    </div>
  )
}

export function Evidence() {
  const [data, setData] = useState<EvalSummary | null>(null)
  useEffect(() => { api.evalSummary().then(setData).catch(() => setData({ available: false })) }, [])
  const rows: [string, string][] = [['broad', 'Broad access'], ['warrant', 'Warrant']]
  const ready = data && data.available
  return (
    <div className="page">
      <header className="phead">
        <span className="eyebrow">Evidence</span>
        <h1>Measured, not claimed</h1>
        <p className="lede">Each mission asks for more than its approved warrant allows, so a faithful agent tries to reach
          pages outside it. The same missions run with broad access and under the warrant. Every number below comes
          from recorded runs.</p>
      </header>
      <div className="evtable">
        <table>
          <thead><tr><th>Setup</th><th>Runs</th><th>Off-warrant requests tried</th><th>Off-warrant requests that went through</th>
            <th>Missions completed</th><th>Nemotron calls</th><th>Tokens</th></tr></thead>
          <tbody>
            {rows.map(([key, label]) => {
              const r = ready ? data.setups[key] : undefined
              return (
                <tr key={key} className={key === 'warrant' ? 'mine' : ''}>
                  <td><b>{label}</b></td>
                  <td>{r ? r.runs : '—'}</td>
                  <td>{r ? r.outside_requests_attempted : '—'}</td>
                  <td>{r ? <Ticker value={r.outside_requests_that_went_through} /> : '—'}</td>
                  <td>{r ? `${r.missions_completed} / ${r.runs}` : '—'}</td>
                  <td>{r ? r.model_calls : '—'}</td>
                  <td>{r ? r.tokens.toLocaleString() : '—'}</td>
                </tr>
              )
            })}
          </tbody>
        </table>
        <p className="dim mono">
          {ready
            ? `${data.scenarios} frozen scenarios × ${data.repeats} repeats · ${data.model} · warrant runs enforced by ${data.enforcer_for_warrant_setup === 'openshell' ? 'NVIDIA OpenShell' : 'the built-in enforcer'} · scenarios sha256 ${data.scenarios_sha256.slice(0, 12)} · ${new Date(data.finished_at * 1000).toLocaleString()}`
            : 'No evaluation has been recorded yet. Cells stay empty until real runs fill them.'}
        </p>
      </div>
    </div>
  )
}
