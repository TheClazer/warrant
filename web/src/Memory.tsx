import { FormEvent, useCallback, useEffect, useState } from 'react'
import { api, MemoryEntry, SkillEntry } from './api'
import { ago, Code, Skeleton } from './ui'

const LABELS: Record<string, string> = {
  note: 'You asked it to remember',
  refusal: 'You removed this from a job',
  last: 'Its last answer to a job',
}

export function MemoryPage({ notify }: { notify: (msg: string) => void }) {
  const [memory, setMemory] = useState<MemoryEntry[] | null>(null)
  const [skills, setSkills] = useState<SkillEntry[]>([])
  const [note, setNote] = useState('')

  const load = useCallback(async () => {
    const [m, s] = await Promise.all([api.memory(), api.skills()])
    setMemory(m)
    setSkills(s)
  }, [])
  useEffect(() => { load().catch(e => notify(e.message)) }, [load, notify])

  const act = async (fn: () => Promise<unknown>) => {
    try { await fn(); await load() } catch (e) { notify((e as Error).message) }
  }
  const add = (e: FormEvent) => {
    e.preventDefault()
    if (!note.trim()) return
    void act(async () => { await api.addMemory(note.trim()); setNote('') })
  }
  const run = async (s: SkillEntry) => {
    try {
      const writes = s.warrant.per_run_approval
      if (writes && !window.confirm(`“${s.name}” changes something. Allow this run?`)) return
      location.hash = `#/run/${(await api.runSkill(s.name, writes)).run_id}`
    } catch (e) { notify((e as Error).message) }
  }

  return (
    <div className="page memory">
      <h1>Memory and skills</h1>
      <p className="lede">Warrant learns how you work between runs. None of this can give the agent a new permission: memory is background, and only an approved warrant opens anything.</p>

      <section className="mem-sec">
        <h2>Skills</h2>
        <p className="dim-p">A skill is a job you've approved, saved by name. It runs again with the same warrant, without asking the AI for new permissions. Jobs that change something still ask every time.</p>
        {skills.length === 0 && <p className="empty">No skills yet. Run a job, then choose “Save as a skill” on its result.</p>}
        <ul className="skills">
          {skills.map(s => (
            <li key={s.name} className="enter">
              <div>
                <b>{s.name}</b>
                <p>{s.text}</p>
                <small>Can only: {s.warrant.can.map(g => g.text.replace(' (asks you every run)', '')).join(', ')}</small>
              </div>
              <div className="skill-actions">
                <button className="btn signal" onClick={() => run(s)}>Run</button>
                <button className="text-btn" onClick={() => act(() => api.deleteSkill(s.name))}>Delete</button>
              </div>
            </li>
          ))}
        </ul>
      </section>

      <section className="mem-sec">
        <h2>Memory</h2>
        <p className="dim-p">The agent gets your notes and its last answer to the same job. Permissions you removed stay removed from later drafts of that job, until you forget them here.</p>
        <form className="mem-add" onSubmit={add}>
          <input aria-label="Something to remember" maxLength={300} value={note} onChange={e => setNote(e.target.value)} placeholder="For example: I'm in section B, and I only care about CS301." />
          <button className="btn" disabled={!note.trim()}>Remember</button>
        </form>
        {!memory && <Skeleton lines={3} />}
        {memory?.length === 0 && <p className="empty">Nothing yet. Run a job or add a note.</p>}
        <ul className="mem-list">
          {memory?.map(m => (
            <li key={m.id} className="enter">
              <div><span className="label">{LABELS[m.kind] ?? m.kind} · {ago(m.created_at)}</span><p>{m.text}</p></div>
              <button className="text-btn" onClick={() => act(() => api.forget(m.id))}>Forget</button>
            </li>
          ))}
        </ul>
        <p className="dim-p note-public">On this public demo, memory and skills are shared by all visitors and reset when the server restarts. On your machine they stay in <code>~/.warrant</code>.</p>
      </section>

      <section className="mem-sec">
        <h2>The same from your terminal</h2>
        <Code text={`warrant remember "I only care about CS301"\nwarrant memory\nwarrant try "Find my exams this week" --save-as exams\nwarrant skill list\nwarrant skill run exams`} />
      </section>
    </div>
  )
}
