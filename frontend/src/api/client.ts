/** Fetch wrapper for the backend. Errors keep the server's own message ({error|detail}), problems list and job_id. */

export class ApiError extends Error {
  status: number
  problems: unknown[] | null
  jobId: string | null
  constructor(message: string, status: number, problems: unknown[] | null = null, jobId: string | null = null) {
    super(message)
    this.name = 'ApiError'
    this.status = status
    this.problems = problems
    this.jobId = jobId
  }
}

export async function api<T = unknown>(path: string, opts: RequestInit = {}): Promise<T> {
  let r: Response
  try {
    r = await fetch('/api' + path, { ...opts, headers: { 'Content-Type': 'application/json', ...(opts.headers || {}) } })
  } catch (e) {
    throw new ApiError((e as Error).message || 'Network error', 0)
  }
  let j: any = null
  try { j = await r.json() } catch { /* empty or non-JSON body */ }
  if (!r.ok) {
    throw new ApiError((j && (j.error || j.detail)) || `Request failed (${r.status})`, r.status, (j && j.problems) || null, (j && j.job_id) || null)
  }
  return j as T
}

export const post = <T = unknown>(path: string, body: unknown) => api<T>(path, { method: 'POST', body: JSON.stringify(body) })

/** Start a background job; if the server says one is already running (409 with its job_id), follow that one instead. */
export async function startJob(path: string, body: unknown): Promise<{ job_id: string; id?: string; attached?: boolean }> {
  try {
    return await post(path, body)
  } catch (e) {
    if (e instanceof ApiError && e.status === 409 && e.jobId) return { job_id: e.jobId, attached: true }
    throw e
  }
}

export const enc = encodeURIComponent

export function fileToB64(f: File): Promise<string> {
  return new Promise((res, rej) => {
    const r = new FileReader()
    r.onload = () => res(String(r.result).split(',')[1] || '')
    r.onerror = () => rej(r.error)
    r.readAsDataURL(f)
  })
}

/** Every upload: at most 25 MB a file (the server checks again). */
export const MAX_FILE = 25 * 2 ** 20
