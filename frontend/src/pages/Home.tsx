import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { Band } from '../components/Layout'
import { Icon } from '../components/Icon'
import { AppDialog, Button, Card, GradeChip, KpiTile, PageHead, toast } from '../components/ui'
import { useJourney } from '../lib/useJourney'
import { addBusy, freshAssessment, openCompany } from '../lib/actions'
import { coLabel, greeting, PATHS, todayLabel } from '../lib/journey'
import { useDeleteCompany } from '../api/queries'
import { useInsideOut } from '../store/insideOut'
import type { CompanySummary } from '../api/types'

export default function Home() {
  const nav = useNavigate()
  const { session, apiOn, companies: cs, companiesQ, j, cur, hasCompany, oiDone, ioDone, period, actions } = useJourney()
  const del = useDeleteCompany()
  const [target, setTarget] = useState<CompanySummary | null>(null)
  const done = cs.filter((c) => c.stages?.outside_in).length
  const co = j?.meta.short || j?.meta.company || cur?.short || ''

  const newAssessment = () => { freshAssessment(); nav(PATHS.setup) }
  const pick = async (id: string) => {
    const v = await openCompany(id)
    if (!v) return
    if (!addBusy()) useInsideOut.getState().resetAdd('file')
    nav(v.io ? PATHS.ioRead : PATHS.oi)
  }
  const confirmDelete = () => {
    if (!target) return
    const c = target
    del.mutate(c.id, {
      onSuccess: () => { toast(`${c.name} was deleted.`); setTarget(null) },
      onError: (e) => { toast((e as Error).message); setTarget(null) },
    })
  }

  return (
    <>
      <Band>
        <PageHead eyebrow={todayLabel()} title={greeting() + (session.name ? ', ' + session.name.split(' ')[0] : '')}
          sub="Your board assessments, readouts and open actions in one place."
          right={<Button variant="inv" icon="plus" onClick={newAssessment}>New assessment</Button>} />
        <div className="kpis kband">
          <KpiTile label="Companies on file" value={cs.length} sub={`${done} with an outside-in assessment`} />
          <KpiTile label="Current assessment" value={hasCompany ? co : '–'} sub={hasCompany ? `${period} · ${ioDone ? 'complete' : oiDone ? 'inside-out pending' : 'not started'}` : 'No company yet'} />
          <KpiTile label="Final readouts" value={cs.filter((c) => c.stages?.inside_out).length} sub="Inside-out complete" />
          <KpiTile label="Open actions" value={actions.length} sub="For your attention" />
        </div>
      </Band>
      <div className="wrap pagec">
        <Card>
          <div className="row sb chead"><h3 className="m0">Actions</h3><span className="cnt">{actions.length} open</span></div>
          {actions.map((n) => (
            <div className="li" key={n.title}>
              <div className={`ib ${n.tone}`}><Icon name={n.icon} /></div>
              <div className="lb"><b>{n.title}</b><div className="muted">{n.text}</div></div>
              <div className="lr"><small>{n.when}</small><Link className="btn sec sm" to={n.to}>{n.label}</Link></div>
            </div>
          ))}
        </Card>
        <Card>
          <div className="row sb chead">
            <h3 className="m0">Companies</h3>
            {apiOn && <Button variant="sec" size="sm" icon="plus" onClick={() => { if (!addBusy()) useInsideOut.getState().resetAdd(); nav(PATHS.setup) }}>Add a company</Button>}
          </div>
          {cs.length ? (
            <div className="scroll"><table className="tbl port"><thead><tr><th>Company</th><th>Peers</th><th>Period</th><th>Outside-in</th><th>After inside-out</th><th></th></tr></thead><tbody>
              {cs.map((c) => { const g = c.grades || {}; return (
                <tr key={c.id}>
                  <td><b>{c.name}</b><div className="muted">{c.ticker || ''}{c.source === 'research' ? ' · researched' : c.source === 'imported' ? ' · imported' : ''}</div></td>
                  <td>{(c.peers || []).join(', ')}</td><td>{c.period || ''}</td>
                  <td>{g.oi ? <><GradeChip g={g.oi} /> <span className="muted">{c.labels?.oi || ''}</span></> : <span className="muted">–</span>}</td>
                  <td>{g.io ? <GradeChip g={g.io} /> : <span className="muted">Not yet</span>}</td>
                  <td className="ra"><div className="row nowrap" style={{ justifyContent: 'flex-end', flexWrap: 'nowrap' }}>
                    <Button size="sm" variant={c.id === session.companyId ? '' : 'sec'} onClick={() => pick(c.id)} aria-label={`${c.id === session.companyId ? 'Continue' : 'Open'} ${coLabel(c)}`}>{c.id === session.companyId ? 'Continue' : 'Open'}</Button>
                    {apiOn && <Button size="sm" variant="sec" icon="trash" onClick={() => setTarget(c)} aria-label={`Delete ${c.name}`} title="Delete" />}
                  </div></td>
                </tr>) })}
            </tbody></table></div>
          ) : (
            <p className="muted m0">{companiesQ.isLoading ? 'Loading companies…' : apiOn
              ? 'No companies yet. Add a listed company to research its board from public information, or import assessment files prepared by the A&M team.'
              : 'No companies are available. Companies are held by the assessment service, which is not connected; your A&M engagement team can give you access.'}</p>
          )}
        </Card>
      </div>
      <AppDialog open={!!target} onOpenChange={(o) => { if (!o) setTarget(null) }} title={`Delete ${target?.name ?? 'company'}?`}
        description="This removes the company's assessments, survey invitations and files from the assessment service. It cannot be undone.">
        <div className="row" style={{ marginTop: 20, justifyContent: 'flex-end' }}>
          <Button variant="sec" onClick={() => setTarget(null)}>Cancel</Button>
          <Button onClick={confirmDelete} disabled={del.isPending}>{del.isPending ? 'Deleting…' : 'Delete company'}</Button>
        </div>
      </AppDialog>
    </>
  )
}
