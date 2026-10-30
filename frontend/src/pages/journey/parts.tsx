import { useMemo, useState, type ReactNode } from 'react'
import { useActionEdit } from '../../api/queries'
import { Link } from 'react-router-dom'
import { Icon } from '../../components/Icon'
import { Button, Card, Chip, DlButton, GradeChip, GradeSquare, NextButton } from '../../components/ui'
import { DIMN, DIMS, DSHORT } from '../../lib/constants'
import { dimGrades, fmtStatus, overallAvg, prevGradeArrow, priorActionsList, selectedPriors } from '../../lib/journey'
import { useSession } from '../../store/session'
import { useJourney } from '../../lib/useJourney'
import type { JourneyAction, JourneyView } from '../../api/types'
import { useOutletContext } from 'react-router-dom'

export interface JourneyCtx { openDash: (s: 'oi' | 'io') => void; openPlan: (s: 'oi' | 'io') => void }
export const useJourneyCtx = () => useOutletContext<JourneyCtx>()

/** Text with evidence codes such as [E05] shown as code chips (the evidence panel itself belongs to the report). */
export function Codes({ text }: { text: string }) {
  const parts = useMemo(() => String(text ?? '').split(/(\[(?:IO|SA|[A-Z])\d{2,3}\])/g), [text])
  return <>{parts.map((p, i) => (/^\[(?:IO|SA|[A-Z])\d{2,3}\]$/.test(p) ? <span key={i} className="code">{p.slice(1, -1)}</span> : <span key={i}>{p}</span>))}</>
}

/** One action, as on the action plan: heading, target, what to do (with its evidence) and how progress is measured. */
export function ActionCard({ a, cid }: { a: JourneyAction & { edited?: boolean }; cid?: string }) {
  const [editing, setEditing] = useState(false)
  const [f, setF] = useState({ heading: '', description: '', target: '', measures: '' })
  const m = useActionEdit(cid || '')
  const open = () => { setF({ heading: a.heading, description: a.description, target: a.target || '', measures: (a.measures || []).join('\n') }); setEditing(true) }
  const save = () => m.mutate({ n: a.n, body: { ...f, measures: f.measures.split('\n').map((x) => x.trim()).filter(Boolean) } }, { onSuccess: () => setEditing(false) })
  const del = () => { if (window.confirm(`Delete action ${a.n}, “${a.heading}”?`)) m.mutate({ n: a.n, del: true }) }
  if (editing) return <ActionForm f={f} setF={setF} onSave={save} onCancel={() => setEditing(false)} busy={m.isPending} err={m.error?.message} />
  return (
    <div className="pact">
      <div className="pnum">{a.n}</div>
      <div className="pbody">
        <div className="phead"><h3>{a.heading}</h3><span className="ptgt">Target {a.target || '–'}</span></div>
        {cid && <div className="row" style={{ gap: 8, marginBottom: 6 }}>
          {a.edited && <span className="chip">edited by you</span>}
          <Button size="sm" variant="sec" onClick={open}>Edit</Button><Button size="sm" variant="sec" disabled={m.isPending} onClick={del}>Delete</Button>
          {m.error && <span className="muted err" role="alert">{m.error.message}</span>}
        </div>}
        <p><Codes text={a.description} /></p>
        {(a.measures || []).length > 0 && <><div className="kl">How progress is measured</div><ul className="pmeas">{a.measures!.map((x, i) => <li key={i}>{x}</li>)}</ul></>}
      </div>
    </div>
  )
}

type ActionFormState = { heading: string; description: string; target: string; measures: string }
function ActionForm({ f, setF, onSave, onCancel, busy, err }: { f: ActionFormState; setF: (v: ActionFormState) => void; onSave: () => void; onCancel: () => void; busy: boolean; err?: string }) {
  const set = (k: keyof ActionFormState) => (e: { target: { value: string } }) => setF({ ...f, [k]: e.target.value })
  return (
    <div className="pact"><div className="pbody">
      <label className="kl" htmlFor="af-h">Heading</label><input id="af-h" className="input" value={f.heading} onChange={set('heading')} maxLength={300} />
      <label className="kl" htmlFor="af-d">What to do</label><textarea id="af-d" className="input" rows={4} value={f.description} onChange={set('description')} />
      <label className="kl" htmlFor="af-t">Target (for example 2027-Q2)</label><input id="af-t" className="input" value={f.target} onChange={set('target')} maxLength={200} />
      <label className="kl" htmlFor="af-m">How progress is measured (one per line)</label><textarea id="af-m" className="input" rows={3} value={f.measures} onChange={set('measures')} />
      <div className="row" style={{ marginTop: 10 }}><Button size="sm" disabled={busy || !f.heading.trim()} onClick={onSave}>Save</Button><Button size="sm" variant="sec" onClick={onCancel}>Cancel</Button>{err && <span className="muted err" role="alert">{err}</span>}</div>
    </div></div>
  )
}

