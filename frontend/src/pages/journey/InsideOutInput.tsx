import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { Card, Chip, Meter, Notice, PageHead, NextButton } from '../../components/ui'
import { useJourney } from '../../lib/useJourney'
import { sizeOk, startInsideOutRun } from '../../lib/actions'
import { FILE_ACCEPT } from '../../lib/constants'
import { PATHS } from '../../lib/journey'
import { useInsideOut } from '../../store/insideOut'
import { FileChips } from './parts'
import SurveyCard, { useSurveyNow } from './SurveyCard'

/** Stage 2 input: board documents, other information and the anonymous self-assessment, with live readiness. */
export default function InsideOutInput() {
  const nav = useNavigate()
  const { session, apiOn, research, j, ioDone, ioBusy } = useJourney()
  const cid = session.companyId
  const docs = useInsideOut((s) => s.docs)
  const other = useInsideOut((s) => s.other)
  const qFiles = useInsideOut((s) => s.qFiles)
  const { v, n, count, loaded } = useSurveyNow(cid || '', true)
  const [msg, setMsg] = useState('')
  if (!j || !cid) return <p className="muted">Loading…</p>

  const canRun = apiOn && research.enabled
  const provided = j.docs.filter((_, i) => (docs[i + 1] || []).length > 0).length
  const base = apiOn && research.enabled && n >= v.min
  /* The server says whether the inside-out view can be prepared (can_generate, with its reason). Returned questionnaires are
     uploaded when the run starts, so a shortfall in the count alone is made up by those waiting here. */
  const canGenerate = ioBusy ? false : !loaded || typeof v.can_generate !== 'boolean' ? base : v.can_generate || (qFiles.length > 0 && count < v.min && base)
  const why = canGenerate || ioBusy ? '' : (loaded && v.reason) || ''

  const start = () => {
    if (n < v.min) return setMsg(`At least ${v.min} self-assessment responses are needed; ${n} so far.`)
    setMsg('')
    void startInsideOutRun(cid, j.meta.company, session.mode)
    nav(PATHS.ioRun)
  }

  return (
    <>
      <PageHead title="Inside-out: add what only the board can see" sub="Board documents carry more weight than public sources. Grades change only where something you supply settles an indicator." eyebrow="Stage 2 of 3" />
      {ioDone && <Notice kind="ok"><b>An inside-out assessment for {j.meta.period} is already on file.</b> Open it, or add new material below to run it again. <Link className="btn sm" style={{ marginLeft: 10 }} to={PATHS.ioRead}>Open the readout</Link></Notice>}
      {!canRun && <Notice>Scoring of your own board documents is not available in this version. Your A&amp;M engagement team can run the inside-out stage with you.</Notice>}
      <Card className="acc">
        <h3>What would move the assessment most</h3>
        <p className="muted">Your material is used only for this company’s assessment, cited by document and date (never by person), and never used to assess a peer. Where public evidence is thin or inferred:</p>
        <ul className="flist">{(j.addl || []).length ? j.addl.map((x, i) => <li key={i}>{x.replace(/^•\s*/, '')}</li>) : <li>Board and committee minutes and board packs settle the most indicators.</li>}</ul>
        <p className="muted m0">The first seven documents below settle the most indicators.</p>
      </Card>

      <Card className="acc">
        <h3>1. Board documents</h3>
        <div id="meter"><Meter pct={(provided / (j.docs.length || 1)) * 100} /><div className="muted">{provided} of {j.docs.length} documents provided</div></div>
        <p className="ks">PDF, Word or text files, up to 25 MB each.</p>
        <div className="scroll"><table className="tbl"><thead><tr><th style={{ width: 70 }}>Provided</th><th>Document</th><th>Indicators it informs</th><th>File</th></tr></thead><tbody>
          {j.docs.map((d, i) => {
            const slot = i + 1, files = docs[slot] || []
            return (
              <tr key={slot}>
                <td><input type="checkbox" checked={files.length > 0} readOnly disabled aria-label={`Document ${slot} provided`} /></td>
                <td>{slot}. {d[0]}{slot <= 7 && <> <span className="chip">priority</span></>}</td>
                <td>{String(d[1] || '').split(' ').filter(Boolean).map((x) => <span className="chip" key={x}>{x}</span>)}</td>
                <td>
                  <input type="file" accept={FILE_ACCEPT} multiple className="fileinput" aria-label={`Add files for document ${slot}`} value=""
                    onChange={(e) => useInsideOut.getState().addDocFiles(slot, sizeOk(Array.from(e.target.files || [])).map((f) => ({ name: f.name, file: f })))} />
                  <FileChips files={files} onRemove={(k) => useInsideOut.getState().removeDocFile(slot, k)} />
                </td>
              </tr>)
          })}
        </tbody></table></div>
      </Card>

      <Card className="acc">
        <h3>2. Other information</h3>
        <p className="muted">Anything else that bears on how the board works: committee papers, advisor reports, investor correspondence. Listed in the report’s sources. Up to 25 MB per file.</p>
        <div className="frow"><input type="file" id="otherfiles" multiple accept={FILE_ACCEPT} className="fileinput" aria-label="Other information" value=""
          onChange={(e) => useInsideOut.getState().addOther(sizeOk(Array.from(e.target.files || [])).map((f) => ({ name: f.name, file: f })))} /></div>
        <div className="chips">{other.map((f, i) => <Chip key={f.name + i} label="Remove" onRemove={() => useInsideOut.getState().removeOther(i)}>{f.name}</Chip>)}</div>
      </Card>

      <SurveyCard cid={cid} j={j} apiOn={apiOn} />

      <div className="row sb">
        <Link className="btn sec" to={PATHS.oi}>Back to outside-in readout</Link>
        <div className="row"><span className="muted err" role="alert">{msg}</span><NextButton size="lg" disabled={!canGenerate} onClick={start}>Generate inside-out assessment</NextButton></div>
      </div>
      <p className="ks iowhy" aria-live="polite">{why}</p>
    </>
  )
}

