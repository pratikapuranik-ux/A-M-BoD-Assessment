import { Link } from 'react-router-dom'
import { Icon } from '../../components/Icon'
import { DlButton, PageHead } from '../../components/ui'
import { useJourney } from '../../lib/useJourney'
import { listJoin, PATHS, withPriors } from '../../lib/journey'
import ReportView from '../../report/ReportView'
import { ActionCard, DeliveryCard, DownloadGroup, NextCard, PlanButton, PriorCard, StickyNext } from './parts'

/** The readout of one stage: grades, headline findings, actions, downloads and the full report. */
export default function StageSummary({ stage }: { stage: 'oi' | 'io' }) {
  const { j, raw, session } = useJourney()
  if (!j || !raw) return <p className="muted">Loading…</p>
  const files = j.files
  const report = <ReportView view={withPriors(raw, session.priorSel)} mode={stage === 'io' ? 'inside_out' : 'outside_in'} />

  if (stage === 'oi') {
    return (
      <>
        <PageHead title="Outside-in readout" sub={`${j.meta.company} against ${listJoin(j.meta.peer_short || [])} · public information only`}
          right={<><PlanButton stage="oi" j={j} /><DlButton files={files} k="oi_docx" label="Report (Word)" icon="doc" /></>} eyebrow="Stage 1 of 3 · complete" />
        <DeliveryCard stage="oi" j={j} />
        <PriorCard j={j} fresh={false} />
        <h2 className="sech">What the board could do next</h2>
        <p className="muted">Five actions from the outside-in assessment. The inside-out stage tests them against the board’s own material and refines them into the final five.</p>
        {j.actions.map((a) => <ActionCard key={a.n} a={a} />)}
        <h2 className="sech">Detailed report</h2>
        {report}
        <NextCard title="Next: inside-out" text="Add board documents and invite directors to an anonymous self-assessment. Grades are refined where that material settles an indicator, and the five actions are refined with them."
          to={PATHS.ioInput} label="Continue to inside-out" />
        <StickyNext text="Next: add the board’s own material" to={PATHS.ioInput} label="Continue to inside-out" />
      </>
    )
  }

  const anyDl = (...k: (keyof typeof files)[]) => k.some((x) => files?.[x])
  return (
    <>
      <PageHead title="Your board assessment" sub={`${j.meta.company} · ${j.meta.period} · complete and saved to your Briefcase`}
        right={<PlanButton stage="io" j={j} />} eyebrow="Stage 2 of 3 · complete" />
      <DeliveryCard stage="io" j={j} />
      {anyDl('io_docx', 'io_html', 'oi_docx', 'oi_html', 'prior_docx', 'quest') && (
        <>
          <h2 className="sech">Download the readout</h2>
          <div className="grid3">
            {anyDl('io_docx', 'io_html') && <DownloadGroup title="Board assessment" sub="Both grades side by side, peer comparison, updated actions and sources."><DlButton files={files} k="io_docx" label="Report (Word)" icon="doc" /><DlButton files={files} k="io_html" label="Dashboard (HTML)" icon="web" /></DownloadGroup>}
            {anyDl('oi_docx', 'oi_html') && <DownloadGroup title="Outside-in view" sub="The public-information report for the same period."><DlButton files={files} k="oi_docx" label="Report (Word)" icon="doc" /><DlButton files={files} k="oi_html" label="Dashboard (HTML)" icon="web" /></DownloadGroup>}
            {anyDl('prior_docx', 'quest') && <DownloadGroup title="Supporting files" sub="The earlier-quarter report and the director questionnaire."><DlButton files={files} k="prior_docx" label="Earlier quarter (Word)" icon="doc" /><DlButton files={files} k="quest" label="Questionnaire (Word)" icon="doc" /></DownloadGroup>}
          </div>
        </>
      )}
      <h2 className="sech">Detailed report</h2>
      {report}
      <NextCard title="Next: the board’s five actions" text="The outside-in actions, refined by what the board’s own material and the directors’ self-assessment showed." to={PATHS.actions} label="See the board’s five actions" />
      <div className="row" style={{ marginBottom: 20 }}><Link className="btn sec" to={PATHS.ioInput}><Icon name="upload" size={16} />Add more material and run again</Link></div>
      <StickyNext text="Next: the board’s five actions" to={PATHS.actions} label="See the board’s five actions" />
    </>
  )
}