/** Adds one more action to the board's list (the server holds at most five). */
export function AddAction({ cid, count }: { cid: string; count: number }) {
  const [open, setOpen] = useState(false)
  const [f, setF] = useState<ActionFormState>({ heading: '', description: '', target: '', measures: '' })
  const m = useActionEdit(cid)
  if (count >= 5) return null
  if (!open) return <div className="row" style={{ marginBottom: 20 }}><Button variant="sec" onClick={() => setOpen(true)}>Add an action</Button></div>
  return <ActionForm f={f} setF={setF} busy={m.isPending} err={m.error?.message} onCancel={() => setOpen(false)}
    onSave={() => m.mutate({ body: { ...f, measures: f.measures.split('\n').map((x) => x.trim()).filter(Boolean) } }, { onSuccess: () => { setOpen(false); setF({ heading: '', description: '', target: '', measures: '' }) } })} />
}

export function PlanButton({ stage, j }: { stage: 'oi' | 'io'; j: JourneyView }) {
  const ctx = useJourneyCtx()
  const n = ((stage === 'io' ? j.io?.actions : j.actions) || []).length
  return <Button variant="sec" icon="clip" onClick={() => ctx.openPlan(stage)}>Action plan <span className="bcnt">{n}</span></Button>
}

/** A bar fixed to the bottom of the screen with the next step, so it is in reach however far the report is scrolled. */
export function StickyNext({ text, to, label }: { text: string; to: string; label: string }) {
  return (
    <>
      <div className="stickpad" />
      <div className="stickynext"><div className="wrap"><span>{text}</span><Link className="btn" to={to}>{label}<Icon name="arrow" size={16} /></Link></div></div>
    </>
  )
}

export function NextCard({ title, text, to, label }: { title: string; text: string; to: string; label: string }) {
  return (
    <Card className="dlcard nextcard">
      <div className="dltxt"><h3 className="m0">{title}</h3><p className="muted m0">{text}</p></div>
      <div className="row"><Link className="btn lg" to={to}>{label}<Icon name="arrow" size={16} /></Link></div>
    </Card>
  )
}

/** Grade summary card shown at the top of each stage's result. */
export function DeliveryCard({ stage, j }: { stage: 'oi' | 'io'; j: JourneyView }) {
  const ctx = useJourneyCtx()
  const priorSel = useSession((s) => s.priorSel)
  const io = stage === 'io'
  const L = (io ? j.overall.io : j.overall.oi) || {}
  const hist = selectedPriors(j, priorSel), last = hist[hist.length - 1]
  const lastGrade = last ? last.overall?.grade ?? last.grade ?? null : null
  const arrow = prevGradeArrow(j.overall.oi?.grade, lastGrade)
  const avg = overallAvg(L)
  const dims = dimGrades(j, stage)
  const findings = (io ? j.findings_io : j.findings_oi) || []
  const pa = io ? priorActionsList(j, priorSel) : []
  return (
    <div className="card gcard">
      <div className="gcl">
        <div className="kl">Overall grade · {io ? 'after inside-out' : 'outside-in'}</div>
        <div className="kgrade big">
          <GradeSquare g={L.grade} size="xl" />
          <div>
            <b>{L.label || 'No overall grade'}</b>
            <div className="ks">{avg != null ? avg.toFixed(2) + ' of 5.00' : ''}</div>
            {io && <div className="ks">Outside-in <GradeChip g={j.overall.oi?.grade} /> → <GradeChip g={j.overall.io?.grade} /></div>}
            {last && arrow && <div className="ks">{arrow.dir === 'up' ? <span className="delta up">▲ up from {arrow.prev}</span> : arrow.dir === 'dn' ? <span className="delta dn">▼ down from {arrow.prev}</span> : <span className="muted">▬ unchanged</span>} · {last.period}</div>}
          </div>
        </div>
        {dims && (
          <div className="dimstrip">{DIMS.map((d) => <div key={d} title={DIMN[d]}><span className={`g g${dims[d] || 'NA'}`}>{dims[d] || '–'}</span><small>{DSHORT[d]}</small></div>)}</div>
        )}
        <Button block icon="dash" onClick={() => ctx.openDash(stage)}>Open the dashboard</Button>
      </div>
      <div className="gcr">
        <div className="eb m0">Three headline findings</div>
        <ol className="flist">{findings.map((x, i) => <li key={i}><Codes text={x} /></li>)}</ol>
        {io && pa.length > 0 && (
          <>
            <div className="eb">Progress on last quarter’s actions</div>
            <div className="scroll"><table className="dt"><thead><tr><th>Prior action</th><th>Status</th></tr></thead><tbody>
              {pa.map((a, i) => <tr key={i}><td>{a.heading}</td><td><span className={`st-${a.status}`}>{fmtStatus(a.status)}</span></td></tr>)}
            </tbody></table></div>
          </>
        )}
      </div>
    </div>
  )
}

