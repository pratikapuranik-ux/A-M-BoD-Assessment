import { useEffect } from 'react'
import { useLocation, useNavigate } from 'react-router-dom'
import { keys, queryClient, useJob } from '../api/queries'
import { useInsideOut, type AddJob, type IoRun } from '../store/insideOut'
import { useSession } from '../store/session'
import { PATHS } from '../lib/journey'
import { api, enc } from '../api/client'
import type { View } from '../api/viewTypes'
import { toast } from './ui'

/** Follows the background jobs the director has started (they continue when the page is left) and applies their outcome once. */
export default function JobRunner() {
  const addJob = useInsideOut((s) => s.addJob)
  const ioRuns = useInsideOut((s) => s.ioRuns)
  return (
    <>
      {addJob && <AddJobWatcher job={addJob} />}
      {Object.entries(ioRuns).map(([cid, r]) => (r.phase === 'job' && r.jobId && !r.error ? <IoJobWatcher key={cid + r.jobId} cid={cid} run={r} /> : null))}
    </>
  )
}

function AddJobWatcher({ job }: { job: AddJob }) {
  const { job: j, error } = useJob(job.jobId)
  const nav = useNavigate()
  const loc = useLocation()
  useEffect(() => {
    const st = useInsideOut.getState()
    if (!st.addJob || st.addJob.jobId !== job.jobId || st.addJob.handled) return
    const failed = error || j?.status === 'error'
    if (failed) {
      st.setAddJob({ ...st.addJob, handled: true })
      const msg = error || j?.error || 'The job failed.'
      st.patchAdd({ busy: false, err: msg, problems: error ? null : (j?.problems as unknown[]) || null })
      st.setAddJob(null)
      if (loc.pathname !== PATHS.setup) toast(msg)
    } else if (j?.status === 'done') {
      st.setAddJob({ ...st.addJob, handled: true })
      void (async () => {
        const id = j.result?.company_id || j.result?.id || job.fallbackId
        try {
          if (!id) throw new Error('The company could not be found after the run.')
          await queryClient.invalidateQueries({ queryKey: keys.companies })
          const v = await queryClient.fetchQuery({ queryKey: keys.view(id), queryFn: () => api<View>(`/companies/${enc(id)}/view`), staleTime: 0 })
          // earlier assessments picked on the setup page stay selected if they are on file for this company
          const onFile = ((v as unknown as { priors?: { period: string }[] }).priors || []).map((p) => p.period)
          useSession.setState({ companyId: id, oiDone: true, seen3: false, priorSel: useSession.getState().priorSel.filter((p) => onFile.includes(p)) })
          const s = useInsideOut.getState()
          s.resetRun(); s.resetAdd('file'); s.setAddJob(null)
          nav(PATHS.oi)
          toast(((v as unknown as { meta: { company: string } }).meta.company || 'The company') + ' is ready.')
        } catch (e) {
          const s = useInsideOut.getState()
          s.setAddJob(null); s.patchAdd({ busy: false, err: (e as Error).message })
        }
      })()
    }
  }, [j, error]) // eslint-disable-line react-hooks/exhaustive-deps
  return null
}

function IoJobWatcher({ cid, run }: { cid: string; run: IoRun }) {
  const { job: j, error } = useJob(run.jobId)
  const nav = useNavigate()
  const loc = useLocation()
  useEffect(() => {
    const st = useInsideOut.getState()
    const cur = st.ioRuns[cid]
    if (!cur || cur.handled) return
    if (j && j.status !== 'done' && j.status !== 'error') st.patchIoRun(cid, { message: j.message })
    if (error || j?.status === 'error') {
      const msg = error || j?.error || 'The job failed.'
      st.patchIoRun(cid, { error: msg, problems: error ? null : (j?.problems as unknown[]) || null, handled: true })
      if (useSession.getState().companyId !== cid || !loc.pathname.startsWith(PATHS.ioRun)) toast(`Inside-out for ${run.label} did not finish: ${msg}`)
    } else if (j?.status === 'done') {
      st.patchIoRun(cid, { handled: true })
      void (async () => {
        try {
          await queryClient.invalidateQueries({ queryKey: ['company', cid] })
          await queryClient.invalidateQueries({ queryKey: keys.companies })
          await queryClient.fetchQuery({ queryKey: keys.view(cid), queryFn: () => api<View>(`/companies/${enc(cid)}/view`), staleTime: 0 })
        } catch { /* the readout will retry the load */ }
        useInsideOut.getState().setIoRun(cid, null)
        if (useSession.getState().companyId === cid && window.location.pathname.startsWith(PATHS.ioRun)) nav(PATHS.ioRead)
        else toast(`Inside-out for ${run.label} is ready.`)
      })()
    }
  }, [j, error]) // eslint-disable-line react-hooks/exhaustive-deps
  return null
}
