/** Imperative journey actions shared by pages (they read/write the stores directly, outside React render). */
import { ApiError, api, enc, isZip, MAX_FILE, MAX_ZIP, startJob, uploadFile } from '../api/client'
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

const limitOf = (f: File) => (isZip(f) ? MAX_ZIP : MAX_FILE)

/** Every upload: at most 100 MB a file, or 500 MB for a .zip (the server checks again). Returns the files that fit. */
export function sizeOk(files: File[]): File[] {
  const big = files.filter((f) => f.size > limitOf(f))
  if (big.length) toast(listJoin(big.map((f) => f.name)) + `: over the ${big.some(isZip) ? '500 MB limit per zip and 100 MB' : '100 MB limit'} per file, so not added.`)
  return files.filter((f) => f.size <= limitOf(f))
}

/** Send files to the server one request each, three at a time; resolves to their upload ids in the order given.
 *  Nothing is held in memory beyond the files themselves, so the number and total size of files is not limited by the browser. */
async function stage(files: File[], onProgress?: (done: number, total: number) => void): Promise<string[]> {
  const ids: string[] = new Array(files.length)
  let next = 0, done = 0
  const worker = async () => {
    while (next < files.length) { const i = next++; ids[i] = await uploadFile(files[i]); onProgress?.(++done, files.length) }
  }
  const lanes = files.some((f) => f.size > 100 * 2 ** 20) ? 1 : 3  // a big zip is read into memory whole: do not hold several at once
  await Promise.all(Array.from({ length: Math.min(lanes, files.length) }, worker))
  return ids
}

/* ---------- outside-in: research or import (job follows in JobRunner) ---------- */
const fail = (err: string, problems: unknown[] | null = null) => useInsideOut.getState().patchAdd({ err, problems, busy: false, msg: '' })

export async function startResearch(mode: string) {
  const io = useInsideOut.getState(), A = io.add
  const peers = A.peers.filter((p) => p.name.trim())
  if (!useSession.getState().listed) return fail('Please confirm the company and its peers are listed.')
  if (!A.company.trim() || !A.ticker.trim()) return fail('Enter the company name and ticker.')
  if (peers.length < 2) return fail('Add at least two peers.')
  if (!PERIOD_RE.test(A.period.trim())) return fail('Period must look like 2026-Q4.')
  io.patchAdd({ busy: true, err: '', problems: null, msg: A.files.length ? 'Preparing your documents…' : 'Starting the assessment…' })
  try {
    const files = A.files.filter((f) => f.subject !== -1)  // -1: in the folder of a company that is not in this assessment
    const ids = await stage(files.map((f) => f.file), (d, t) => useInsideOut.getState().patchAdd({ msg: `Uploading your documents… ${d} of ${t} files` }))
    useInsideOut.getState().patchAdd({ msg: 'Starting the assessment…' })
    const documents: UploadDoc[] = files.map((f, i) => ({ name: f.path || f.name, mime: f.file.type, upload_id: ids[i], ...(f.subject !== undefined ? { subject: f.subject } : {}) }))
    const r = await startJob('/research', {
      company: A.company.trim(), ticker: A.ticker.trim().toUpperCase(),
      peers: peers.map((p) => ({ name: p.name.trim(), ticker: p.ticker.trim().toUpperCase() })), period: A.period.trim(), mode, documents,
    })
    useInsideOut.getState().setAddJob({ jobId: r.job_id, kind: 'research', handled: false })
    useInsideOut.getState().patchAdd({ busy: false, msg: '' })
  } catch (e) { fail((e as Error).message, (e as ApiError).problems ?? null) }
}

export async function startImport() {
  const io = useInsideOut.getState(), A = io.add
  if (A.busy || io.addJob) return
  io.patchAdd({ busy: true, err: '', problems: null })
  const { importOi: oi, importIo: ioF, importPr: pr } = A
  if (!oi) return fail('Choose the outside-in assessment file.')
  const big = [oi, ioF, ...pr].filter((x): x is File => !!x && x.size > MAX_FILE)
  if (big.length) return fail(listJoin(big.map((x) => x.name)) + ': over the 100 MB limit per file.')
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
    const items = [...slots.map(([n, f]) => ({ slot: n, f })), ...other.map((f) => ({ slot: 0, f }))]
    const ids = await stage(items.map((x) => x.f.file), (d, t) => useInsideOut.getState().patchIoRun(cid, { message: `Uploading your material… ${d} of ${t} files` }))
    const docs: UploadDoc[] = items.map((x, i) => ({ slot: x.slot, name: x.f.name, mime: x.f.file.type, upload_id: ids[i] }))
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

