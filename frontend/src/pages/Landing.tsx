import { useRef, useState, type FormEvent } from 'react'
import { Navigate, useNavigate, useSearchParams } from 'react-router-dom'
import { AmLogo, Icon } from '../components/Icon'
import { Button, FadeIn, NextButton } from '../components/ui'
import { BASE, DIMN, DIMS, DRAFT, IDS } from '../lib/constants'
import { EMAIL_RE } from '../lib/journey'
import { useSession } from '../store/session'

const STEPS: [string, string, string][] = [
  ['1', 'Outside-in', 'From public information only. We read filings, proxies, earnings calls, announcements and regulator records for the company and every peer, and grade the board A–F, with trend against earlier quarters and five proposed actions.'],
  ['2', 'Inside-out', 'Add what only the board can see: minutes, agendas, board packs, treasury and audit reports, plus an anonymous self-assessment by the directors. Grades update only where that material settles an indicator.'],
  ['3', 'Board actions', 'The five actions proposed outside-in are tested against the board’s own material and refined into the five that matter most, each with measures and a target date.'],
]
const DELIVERABLES: ['dash' | 'doc', string, string][] = [
  ['dash', 'Board dashboard', 'Grades, peer position, trend, the 22 indicators and the board’s actions on one screen, in the app or as a file.'],
  ['doc', 'Detailed report', 'Executive summary, scorecard, evidence for every indicator, peer comparison, actions and appendices, in the app and in Word.'],
]
const EVIDENCE_RULES = [0, 1, 2, 3, 4, 10]

