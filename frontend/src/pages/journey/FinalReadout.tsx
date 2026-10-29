import { useEffect } from 'react'
import { Link } from 'react-router-dom'
import { Icon } from '../../components/Icon'
import { Button, Card, Collapsible, DlButton, PageHead } from '../../components/ui'
import { useJourney } from '../../lib/useJourney'
import { fmtStatus, priorActionsList } from '../../lib/journey'
import { useSession } from '../../store/session'
import { ActionCard, AddAction, Codes, useJourneyCtx } from './parts'

/** Stage 3: the five actions, refined by the inside-out assessment. */
export default function FinalReadout() {
  const { j, session } = useJourney()
  const ctx = useJourneyCtx()
  useEffect(() => { useSession.getState().markSeen3() }, [])
  if (!j) return <p className="muted">Loading…</p>
  const acts = j.io ? j.io.actions : j.actions
  const pal = priorActionsList(j, session.priorSel), back = j.io?.back || []
  return (
    <>
      <PageHead title="The board’s five actions" sub={`${j.meta.company} · ${j.meta.period} · refined by the inside-out assessment`} eyebrow="Stage 3 of 3 · summary"
        right={<><Button variant="sec" icon="dash" onClick={() => ctx.openDash('io')}>Dashboard</Button><DlButton files={j.files} k="io_docx" label="Report (Word)" icon="doc" /></>} />
      <Card className="acc"><p className="m0">The outside-in assessment proposed five actions from public information. The inside-out assessment tested them against the board’s own documents and the directors’ anonymous self-assessment. These are the five that stand, in priority order, each tied to its evidence and with measures to track progress.</p></Card>
      {acts.map((a) => <ActionCard key={a.n} a={a} cid={session.companyId || undefined} />)}
      {session.companyId && <AddAction cid={session.companyId} count={acts.length} />}
      {pal.length > 0 && (
        <>
          <h2 className="sech">Last quarter’s actions</h2>
          <Card>
            {pal.map((a, i) => {
              const b = back.find((x) => x.id === a.id)
              return (
                <div className="dact st" key={a.id ?? i}>
                  <i className={`sd st-${a.status}`} />
                  <div style={{ flex: 1 }}>
                    <b>{a.heading}</b>
                    <div className="ks"><span className={`st-${a.status}`}>{fmtStatus(a.status)}</span>{a.note ? <> · <Codes text={a.note} /></> : null}</div>
                    {b && (
                      <Collapsible summary="How to get back on track" className="pback">
                        <p><b>What happened.</b> {b.what}</p>
                        <p><b>Root cause.</b> {b.cause}</p>
                        <p><b>To prevent it recurring.</b> {b.prevent}</p>
                      </Collapsible>
                    )}
                  </div>
                </div>
              )
            })}
          </Card>
        </>
      )}
      <Collapsible summary="The outside-in proposals these were refined from" className="orig">
        {j.actions.map((a) => <div className="dact" key={a.n}><span>{a.n}</span><div><b>{a.heading}</b><div className="ks"><Codes text={a.description} /></div></div></div>)}
      </Collapsible>
      <div className="row sb" style={{ marginTop: 20 }}>
        <Link className="btn sec" to="/journey/inside-out/readout">Back to the inside-out readout</Link>
        <Link className="btn" to="/briefcase"><Icon name="brief" size={16} />Briefcase</Link>
      </div>
    </>
  )
}
