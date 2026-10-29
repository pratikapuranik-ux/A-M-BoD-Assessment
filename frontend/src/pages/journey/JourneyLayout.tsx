import { useEffect, useState } from 'react'
import { Navigate, Outlet, useLocation, useNavigate } from 'react-router-dom'
import { BackLink } from '../../components/Layout'
import { Icon } from '../../components/Icon'
import { AppDialog, Button } from '../../components/ui'
import { useJourney } from '../../lib/useJourney'
import { PATHS, withPriors } from '../../lib/journey'
import { useInsideOut } from '../../store/insideOut'
import DashboardDialog from '../../components/DashboardDialog'
import ReportView from '../../report/ReportView'
import { ActionCard, type JourneyCtx } from './parts'

type Stage = 1 | 2 | 3
const STEPS: [Stage, string, string][] = [[1, 'Outside-in', 'Public information'], [2, 'Inside-out', 'Board material and self-assessment'], [3, 'Board actions', 'The five that matter most']]

/** Where a path sits in the three-stage journey. */
const stageOf = (p: string): Stage => (p.startsWith(PATHS.actions) ? 3 : p.startsWith('/journey/inside-out') ? 2 : 1)

/** Sticky context bar (company, stage stepper, dashboard), the back link and the stage pages. */
export default function JourneyLayout() {
  const loc = useLocation()
  const nav = useNavigate()
  const { session, apiOn, health, companiesQ, viewQ, raw, j, hasCompany, oiDone, ioDone, ioBusy } = useJourney()
  const hasRun = useInsideOut((s) => !!(session.companyId && s.ioRuns[session.companyId]))
  const [dash, setDash] = useState<null | 'oi' | 'io'>(null)
  const [plan, setPlan] = useState<null | 'oi' | 'io'>(null)
  const [hideDash, setHideDash] = useState(false)
  const path = loc.pathname.replace(/\/$/, '')
  const stage = stageOf(path)

  /* The bar's Dashboard shortcut appears only once the grade card (which has its own dashboard button) is scrolled away. */
  useEffect(() => {
    setHideDash(false)
    const card = document.querySelector('.gcard')
    if (!card || !('IntersectionObserver' in window)) return
    setHideDash(true)
    const io = new IntersectionObserver((es) => es.forEach((e) => setHideDash(e.isIntersecting)), { rootMargin: '-150px 0px 0px 0px' })
    io.observe(card)
    return () => io.disconnect()
  }, [path, j])

  useEffect(() => { window.scrollTo(0, 0) }, [path])

  const loading = health.isLoading || (apiOn && companiesQ.isLoading) || (apiOn && companiesQ.isSuccess && !session.booted) || (!!session.companyId && !j && viewQ.isLoading)
  if (loading) return <div className="wrap jbody"><p className="muted" role="status">Loading…</p></div>

  /* Route guards: the stages open in order */
  let redirect: string | null = null
  if (path === '/journey' || path === '') redirect = ioDone ? PATHS.ioRead : oiDone ? PATHS.oi : PATHS.setup
  else if (!hasCompany || !oiDone) { if (path !== PATHS.setup) redirect = PATHS.setup }
  else if (path === PATHS.ioInput && ioBusy) redirect = PATHS.ioRun
  else if (path === PATHS.ioRun && !hasRun) redirect = ioDone ? PATHS.ioRead : PATHS.ioInput
  else if (path === PATHS.ioRead && !ioDone) redirect = ioBusy ? PATHS.ioRun : PATHS.ioInput
  else if (path === PATHS.actions && !ioDone) redirect = PATHS.oi
  if (redirect && redirect !== path) return <Navigate to={redirect} replace />

  const done = (n: Stage) => (n === 1 && oiDone) || (n === 2 && ioDone) || (n === 3 && session.seen3)
  const canGo = (n: Stage) => done(n) || n === stage || (n === 2 && oiDone) || (n === 3 && ioDone)
  const go = (n: Stage) => nav(n === 1 ? (oiDone ? PATHS.oi : PATHS.setup) : n === 3 ? PATHS.actions : ioBusy ? PATHS.ioRun : ioDone ? PATHS.ioRead : PATHS.ioInput)
  const dashStage = ioDone ? 'io' : oiDone ? 'oi' : null
  const back: [string, string] = stage === 3 ? [PATHS.ioRead, 'Back to the inside-out readout'] : stage === 2 ? [PATHS.oi, 'Back to the outside-in readout'] : ['/home', 'Back to Home']

  /* the backend-generated HTML dashboard: inside-out once that stage is done, otherwise outside-in */
  const dashTitle = dash === 'io' ? 'Dashboard · after inside-out' : 'Dashboard · outside-in'
  const dashUrl = (ioDone ? raw?.files?.io_html : raw?.files?.oi_html) || null
  const ctx: JourneyCtx ={ openDash: setDash, openPlan: setPlan }
  const planActions = j ? (plan === 'io' ? j.io?.actions : j.actions) || [] : []

  return (
    <>
      <div className="jwrap">
        <div className="wrap jbar">
          <div className="jco">
            <span className="jic"><Icon name="bld" size={18} /></span>
            <div><b>{j?.meta.company || 'New assessment'}</b><span>{j?.meta.ticker ? j.meta.ticker + ' · ' : ''}{j?.meta.period || ''}</span></div>
          </div>
          <div className="journey" role="list">
            {STEPS.map(([n, t, s], i) => (
              <div key={n} style={{ display: 'contents' }} role="listitem">
                {i > 0 && <div className="jline" />}
                <button type="button" className={`jstep ${done(n) ? 'done' : stage === n ? 'on' : ''}`} disabled={!canGo(n)} onClick={() => go(n)} aria-current={stage === n ? 'step' : undefined}>
                  <i>{done(n) ? <Icon name="check" size={14} /> : n}</i><div><b>{t}</b><span>{s}</span></div>
                </button>
              </div>
            ))}
          </div>
          <div className="jact">{dashStage && !hideDash && <Button size="sm" icon="dash" className="jdash" onClick={() => setDash(dashStage)}>Dashboard</Button>}</div>
        </div>
      </div>
      <div className="wrap jbody">
        <BackLink to={back[0]}>{back[1]}</BackLink>
        <Outlet context={ctx} />
      </div>

      {dashUrl ? (
        <DashboardDialog open={!!dash} onOpenChange={(o) => { if (!o) setDash(null) }} title={dashTitle} url={dashUrl} />
      ) : (
        <AppDialog open={!!dash} onOpenChange={(o) => { if (!o) setDash(null) }} title={dashTitle} size="wide">
          {dash && raw && <ReportView view={withPriors(raw, session.priorSel)} mode={dash === 'io' ? 'combined' : 'outside_in'} />}
        </AppDialog>
      )}
      <AppDialog open={!!plan} onOpenChange={(o) => { if (!o) setPlan(null) }} title="Action plan" size="mid"
        description="The board actions with their targets and how progress is measured.">
        <div style={{ marginTop: 14 }}>{planActions.map((a) => <ActionCard key={a.n} a={a} />)}</div>
      </AppDialog>
    </>
  )
}
