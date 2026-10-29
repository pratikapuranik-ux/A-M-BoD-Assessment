/** TanStack Query hooks, one per backend endpoint. Server state lives here; client/draft state is in store/*. */
import { QueryClient, useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { api, ApiError, enc, post, startJob } from './client'
import type {
  CompanySummary, Health, ImportBody, InsideOutBody, Job, PaperResponseBody, ResearchBody, StartedJob, SurveyStatus,
} from './types'
import type { View } from './viewTypes'

export const queryClient = new QueryClient({ defaultOptions: { queries: { refetchOnWindowFocus: false, staleTime: 15_000, retry: 1 } } })

export const POLL_MS = 1500
export const SURVEY_POLL_MS = 6000

export const keys = {
  health: ['health'] as const,
  framework: ['framework'] as const,
  companies: ['companies'] as const,
  view: (id: string, mode?: string | null) => ['company', id, 'view', mode ?? null] as const,
  survey: (id: string) => ['company', id, 'survey'] as const,
  job: (id: string) => ['job', id] as const,
}

/* ---------- reference data ---------- */
export const useHealth = () =>
  useQuery({ queryKey: keys.health, queryFn: () => api<Health>('/health'), retry: false, staleTime: 30_000 })

export const useFramework = (enabled = true) =>
  useQuery({ queryKey: keys.framework, queryFn: () => api<Record<string, unknown>>('/framework'), enabled, staleTime: Infinity })

/* ---------- companies ---------- */
export const useCompanies = (enabled = true) =>
  useQuery({ queryKey: keys.companies, queryFn: () => api<CompanySummary[]>('/companies'), enabled })

/** One company's view (the report model, graded by the server). */
export const useCompanyView = (id: string | null | undefined, mode?: string | null) =>
  useQuery({
    queryKey: keys.view(id || '', mode),
    queryFn: () => api<View>(`/companies/${enc(id!)}/view` + (mode ? `?mode=${enc(mode)}` : '')),
    enabled: !!id,
  })

export const useDeleteCompany = () => {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (id: string) => api<{ ok: boolean; id: string }>(`/companies/${enc(id)}`, { method: 'DELETE' }),
    onSuccess: (_r, id) => {
      qc.removeQueries({ queryKey: ['company', id] })
      return qc.invalidateQueries({ queryKey: keys.companies })
    },
  })
}

/* ---------- starting jobs ---------- */
export const useStartResearch = () => useMutation({ mutationFn: (body: ResearchBody) => startJob('/research', body) })
export const useImportCompany = () => useMutation({ mutationFn: (body: ImportBody) => startJob('/companies/import', body) })
export const startInsideOutJob = (cid: string, body: InsideOutBody): Promise<StartedJob> => startJob(`/companies/${enc(cid)}/inside-out`, body)

/* ---------- job polling ---------- */
const NOT_FOUND_MSG = 'The assessment service was restarted, so this run stopped before it finished. Nothing was saved; please start it again.'
const LOST_MSG = 'Lost contact with the assessment service. Check that it is running, then start the run again.'

/** Follow a background job every 1.5 s until it is done or has failed. A brief network drop is retried for about a minute;
 *  a job the server no longer knows (it was restarted, which ends running jobs) is reported in plain words. */
export function useJob(jobId: string | null | undefined) {
  const q = useQuery({
    queryKey: keys.job(jobId || ''),
    enabled: !!jobId,
    queryFn: async () => {
      try {
        return await api<Job>(`/jobs/${enc(jobId!)}`)
      } catch (e) {
        if (e instanceof ApiError && (e.status === 404 || /not found/i.test(e.message))) throw new ApiError(NOT_FOUND_MSG, 404)
        throw e
      }
    },
    retry: (count, err) => !(err instanceof ApiError && err.status === 404) && count < 40,
    retryDelay: POLL_MS,
    refetchInterval: (query) => {
      const s = query.state.data?.status
      if (s === 'done' || s === 'error' || query.state.error) return false
      return POLL_MS
    },
    refetchIntervalInBackground: true,
    gcTime: 5 * 60_000,
    staleTime: 0,
  })
  const err = q.error ? (q.error instanceof ApiError && q.error.status === 404 ? q.error.message : LOST_MSG) : null
  return { job: q.data ?? null, error: err, query: q }
}

/** Adapt a polled job (or its failure) to what the progress UI shows. */
export function toJobView(job: Job | null, error: string | null, fallbackMsg = 'Queued'): { view: import('./types').JobView; problems: unknown[] } {
  if (error) return { view: { status: 'error', progress: job?.progress ?? 0, message: job?.message ?? '', log: job?.log ?? [], error }, problems: [] }
  if (!job) return { view: { status: 'queued', progress: 1, message: fallbackMsg, log: [] }, problems: [] }
  return {
    view: { status: job.status, progress: job.progress, message: job.message, log: job.log || [], error: job.status === 'error' ? job.error || 'The job failed.' : null },
    problems: job.status === 'error' ? job.problems || [] : [],
  }
}

/* ---------- board self-assessment ---------- */
export const useSurvey = (id: string | null | undefined, poll = false) =>
  useQuery({
    queryKey: keys.survey(id || ''),
    queryFn: () => api<SurveyStatus>(`/companies/${enc(id!)}/survey`),
    enabled: !!id,
    // responses arrive while the page is open (useful in a demo): refresh the count every few seconds
    refetchInterval: poll ? () => (typeof document !== 'undefined' && document.hidden ? false : SURVEY_POLL_MS) : false,
  })

const setSurvey = (qc: QueryClient, id: string, v: SurveyStatus) => qc.setQueryData(keys.survey(id), v)

export const useInvite = (id: string) => {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (emails: string[]) => post<SurveyStatus>(`/companies/${enc(id)}/survey/invite`, { emails }),
    onSuccess: (v) => setSurvey(qc, id, v),
  })
}

export const useUninvite = (id: string) => {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (token: string) => api<SurveyStatus>(`/companies/${enc(id)}/survey/invite/${enc(token)}`, { method: 'DELETE' }),
    onSuccess: (v) => setSurvey(qc, id, v),
  })
}

/** A returned Word questionnaire, stored as one more anonymous response. */
export const postPaperResponse = (id: string, body: PaperResponseBody) =>
  post<SurveyStatus>(`/companies/${enc(id)}/survey/responses`, body)

/** Respondent's public page (F2's Survey.tsx may call these or its own). */
export const useSurveyForm = (token: string | undefined) =>
  useQuery({ queryKey: ['survey-form', token], queryFn: () => api<unknown>(`/survey/${enc(token!)}`), enabled: !!token, retry: false })
export const useSubmitSurvey = (token: string) =>
  useMutation({ mutationFn: (body: { answers: Record<string, string>; ratings: Record<string, number> }) => post<{ ok: boolean }>(`/survey/${enc(token)}`, body) })



