import { motion } from 'motion/react'
import { useEffect, useState } from 'react'
import { api, Site } from './api'
import { rise, Skeleton, stagger, Tag } from './ui'

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
  return (
    <div className="page">
      <header className="phead">
        <span className="eyebrow">Evidence</span>
        <h1>Measured, not claimed</h1>
        <p className="lede">The same missions run under three setups: broad access, broad access with a warning to the
          model, and a per-mission warrant. Results appear here only from recorded runs.</p>
      </header>
      <div className="evtable">
        <table>
          <thead><tr><th>Setup</th><th>Off-warrant requests that went through</th><th>Missions completed</th><th>Model calls</th><th>Cost</th></tr></thead>
          <tbody>
            {['Broad access', 'Broad access + warning prompt', 'Warrant'].map((s, i) => (
              <tr key={s} className={i === 2 ? 'mine' : ''}><td><b>{s}</b></td><td>—</td><td>—</td><td>—</td><td>—</td></tr>
            ))}
          </tbody>
        </table>
        <p className="dim mono">No evaluation has been recorded yet. Cells stay empty until real runs fill them.</p>
      </div>
    </div>
  )
}
