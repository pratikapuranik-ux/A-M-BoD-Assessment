import { useNavigate, Link } from 'react-router-dom'
import { Button, Card, Collapsible, JobProgress, Notice, NextButton, PageHead, SegTabs, fmtProblem, toast } from '../../components/ui'
import { useJob, toJobView } from '../../api/queries'
import { useJourney } from '../../lib/useJourney'
import { openCompany, sizeOk, startImport, startResearch } from '../../lib/actions'
import { coLabel, PATHS } from '../../lib/journey'
import { FILE_ACCEPT, MAX_OI_DOCS, MAX_PEERS } from '../../lib/constants'
import { useInsideOut, type AddTab } from '../../store/insideOut'
import { useSession } from '../../store/session'
import { FileChips, PriorCard } from './parts'

function AddJobView() {
  const jobId = useInsideOut((s) => s.addJob?.jobId)
  const { job, error } = useJob(jobId)
  const { view, problems } = toJobView(job, error)
  return <JobProgress job={view} problems={problems} />
}

export default function OutsideInSetup() {
  const nav = useNavigate()
  const { session, apiOn, research, companies, j } = useJourney()
  const A = useInsideOut((s) => s.add)
  const addJob = useInsideOut((s) => s.addJob)
  const patch = useInsideOut((s) => s.patchAdd)
  const listed = useSession((s) => s.listed)
  const setListed = useSession((s) => s.setListed)

  const tab: AddTab = A.tab === 'file' && !companies.length ? 'research' : A.tab
  const tabs: [AddTab, string][] = [['research', 'New company'], ...(companies.length ? [['file', 'Company on file'] as [AddTab, string]] : []), ...(apiOn ? [['import', 'Import assessment files'] as [AddTab, string]] : [])]
  const busy = A.busy || !!addJob
  const go = { research: ['Generate outside-in assessment', () => { if (!listed) return patch({ err: 'Please confirm the company and its peers are listed.' }); void startResearch(session.mode) }],
    file: ['Open outside-in assessment', () => { if (!listed) return patch({ err: 'Please confirm the company and its peers are listed.' }); patch({ err: '' }); useSession.getState().markOiDone(); nav(PATHS.oi) }],
    import: ['Import and open', () => { void startImport() }] }[tab] as [string, () => void]
  const off = (tab === 'research' && !research.enabled) || (tab === 'import' && !apiOn)

  const setPeer = (i: number, k: 'name' | 'ticker', v: string) => patch({ peers: A.peers.map((p, n) => (n === i ? { ...p, [k]: v } : p)) })
  const onOwnFiles = (fl: FileList | null) => {
    const files = [...A.files]
    sizeOk(Array.from(fl || [])).forEach((f) => {
      if (files.length >= MAX_OI_DOCS) return toast(`At most ${MAX_OI_DOCS} documents.`)
      if (!files.some((x) => x.name === f.name && x.file.size === f.size)) files.push({ name: f.name, file: f })
    })
    patch({ files })
  }

  return (
    <>
      <PageHead title="Outside-in assessment" sub="Research a listed company and its peers from public information, or open a company already on file." eyebrow="Stage 1 of 3" />
      <Card className="acc" id="coform">
        <h3>Company and peers</h3>
        {!busy && <SegTabs value={tab} onChange={(t) => patch({ tab: t, err: '', problems: null })} tabs={tabs} />}

        {addJob ? <AddJobView /> : tab === 'file' ? (
          <>
            <div className="fgrid">
              <div><label htmlFor="company">Company</label>
                <select id="company" value={session.companyId ?? ''} onChange={(e) => void openCompany(e.target.value)}>
                  {companies.map((c) => <option key={c.id} value={c.id}>{coLabel(c)}</option>)}
                </select></div>
              <div><label htmlFor="tk">Ticker</label><input type="text" id="tk" value={j?.meta.ticker || ''} readOnly /></div>
              <div><label htmlFor="pd">Period</label><input type="text" id="pd" value={j?.meta.period || ''} readOnly /></div>
            </div>
            <label>Peers</label><div className="chips">{(j?.meta.peer_short || []).map((p) => <span className="chip" key={p}>{p}</span>)}</div>
          </>
        ) : tab === 'import' ? (
          <>
            <p className="muted">Add a company from the assessment files prepared by the A&amp;M team. They are checked against the scoring rules before the company is added, and the report and dashboard are prepared from them.</p>
            <label htmlFor="a_oi">Outside-in assessment file (required)</label>
            <div className="frow"><input type="file" id="a_oi" accept=".json" className="fileinput" onChange={(e) => patch({ importOi: e.target.files?.[0] ?? null })} /></div>
            <label htmlFor="a_io">Inside-out assessment file (optional)</label>
            <div className="frow"><input type="file" id="a_io" accept=".json" className="fileinput" onChange={(e) => patch({ importIo: e.target.files?.[0] ?? null })} /></div>
            <label htmlFor="a_pr">Earlier quarters (optional, up to four)</label>
            <div className="frow"><input type="file" id="a_pr" accept=".json" multiple className="fileinput" onChange={(e) => patch({ importPr: Array.from(e.target.files || []) })} /></div>
          </>
        ) : (
          <>
            {research.enabled
              ? <p className="muted">The board is researched from approved public sources for the company and each peer, scored against the 22 indicators and checked against the scoring rules. It usually takes 10 to 20 minutes. To assess a company on file for a new quarter, enter it again with the new period.</p>
              : <Notice>{apiOn ? 'New-company research is not switched on yet. Your A&M team can still add a company from its assessment files.' : 'Companies are held by the assessment service, which is not connected. Your A&M engagement team can give you access.'}</Notice>}
            <div className="fgrid3">
              <div><label htmlFor="a_company">Company</label><input type="text" id="a_company" value={A.company} onChange={(e) => patch({ company: e.target.value })} placeholder="e.g. Microsoft Corporation" /></div>
              <div><label htmlFor="a_ticker">Ticker</label><input type="text" id="a_ticker" value={A.ticker} onChange={(e) => patch({ ticker: e.target.value })} placeholder="MSFT" /></div>
              <div><label htmlFor="a_period">Period</label><input type="text" id="a_period" value={A.period} onChange={(e) => patch({ period: e.target.value })} placeholder="2026-Q4" /></div>
            </div>
            <label>Peers (two to five listed competitors)</label>
            {A.peers.map((p, i) => (
              <div className="prow" key={i}>
                <input type="text" value={p.name} onChange={(e) => setPeer(i, 'name', e.target.value)} placeholder={`Peer ${i + 1} name`} aria-label={`Peer ${i + 1} name`} />
                <input type="text" value={p.ticker} onChange={(e) => setPeer(i, 'ticker', e.target.value)} placeholder="Ticker" aria-label={`Peer ${i + 1} ticker`} />
                {A.peers.length > 2 && <Button variant="sec" size="sm" aria-label="Remove peer" onClick={() => patch({ peers: A.peers.filter((_, n) => n !== i) })}>×</Button>}
              </div>
            ))}
            {A.peers.length < MAX_PEERS && <Button variant="sec" size="sm" icon="plus" onClick={() => patch({ peers: [...A.peers, { name: '', ticker: '' }] })}>Add a peer</Button>}
          </>
        )}

        {!busy && tab !== 'import' && (
          <label className="pl"><input type="checkbox" id="listed" checked={listed} onChange={(e) => { setListed(e.target.checked); if (e.target.checked) patch({ err: '' }) }} /> I confirm the company and its peers are listed.</label>
        )}
        {A.err && <Notice kind="bad"><b>{A.err}</b>{A.problems && A.problems.length > 0 && <ul>{A.problems.slice(0, 10).map((p, i) => <li key={i}>{fmtProblem(p)}</li>)}</ul>}</Notice>}
        {!busy && (
          <Collapsible summary="Sources we rely on" className="guard">
            <p><b>Used:</b> regulators and exchanges, company investor-relations sites, established news and trade press, proxy advisors, rating agencies and sell-side research, sector conference presentations, sustainability and integrated reports.</p>
            <p><b>Not used:</b> social media posts by individuals, anonymous forums, unverified blogs and employee-review sites.</p>
          </Collapsible>
        )}
      </Card>

      {!busy && tab === 'research' && (
        <Card className="acc">
          <h3>Your own documents (optional)</h3>
          <p className="muted">Analyst notes, earlier work or other material on the company. Claude reads it alongside the public record, for the company only (not the peers), and cites anything it uses as a source marked “provided”. PDF, Word or text, up to 25 MB per file and 10 files.</p>
          <div className="frow"><input type="file" id="oifiles" multiple accept={FILE_ACCEPT} className="fileinput" aria-label="Your own documents" value="" onChange={(e) => onOwnFiles(e.target.files)} /></div>
          <FileChips files={A.files} onRemove={(i) => patch({ files: A.files.filter((_, n) => n !== i) })} />
        </Card>
      )}
      {!busy && <PriorCard j={tab === 'file' && session.companyId ? j : undefined} fresh={tab !== 'file' || !session.companyId} />}

      {!busy && (
        <div className="row sb">
          <Link className="btn sec" to="/home">Cancel</Link>
          <NextButton size="lg" disabled={off} onClick={go[1]}>{go[0]}</NextButton>
        </div>
      )}
    </>
  )
}


