/** Imperative journey actions shared by pages (they read/write the stores directly, outside React render). */
import { ApiError, api, enc, fileToB64, MAX_FILE, startJob } from '../api/client'
import { keys, postPaperResponse, queryClient, startInsideOutJob } from '../api/queries'
import type { UploadDoc } from '../api/types'
import { PERIOD_RE, listJoin, asJourney } from './journey'
import type { JourneyView } from '../api/types'
import type { View } from '../api/viewTypes'
import { useSession } from '../store/session'
import { useInsideOut } from '../store/insideOut'
import { toast } from '../components/ui'

/** Open a company: load its view (so a failure is reported here) and start a fresh run on it. Resolves to the view, or null. */
export async function openCompany(id: string): Promise<JourneyView | null> {
  let v: View
  try {
    v = await queryClient.fetchQuery({ queryKey: keys.view(id), queryFn: () => api<View>(`/companies/${enc(id)}/view`), staleTime: 0 })
  } catch (e) {
    toast('Could not open the company: ' + (e as Error).message)
    return null
  }
  const s = useSession.getState()
  if (!(id === s.companyId && s.oiDone)) { s.selectCompany(id); useInsideOut.getState().resetRun() }
  return asJourney(v)
}
/** New assessment: the selected company stays, the run is reset. Keeps a research/import in progress. */
export function freshAssessment() {
  const io = useInsideOut.getState()
  if (!(io.add.busy || io.addJob)) { useSession.getState().startFresh(); io.resetRun(); io.resetAdd() }
}
export const addBusy = () => { const io = useInsideOut.getState(); return !!(io.add.busy || io.addJob) }

/** Every upload: at most 25 MB a file (the server checks again). Returns the files that fit. */
export function sizeOk(files: File[]): File[] {
  const big = files.filter((f) => f.size > MAX_FILE)
  if (big.length) toast(listJoin(big.map((f) => f.name)) + ': over the 25 MB limit per file, so not added.')
  return files.filter((f) => f.size <= MAX_FILE)
}

/* ---------- outside-in: research or import (job follows in JobRunner) ---------- */
const fail = (err: string, problems: unknown[] | null = null) => useInsideOut.getState().patchAdd({ err, problems, busy: false })

export async function startResearch(mode: string) {
  const io = useInsideOut.getState(), A = io.add
  const peers = A.peers.filter((p) => p.name.trim())
  if (!useSession.getState().listed) return fail('Please confirm the company and its peers are listed.')
  if (!A.company.trim() || !A.ticker.trim()) return fail('Enter the company name and ticker.')
  if (peers.length < 2) return fail('Add at least two peers.')
  if (!PERIOD_RE.test(A.period.trim())) return fail('Period must look like 2026-Q4.')
  io.patchAdd({ busy: true, err: '', problems: null })
  try {
    const documents: UploadDoc[] = []
    for (const f of A.files) documents.push({ name: f.name, mime: f.file.type, data_b64: await fileToB64(f.file) })
    const r = await startJob('/research', {
      company: A.company.trim(), ticker: A.ticker.trim().toUpperCase(),
      peers: peers.map((p) => ({ name: p.name.trim(), ticker: p.ticker.trim().toUpperCase() })), period: A.period.trim(), mode, documents,
    })
    useInsideOut.getState().setAddJob({ jobId: r.job_id, kind: 'research', handled: false })
    useInsideOut.getState().patchAdd({ busy: false })
  } catch (e) { fail((e as Error).message, (e as ApiError).problems ?? null) }
}

export async function startImport() {
  const io = useInsideOut.getState(), A = io.add
  if (A.busy || io.addJob) return
  io.patchAdd({ busy: true, err: '', problems: null })
  const { importOi: oi, importIo: ioF, importPr: pr } = A
  if (!oi) return fail('Choose the outside-in assessment file.')
  const big = [oi, ioF, ...pr].filter((x): x is File => !!x && x.size > MAX_FILE)
  if (big.length) return fail(listJoin(big.map((x) => x.name)) + ': over the 25 MB limit per file.')
  const read = async (x: File) => JSON.parse(await x.text())
  let body: { outside_in: unknown; inside_out?: unknown; priors?: unknown[] }
  try {
    body = { outside_in: await read(oi) }
    if (ioF) body.inside_out = await read(ioF)
    if (pr.length) body.priors = await Promise.all(pr.slice(0, 4).map(read))
  } catch (e) { return fail('One of the files is not valid JSON: ' + (e as Error).message) }
  try {
    const r = await startJob('/companies/import', body)
    useInsideOut.getState().setAddJob({ jobId: r.job_id, kind: 'import', fallbackId: r.id, handled: false })
    useInsideOut.getState().patchAdd({ busy: false })
  } catch (e) { fail((e as Error).message, (e as ApiError).problems ?? null) }
}

/* ---------- inside-out ---------- */
/** Returned Word questionnaires become anonymous responses when the inside-out run starts. Each file leaves the list as soon
 *  as it is stored, so a retry never posts it twice; a duplicate or empty return is dropped. */
async function sendPaperReturns(cid: string) {
  const io = useInsideOut.getState()
  for (const f of io.qFiles.slice()) {
    const answers: Record<number, string> = {}
    f.answers.forEach((x, i) => { answers[i + 1] = x || '' })
    try {
      const v = await postPaperResponse(cid, { answers, ratings: f.ratings })
      useInsideOut.getState().dropQFile(f)
      queryClient.setQueryData(keys.survey(cid), v)
    } catch (e) {
      const err = e as ApiError
      if (err.status === 409 && /already/i.test(err.message)) { useInsideOut.getState().dropQFile(f); toast(f.name + ' has already been added, so it was not counted again.') }
      else if (err.status === 400 && /empty|at least one/i.test(err.message)) { useInsideOut.getState().dropQFile(f); toast(f.name + ' has no answers, so it was not added.') }
      else throw e
    }
  }
}

/** Documents and answers go to the backend, which scores them. The run belongs to its company: JobRunner follows the job. */
export async function startInsideOutRun(cid: string, label: string, mode: string) {
  const io = useInsideOut.getState()
  const cur = io.ioRuns[cid]
  if (cur && !cur.error) return
  const slots = Object.entries(io.docs).flatMap(([n, fs]) => fs.map((f) => [Number(n), f] as const)), other = io.other.slice()
  io.setIoRun(cid, { phase: 'uploading', message: 'Uploading your material…', handled: false, label })
  try {
    const docs: UploadDoc[] = []
    for (const [n, f] of slots) docs.push({ slot: n, name: f.name, mime: f.file.type, data_b64: await fileToB64(f.file) })
    for (const f of other) docs.push({ slot: 0, name: f.name, mime: f.file.type, data_b64: await fileToB64(f.file) })
    await sendPaperReturns(cid)
    const r = await startInsideOutJob(cid, { mode, documents: docs })
    useInsideOut.getState().patchIoRun(cid, { phase: 'job', jobId: r.job_id, message: 'Queued' })
  } catch (e) {
    const msg = (e as Error).message
    useInsideOut.getState().patchIoRun(cid, { error: msg, problems: (e as ApiError).problems ?? null, handled: true })
    if (useSession.getState().companyId !== cid) toast(`Inside-out for ${label} did not finish: ${msg}`)
  }
}

export const ioUploadedCount = (docs: Record<number, { name: string }[]>) => Object.values(docs).filter((d) => d.length > 0).length