/** Earlier assessments of this company on file; up to two can be compared with this quarter. `fresh`: a company not yet on file. */
export function PriorCard({ j, fresh }: { j?: JourneyView; fresh: boolean }) {
  const sel = useSession((s) => s.priorSel)
  const toggle = useSession((s) => s.togglePrior)
  const co = j?.meta.short || j?.meta.company || ''
  const pr = fresh || !j ? [] : (j.priors || []).filter((p) => p.period !== j.meta.period).slice().sort((a, b) => (a.period < b.period ? 1 : -1))
  const n = fresh ? 0 : sel.length
  return (
    <Card className="acc">
      <h3>Earlier assessments (for trend)</h3>
      {pr.length ? (
        <>
          <p className="muted">Choose up to two earlier assessments of {co} to compare with this quarter.</p>
          <div className="plist">
            {pr.map((p) => {
              const on = sel.includes(p.period), dis = !on && n >= 2, grade = p.overall?.grade ?? p.grade
              return (
                <label key={p.period} className={`pitem${on ? ' on' : ''}${dis ? ' dis' : ''}`}>
                  <input type="checkbox" value={p.period} checked={on} disabled={dis} onChange={(e) => toggle(p.period, e.target.checked)} />
                  <b>{p.period}</b><span className="muted">{p.stage === 'inside_out' ? 'Outside-in and inside-out' : 'Outside-in'}</span>
                  {grade ? <GradeChip g={grade} /> : null}
                </label>
              )
            })}
          </div>
          <p className="ks">{n} of 2 selected</p>
        </>
      ) : (
        <>
          <p className="muted">Choose up to two earlier assessments to compare with this quarter.</p>
          <div className="plist pempty"><Icon name="clip" size={18} /><span>{fresh ? 'No earlier assessments to show. Enter a company that is already on file (same name or ticker) and its earlier assessments are listed here, so you can pick up to two to show the trend.' : `No earlier assessments of ${co} yet. Each completed assessment is listed here, so in a later quarter you can pick up to two to show the trend.`}</span></div>
          <p className="ks">0 of 2 selected</p>
        </>
      )}
    </Card>
  )
}

/** The documents already supplied for this stage's assessment (names only; the files are not kept), shown again on the input page. */
export function SubmittedDocs({ stage }: { stage: 'oi' | 'io' }) {
  const { raw } = useJourney()
  const docs = raw?.documents_provided?.[stage] || []
  if (!docs.length) return null
  return (
    <div className="muted" style={{ marginBottom: 10 }}>
      <b>Already supplied ({docs.length}):</b>
      <ul style={{ margin: '4px 0 0 18px' }}>{docs.map((d, i) => <li key={i}>{d.name}</li>)}</ul>
    </div>
  )
}

export function FileChips({ files, onRemove, label }: { files: { name: string }[]; onRemove: (i: number) => void; label?: (n: string) => string }) {
  if (!files.length) return null
  return <div className="chips">{files.map((f, i) => <Chip key={f.name + i} onRemove={() => onRemove(i)} label={label ? label(f.name) : `Remove ${f.name}`}>{f.name}</Chip>)}</div>
}

export const DownloadGroup = ({ title, sub, children }: { title: string; sub: string; children: ReactNode }) => (
  <div className="card dgroup"><h3 className="m0">{title}</h3><p className="muted">{sub}</p><div className="col">{children}</div></div>
)
export { DlButton, NextButton }

