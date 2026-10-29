import { useNavigate } from 'react-router-dom'
import { Card, JobProgress, PageHead } from '../../components/ui'
import { toJobView, useJob } from '../../api/queries'
import { useInsideOut } from '../../store/insideOut'
import { useSession } from '../../store/session'
import { PATHS } from '../../lib/journey'
import type { JobView } from '../../api/types'

/** Live inside-out: documents and answers go to the backend, which scores them and returns the updated view. */
export default function StageRunPage() {
  const nav = useNavigate()
  const cid = useSession((s) => s.companyId)
  const run = useInsideOut((s) => (cid ? s.ioRuns[cid] : undefined))
  const { job, error } = useJob(run?.phase === 'job' ? run.jobId : undefined)
  if (!cid || !run) return null
  const polled = toJobView(job, run.error ? null : error, run.message)
  const view: JobView = run.error
    ? { status: 'error', progress: job?.progress ?? 0, message: job?.message ?? run.message, log: job?.log ?? [], error: run.error }
    : run.phase === 'uploading' ? { status: 'uploading', progress: 0, message: run.message || 'Uploading your material…', log: [] } : polled.view
  const problems = run.error ? run.problems ?? [] : polled.problems
  const back = () => { useInsideOut.getState().setIoRun(cid, null); nav(PATHS.ioInput) }
  return (
    <>
      <PageHead title="Reading the board’s own material" eyebrow="Stage 2 of 3"
        sub="Each document and the pooled self-assessment answers are read against the indicators they bear on and the grades are re-checked against the scoring rules. This can take several minutes." />
      <Card id="livecard" aria-live="polite"><JobProgress job={view} problems={problems} onBack={back} /></Card>
    </>
  )
}