export default function Landing() {
  const email = useSession((s) => s.email)
  const signIn = useSession((s) => s.signIn)
  const nav = useNavigate()
  const [params] = useSearchParams()
  const [msg, setMsg] = useState('')
  const emRef = useRef<HTMLInputElement>(null)
  const loginRef = useRef<HTMLFormElement>(null)
  const methodRef = useRef<HTMLElement>(null)

  /* Invitation links from the legacy server arrive as ?take=<token> */
  const take = params.get('take')
  if (take) return <Navigate to={`/survey/${encodeURIComponent(take)}`} replace />
  if (email) return <Navigate to="/home" replace />

  const submit = (e: FormEvent) => {
    e.preventDefault()
    const em = (emRef.current?.value || '').trim()
    if (!EMAIL_RE.test(em)) { setMsg('Enter your email address.'); return }
    signIn(em); nav('/home')
  }
  const toLogin = () => { loginRef.current?.scrollIntoView({ behavior: 'smooth', block: 'center' }); emRef.current?.focus() }
  const an = BASE.anchors11, scale = BASE.scale

  return (
    <div className="land">
      <header className="lnav"><div className="wrap lnavi"><div className="brandrow"><AmLogo white /><span className="bdiv" /><span className="bname">Board Assessment</span></div></div></header>
      <section className="hero">
        <div className="wrap hgrid">
          <div>
            <div className="eb">Day 1 / Day 2 board assessment</div>
            <h1>Is your board Day 1 or Day 2?</h1>
            <p className="hl">An evidence-based grade for a listed company’s board, from A to F, on six dimensions and 22 indicators, benchmarked against named peers. Public information first; board documents and your own view when you want to go deeper.</p>
            <div className="row" style={{ marginTop: 26 }}><NextButton variant="inv" size="lg" onClick={() => methodRef.current?.scrollIntoView({ behavior: 'smooth' })}>See the methodology</NextButton></div>
            <div className="hstats"><div><b>6</b><span>dimensions</span></div><div><b>22</b><span>indicators</span></div><div><b>A–F</b><span>grade against peers</span></div></div>
          </div>
          <form className="login" id="loginbox" ref={loginRef} onSubmit={submit} noValidate>
            <h3>Sign in</h3>
            <p className="muted">Prepared privately for the requesting director.</p>
            <label htmlFor="em">Email</label><input type="email" id="em" ref={emRef} autoComplete="username" />
            <label htmlFor="pw">Password</label><input type="password" id="pw" autoComplete="current-password" />
            <div className="muted err" role="alert">{msg}</div>
            <button type="submit" className="btn lg block">Sign in<Icon name="arrow" size={16} /></button>
          </form>
        </div>
      </section>

      <section className="lsec" id="method" ref={methodRef}>
        <div className="wrap">
          <FadeIn><div className="eb">The method</div><h2 className="lh">Three steps, one readout</h2></FadeIn>
          <div className="l2">{STEPS.map((x, i) => <FadeIn key={x[0]} delay={i * 0.08}><div className="lcard" style={{ height: '100%' }}><div className="lnum">{x[0]}</div><h3>{x[1]}</h3><p>{x[2]}</p></div></FadeIn>)}</div>
        </div>
      </section>

      <section className="lsec alt"><div className="wrap">
        <FadeIn>
          <div className="eb">The lens</div><h2 className="lh">Day 1 boards stay obsessed with the customer. Day 2 boards slowly stop.</h2>
          <p className="big">{BASE.read[0]}</p><p>{BASE.read[1]}</p>
        </FadeIn>
      </div></section>

      <section className="lsec"><div className="wrap">
        <FadeIn><div className="eb">What is assessed</div><h2 className="lh">Six dimensions, 22 indicators</h2></FadeIn>
        <div className="l3">{DIMS.map((d, i) => (
          <FadeIn key={d} delay={(i % 3) * 0.06}>
            <div className="lcard" style={{ height: '100%' }}><div className="lnum">{d}</div><h3>{DIMN[d]}</h3>
              <ul>{IDS.filter((x) => x[0] === d).map((x) => <li key={x}><b>{x}</b> {BASE.ind[x]}</li>)}</ul></div>
          </FadeIn>))}</div>
      </div></section>

      <section className="lsec alt"><div className="wrap">
        <FadeIn>
          <div className="eb">How scoring works</div><h2 className="lh">Every indicator is scored against written anchors</h2>
          <p>Each indicator is scored 1 (Day 2), 3 (Mixed) or 5 (Day 1); 2 and 4 are used only where evidence sits between two anchors. Example: indicator 1.1, customer evidence in board and management attention.</p>
          <div className="scroll"><table className="dt"><thead><tr><th>1 – Day 2</th><th>3 – Mixed</th><th>5 – Day 1</th></tr></thead><tbody><tr><td>{an['1']}</td><td>{an['3']}</td><td>{an['5']}</td></tr></tbody></table></div>
          <h3 className="sh">From scores to grades</h3>
          <div className="grades">{scale.map((b, i) => (
            <div className="gband" key={b.grade}><span className={`g g${b.grade}`}>{b.grade}</span><b>{b.label}</b>
              <small>{b.min > 0 ? b.min.toFixed(2) + (i === 0 ? ' – 5.00' : ' – ' + (scale[i - 1].min - 0.01).toFixed(2)) : 'below 2.00'}</small></div>))}</div>
        </FadeIn>
      </div></section>

      <section className="lsec"><div className="wrap">
        <FadeIn><div className="eb">Evidence rules</div><h2 className="lh">What stands behind a grade</h2></FadeIn>
        <div className="l3">{EVIDENCE_RULES.map((k, i) => <FadeIn key={k} delay={(i % 3) * 0.06}><div className="lcard" style={{ height: '100%' }}><p>{BASE.method[k].replace(/^\d+\s+/, '')}</p></div></FadeIn>)}</div>
      </div></section>

      <section className="lsec alt"><div className="wrap">
        <FadeIn><div className="eb">Deliverables</div><h2 className="lh">Outputs from the assessment</h2></FadeIn>
        <div className="l2">{DELIVERABLES.map((x, i) => <FadeIn key={x[1]} delay={i * 0.08}><div className="lcard" style={{ height: '100%' }}><div className="lic"><Icon name={x[0]} size={22} /></div><h3>{x[1]}</h3><p>{x[2]}</p></div></FadeIn>)}</div>
        <div className="row" style={{ marginTop: 26 }}><Button size="lg" onClick={toLogin}>Sign in to start<Icon name="arrow" size={16} /></Button></div>
      </div></section>

      <footer className="lfoot"><div className="wrap">
        <img className="wordmark" src="/logo-wordmark.png" alt="Alvarez & Marsal" />
        <div className="draftbox"><b>DRAFT ONLY</b><p>{DRAFT}</p></div>
      </div></footer>
    </div>
  )
}

