export type Rule = { id: string; host: string; port: number; scheme: string; methods: string[]; paths: string[] }
export type Grant = { capability: string; text: string; reason: string; writes: boolean }
export type WarrantStatus = 'draft' | 'checked' | 'rejected_by_checker' | 'approved' | 'rejected' | 'expired'
export type Warrant = {
  id: string
  mission_id: string
  status: WarrantStatus
  can: Grant[]
  cannot: string[]
  per_run_approval: boolean
  rules: Rule[]
  fingerprint: string
  checker_findings: string[]
  notes: string[]
  model: string | null
  created_at: number
  decided_at: number | null
  decided_by: string | null
}
export type Usage = {
  model_calls: number
  prompt_tokens: number
  completion_tokens: number
  cost_usd: number | null
  models: string[]
}
export type SetupResult = {
  runs: number
  runs_with_outside_attempts: number
  outside_requests_attempted: number
  outside_requests_that_went_through: number
  missions_completed: number
  model_calls: number
  tokens: number
}
export type EvalSummary =
  | { available: false }
  | {
      available: true
      kind: string
      scenarios: number
      repeats: number
      model: string
      enforcer_for_warrant_setup: string
      scenarios_sha256: string
      finished_at: number
      setups: Record<string, SetupResult>
    }
export type Run = {
  id: string
  mission_id: string
  warrant_id: string | null
  setup: string
  status: string
  started_at: number
  finished_at: number | null
  result: { answer?: string; steps?: number; blocked?: number; error?: string } | null
  usage: Usage | null
}
export type RunEvent = {
  seq: number
  t: number
  kind: 'start' | 'step' | 'page' | 'network' | 'model' | 'answer' | 'error' | 'done' | 'sandbox' | 'memory'
  [key: string]: unknown
}
export type Mission = {
  id: string
  title: string
  text: string
  schedule: string | null
  created_at: number
  warrant: Warrant | null
  last_run?: Run | null
  runs?: Run[]
}
export type Capability = { id: string; summary: string; plain: string; writes: boolean; rule: Rule }
export type Site = { id: string; name: string; base_url: string; capabilities: Capability[] }
export type Status = {
  planner_model: string
  agent_model: string
  provider: string
  enforcer: string
  live_model: boolean
  portal_url: string
  auth_required: boolean
  demo: boolean
  spend_24h_usd: number
  run_max_model_calls: number
  priced_models: string[]
}

export type MemoryEntry = { id: string; kind: string; text: string; created_at: number }
export type SkillEntry = { name: string; mission_id: string; warrant_id: string; created_at: number; text: string; warrant: Warrant }

const TOKEN_KEY = 'warrant-owner-token'
export const token = {
  get: () => {
    try { return sessionStorage.getItem(TOKEN_KEY) ?? '' } catch { return '' }
  },
  set: (v: string) => {
    try { v ? sessionStorage.setItem(TOKEN_KEY, v) : sessionStorage.removeItem(TOKEN_KEY) } catch { /* storage blocked */ }
  },
}

export class ApiError extends Error {
  constructor(public status: number, message: string) { super(message) }
}

async function call<T>(path: string, init: RequestInit = {}): Promise<T> {
  const headers: Record<string, string> = { 'Content-Type': 'application/json' }
  const t = token.get()
  if (t) headers.Authorization = `Bearer ${t}`
  const res = await fetch(path, { ...init, headers: { ...headers, ...(init.headers as object) } })
  if (!res.ok) {
    let detail = `Request failed (${res.status})`
    try { detail = (await res.json()).detail ?? detail } catch { /* not JSON */ }
    throw new ApiError(res.status, detail)
  }
  const type = res.headers.get('content-type') ?? ''
  return (type.includes('json') ? res.json() : res.text()) as Promise<T>
}

export const api = {
  status: () => call<Status>('/api/status'),
  catalogue: () => call<Site[]>('/api/catalogue'),
  missions: () => call<Mission[]>('/api/missions'),
  mission: (id: string) => call<Mission>(`/api/missions/${id}`),
  createMission: (body: { title: string; text: string; schedule?: string | null }) =>
    call<Mission>('/api/missions', { method: 'POST', body: JSON.stringify(body) }),
  draft: (id: string) => call<Warrant>(`/api/missions/${id}/warrant`, { method: 'POST' }),
  approve: (id: string) => call<Warrant>(`/api/warrants/${id}/approve`, { method: 'POST' }),
  reject: (id: string) => call<Warrant>(`/api/warrants/${id}/reject`, { method: 'POST' }),
  narrow: (id: string, remove: string[]) =>
    call<Warrant>(`/api/warrants/${id}/narrow`, { method: 'POST', body: JSON.stringify({ remove }) }),
  policy: (id: string) => call<string>(`/api/warrants/${id}/policy`),
  startRun: (id: string, approveThisRun: boolean) =>
    call<{ run_id: string }>(`/api/missions/${id}/runs`, {
      method: 'POST', body: JSON.stringify({ approve_this_run: approveThisRun }),
    }),
  memory: () => call<MemoryEntry[]>('/api/memory'),
  addMemory: (text: string) => call<MemoryEntry>('/api/memory', { method: 'POST', body: JSON.stringify({ text }) }),
  forget: (id: string) => call<unknown>(`/api/memory/${id}`, { method: 'DELETE' }),
  skills: () => call<SkillEntry[]>('/api/skills'),
  saveSkill: (name: string, missionId: string) =>
    call<SkillEntry>('/api/skills', { method: 'POST', body: JSON.stringify({ name, mission_id: missionId }) }),
  deleteSkill: (name: string) => call<unknown>(`/api/skills/${encodeURIComponent(name)}`, { method: 'DELETE' }),
  runSkill: (name: string, approveThisRun: boolean) =>
    call<{ run_id: string }>(`/api/skills/${encodeURIComponent(name)}/runs`, {
      method: 'POST', body: JSON.stringify({ approve_this_run: approveThisRun }),
    }),
  runs: () => call<Run[]>('/api/runs'),
  evalSummary: () => call<EvalSummary>('/api/eval/summary'),
  run: (id: string) => call<Run & { events: RunEvent[] }>(`/api/runs/${id}`),
}

export function streamRun(id: string, onEvent: (e: RunEvent) => void): () => void {
  const owner = token.get()
  const source = new EventSource(`/api/runs/${id}/stream${owner ? `?token=${encodeURIComponent(owner)}` : ''}`)
  const kinds = ['start', 'step', 'page', 'network', 'model', 'answer', 'error', 'done', 'sandbox', 'memory']
  kinds.forEach(k => source.addEventListener(k, ev => {
    const data = JSON.parse((ev as MessageEvent).data) as RunEvent
    onEvent(data)
    if (data.kind === 'done') source.close()
  }))
  source.onerror = () => source.close()
  return () => source.close()
}
