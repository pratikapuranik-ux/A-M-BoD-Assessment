import type { View } from '../api/viewTypes'
import type { CompanySummary, FileKey, JourneyView, PriorActionStatus, PriorEntry } from '../api/types'

/** The journey pages read only a slice of the server's view; this narrows F2's View to it. */
export const asJourney = (v: View): JourneyView => v as unknown as JourneyView

export const PATHS = {
  setup: '/journey/setup',
  oi: '/journey/outside-in',
  ioInput: '/journey/inside-out',
  ioRun: '/journey/inside-out/run',
  ioRead: '/journey/inside-out/readout',
  actions: '/journey/actions',
} as const

/** The period defaults to the current calendar quarter until a company is opened. */
export const currentPeriod = (d = new Date()) => `${d.getFullYear()}-Q${Math.floor(d.getMonth() / 3) + 1}`
export const todayLabel = () => new Date().toLocaleDateString('en-GB', { weekday: 'long', day: 'numeric', month: 'long', year: 'numeric' })
export const greeting = () => { const h = new Date().getHours(); return h < 12 ? 'Good morning' : h < 18 ? 'Good afternoon' : 'Good evening' }
export const nameFromEmail = (e: string) => e.split('@')[0].split(/[._-]+/).filter(Boolean).map((w) => w[0].toUpperCase() + w.slice(1)).join(' ')
export const initials = (n: string) => n.split(/\s+/).filter(Boolean).map((x) => x[0]).slice(0, 2).join('').toUpperCase()
export const listJoin = (a: string[]) => (a.length < 2 ? a.join('') : a.slice(0, -1).join(', ') + ' and ' + a[a.length - 1])
export const coLabel = (c: { name?: string; ticker?: string }) => (c.name || '') + (c.ticker ? ` (${c.ticker})` : '')
export const EMAIL_RE = /^[^@\s]+@[^@\s]+\.[^@\s]+$/
export const PERIOD_RE = /^\d{4}-Q[1-4]$/
export const fmtStatus = (s: string) => s.replace(/_/g, ' ')

/** Earlier assessments the director picked for trend (at most two, oldest first, never the current period). */
export function selectedPriors(j: JourneyView | undefined, sel: string[]): PriorEntry[] {
  if (!j) return []
  return (j.priors || []).filter((p) => sel.includes(p.period) && p.period !== j.meta.period)
    .sort((a, b) => (a.period < b.period ? -1 : 1)).slice(-2)
}

/** The same view with only the picked earlier assessments, so the report shows just that trend. */
export function withPriors<T extends object>(view: T, sel: string[]): T {
  const j = view as unknown as JourneyView
  return { ...view, priors: selectedPriors(j, sel) } as T
}

/** Last quarter's actions with their status: from the inside-out run, else the latest picked earlier assessment. */
export function priorActionsList(j: JourneyView | undefined, sel: string[]): PriorActionStatus[] {
  if (!j) return []
  if (j.io?.prior_actions?.length) return j.io.prior_actions
  const hist = selectedPriors(j, sel), last = hist[hist.length - 1]
  const acts = (last?.actions || []) as { id?: string; heading: string; measures?: string[] }[]
  return acts.map((a) => ({
    id: a.id, heading: a.heading, status: 'no_public_evidence',
    note: 'Status needs the action tracker or minutes; none supplied in this run.', metrics: (a.measures || []).join('; '),
  }))
}

export function overallAvg(g?: { numeric_average?: number | null; avg?: number | null } | null): number | null {
  const v = g?.numeric_average ?? g?.avg
  return v == null ? null : v
}

/** Grade per dimension for a stage, or null where the server did not supply them. */
export function dimGrades(j: JourneyView, stage: 'oi' | 'io'): Record<string, string | null | undefined> | null {
  if (stage === 'io') {
    const d = j.io?.dims
    return d ? Object.fromEntries(Object.entries(d).map(([k, v]) => [k, v?.grade])) : null
  }
  const rows = (j.scorecard || []).filter((r) => /^\d+\./.test(r.dim))
  return rows.length ? Object.fromEntries(rows.map((r) => [r.dim.split('.')[0], r.grade])) : null
}

export function prevGradeArrow(now?: string | null, prev?: string | null): { dir: 'up' | 'dn' | 'same'; prev: string } | null {
  const L: Record<string, number> = { A: 5, B: 4, C: 3, D: 2, F: 1 }
  if (!now || !prev) return null
  const d = (L[now] || 0) - (L[prev] || 0)
  return { dir: d > 0 ? 'up' : d < 0 ? 'dn' : 'same', prev }
}

export interface BriefItem { id: string; title: string; meta: string; grade: string; files: [FileKey, string, string][]; prior?: boolean; urls: Partial<Record<FileKey, string>> }

export function briefItems(companies: CompanySummary[]): BriefItem[] {
  const out: BriefItem[] = []
  companies.forEach((c) => {
    const g = c.grades || {}, f = c.files || {}
    if (c.stages?.outside_in) {
      out.push({
        id: c.id, title: `${c.name} · ${c.period}`, urls: f,
        meta: (g.oi ? 'Outside-in ' + g.oi : '') + (g.io ? ' · after inside-out ' + g.io : ' · inside-out not yet run'),
        grade: g.io || g.oi || 'NA',
        files: ([['io_docx', 'Report (Word)', 'doc'], ['io_html', 'Dashboard (HTML)', 'web'], ['oi_docx', 'Outside-in (Word)', 'doc']] as [FileKey, string, string][]).filter((x) => f[x[0]]),
      })
    }
    if (c.prior_period && f.prior_docx) out.push({ id: c.id, title: `${c.name} · ${c.prior_period}`, meta: 'Earlier quarter, outside-in', grade: 'NA', files: [['prior_docx', 'Report (Word)', 'doc']], prior: true, urls: f })
  })
  return out
}

/** Trigger a browser download for a backend file URL. */
export function downloadUrl(url: string) {
  const a = document.createElement('a')
  a.href = url; a.download = ''
  document.body.appendChild(a); a.click(); a.remove()
}
