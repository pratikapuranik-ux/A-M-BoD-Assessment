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

/** Send one file's raw bytes to the server (never turned into a JavaScript string, so the browser's string limit does not apply);
 *  resolves to the id the research / inside-out request uses to refer to it.
 *  The file is read into memory first: handing fetch the File itself streams it lazily, and a file in a OneDrive-synced folder that
 *  syncs or changes while it streams makes the browser abort with a bare "Failed to fetch". A dropped connection is retried. */
export async function uploadFile(f: File): Promise<string> {
  let data: ArrayBuffer
  try { data = await f.arrayBuffer() } catch {
    throw new ApiError(`${f.name}: the browser could not read this file. If it is online-only in OneDrive, open it once or copy it to a local folder, then add it again.`, 0)
  }
  let r: Response | null = null, last = ''
  const waits = [1000, 2000, 4000, 6000, 8000]  // about 20 seconds in all: enough for the backend to come back after a restart
  for (let attempt = 0; attempt <= waits.length; attempt++) {
    try {
      r = await fetch('/api/uploads?name=' + enc(f.name), { method: 'POST', body: data, headers: { 'Content-Type': 'application/octet-stream' } })
      if (![500, 502, 503, 504].includes(r.status)) break  // a real answer (success, or a 4xx that retrying will not change)
      last = `the server answered ${r.status}`
    } catch (e) {
      r = null; last = (e as Error).message || 'network error'
    }
    if (attempt < waits.length) await new Promise((res) => setTimeout(res, waits[attempt]))
  }
  if (!r) throw new ApiError(`${f.name}: could not reach the server (${last}). Check that the BACKEND window is still open, then try again.`, 0)
  let j: any = null
  try { j = await r.json() } catch { /* empty or non-JSON body */ }
  if (!r.ok) throw new ApiError((j && (j.error || j.detail)) || `${f.name}: upload failed (${r.status})`, r.status)
  return j.upload_id as string
}

/** Every upload: at most 100 MB a file, or 500 MB for a .zip of documents (the server checks again). */
export const MAX_FILE = 100 * 2 ** 20
export const MAX_ZIP = 500 * 2 ** 20
export const isZip = (f: { name: string }) => /\.zip$/i.test(f.name)
