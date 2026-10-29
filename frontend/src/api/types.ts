/** Wire types for the HTTP API (same contract as the legacy server/app.py). The report "view" model itself is
 *  defined by F2 in ./viewTypes.ts; `JourneyView` below is only the narrow slice of it that the journey pages read. */

export type RunMode = 'director_request' | 'internal_dry_run' | 'methodology_pilot' | string

export interface Health {
  ok: boolean
  research?: { enabled: boolean; reason: string }
}

export type FileKey = 'oi_docx' | 'oi_html' | 'io_docx' | 'io_html' | 'prior_docx' | 'quest'

export interface CompanySummary {
  id: string
  name: string
  short: string
  ticker: string
  period: string
  peers: string[]
  stages: { outside_in: boolean; inside_out: boolean }
  grades: { oi?: string | null; io?: string | null }
  labels: { oi?: string | null; io?: string | null }
  avg?: { oi?: number | null; io?: number | null }
  has_prior?: boolean
  prior_period?: string | null
  source: 'research' | 'imported' | string
  mode?: string
  updated?: string | null
  files: Partial<Record<FileKey, string>>
  problems?: unknown[]
}

export type JobStatus = 'queued' | 'running' | 'done' | 'error'

export interface Job {
  id?: string
  kind?: string
  status: JobStatus
  progress: number
  message: string
  log: string[]
  error?: string | null
  problems?: unknown[]
  result?: { company_id?: string; id?: string; warnings?: unknown[] } | null
}

/** Job state as the UI shows it, which also covers the client-side phase before the server has a job. */
export interface JobView {
  status: JobStatus | 'uploading'
  progress: number
  message: string
  log: string[]
  error?: string | null
}

export interface StartedJob {
  job_id: string
  id?: string
  attached?: boolean
}

export interface SurveyInvite {
  token: string
  email: string
  created: string
  responded: boolean
  link: string
}

export interface SurveyStatus {
  invites: SurveyInvite[]
  responses: number
  count?: number
  min: number
  can_generate?: boolean
  reason?: string | null
  local?: boolean
}

export interface UploadDoc {
  slot?: number
  name: string
  mime: string
  data_b64: string
}

export interface ResearchBody {
  company: string
  ticker: string
  peers: { name: string; ticker: string }[]
  period: string
  mode: string
  documents: UploadDoc[]
}

export interface ImportBody {
  outside_in: unknown
  inside_out?: unknown
  priors?: unknown[]
  replace?: boolean
}

export interface InsideOutBody {
  mode: string
  documents: UploadDoc[]
}

export interface PaperResponseBody {
  answers: Record<number, string>
  ratings: Record<string, number>
}

export interface GradeSummary {
  grade?: string | null
  label?: string
  numeric_average?: number | null
  avg?: number | null
  provisional?: boolean
}

export interface JourneyAction {
  n: string
  heading: string
  description: string
  measures?: string[]
  target?: string
}

export interface PriorActionStatus {
  id?: string | null
  heading: string
  status: string
  note?: string
  metrics?: string
}

export interface BackOnTrack {
  id?: string | null
  heading: string
  what: string
  cause: string
  prevent: string
}

export interface PriorEntry {
  period: string
  stage: 'outside_in' | 'inside_out' | string
  scores?: Record<string, number | null>
  grade?: string | null
  overall?: GradeSummary | null
  actions?: unknown[]
}

/** The slice of the server's view that the journey pages use. */
export interface JourneyView {
  meta: { id?: string; company: string; short: string; ticker: string; period: string; peers: string[]; peer_short: string[]; mode?: string; source?: string }
  actions: JourneyAction[]
  addl: string[]
  docs: [string, string][]
  q: [string, ...string[]][]
  modes: Record<string, string>
  scale: { min: number; grade: string; label: string }[]
  scorecard: { dim: string; grade?: string | null; line: string }[]
  findings_oi: string[]
  findings_io: string[]
  overall: { oi?: GradeSummary; io?: GradeSummary }
  files: Partial<Record<FileKey, string>>
  priors: PriorEntry[]
  prior: unknown
  io: null | {
    actions: JourneyAction[]
    prior_actions?: PriorActionStatus[]
    back?: BackOnTrack[]
    dims?: Record<string, { grade?: string | null }>
  }
}
