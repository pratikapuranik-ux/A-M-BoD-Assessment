import { useNavigate } from 'react-router-dom'
import { Band, BackLink } from '../components/Layout'
import { Icon } from '../components/Icon'
import { ButtonLink, Button, Card, GradeSquare, PageHead, toast } from '../components/ui'
import { useJourney } from '../lib/useJourney'
import { briefItems, PATHS } from '../lib/journey'
import { freshAssessment, openCompany } from '../lib/actions'

export default function Briefcase() {
  const nav = useNavigate()
  const { companies } = useJourney()
  const items = briefItems(companies)
  const open = async (id: string) => {
    const v = await openCompany(id)
    if (!v) return
    nav(v.io ? PATHS.ioRead : PATHS.oi)
  }
  return (
    <>
      <Band>
        <BackLink to="/home" inverse>Back to Home</BackLink>
        <PageHead eyebrow="Readouts" title="Briefcase" sub="Every readout on file. Download the files, or reopen a readout and its dashboard."
          right={<Button variant="inv" icon="plus" onClick={() => { freshAssessment(); nav(PATHS.setup) }}>New assessment</Button>} />
      </Band>
      <div className="wrap pagec">
        {items.length ? items.map((x) => (
          <Card className="bcard" key={x.id + x.title}>
            <div className="bcrow">
              <div className="bcl">
                {x.grade !== 'NA' ? <GradeSquare g={x.grade} /> : <span className="gsq gNA"><Icon name="doc" size={18} /></span>}
                <div><b className="bt2">{x.title}</b><div className="muted">{x.meta}</div></div>
              </div>
              <div className="row">
                {x.files.map((f) => <ButtonLink key={f[0]} size="sm" icon={f[2] as 'doc' | 'web'} href={x.urls[f[0]]} download onClick={() => toast('Downloading…')}>{f[1]}</ButtonLink>)}
                {!x.prior && <Button size="sm" onClick={() => open(x.id)}>Open readout</Button>}
              </div>
            </div>
          </Card>
        )) : <Card><p className="muted m0">Nothing in the Briefcase yet.</p></Card>}
      </div>
    </>
  )
}
