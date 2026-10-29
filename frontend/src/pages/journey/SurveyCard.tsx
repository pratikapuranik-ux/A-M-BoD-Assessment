import { useState } from 'react'
import { Button, ButtonLink, Card, Chip, DlButton, Meter, toast } from '../../components/ui'
import { useInvite, useSurvey, useUninvite } from '../../api/queries'
import { EMAIL_RE } from '../../lib/journey'
import { numWord } from '../../lib/constants'
import { parseQuestionnaire } from '../../lib/questionnaire'
import { sizeOk } from '../../lib/actions'
import { useInsideOut } from '../../store/insideOut'
import type { JourneyView, SurveyStatus } from '../../api/types'

const DEFAULT_SURVEY: SurveyStatus = { invites: [], responses: 0, min: 3 }

/** The server's count (responses received) plus returned questionnaires not yet uploaded. */
export function useSurveyNow(cid: string, poll: boolean) {
  const q = useSurvey(cid, poll)
  const qFiles = useInsideOut((s) => s.qFiles)
  const v: SurveyStatus = { ...DEFAULT_SURVEY, ...(q.data || {}) }
  const count = v.count != null ? v.count : v.responses
  return { v, n: count + qFiles.length, count, loaded: !!q.data }
}

function mailtoFor(x: { email: string; link: string }, company: string, period: string, nq: number) {
  const body = `You are invited to take part in an anonymous board self-assessment for ${company} (${period}).\n\n` +
    `There are ${numWord(nq)} short questions about how the board works; it takes about 15 minutes. Your answers are pooled with those of other directors and are never attributed to you.\n\n` +
    `Open your personal link to begin:\n${x.link}\n\nThe link is personal to you; please do not forward it.`
  return `mailto:${encodeURIComponent(x.email)}?subject=${encodeURIComponent('Board self-assessment: ' + company)}&body=${encodeURIComponent(body)}`
}

export default function SurveyCard({ cid, j, apiOn }: { cid: string; j: JourneyView; apiOn: boolean }) {
  const { v, n } = useSurveyNow(cid, true)
  const invite = useInvite(cid), uninvite = useUninvite(cid)
  const qFiles = useInsideOut((s) => s.qFiles)
  const [emails, setEmails] = useState('')
  const [msg, setMsg] = useState('')
  const need = Math.max(0, v.min - n)

  const doInvite = () => {
    const list = emails.split(/[\s,;]+/).map((x) => x.trim()).filter(Boolean)
    if (!list.length) return setMsg('Enter at least one email address.')
    const bad = list.filter((e) => !EMAIL_RE.test(e))
    if (bad.length) return setMsg('Not an email address: ' + bad.join(', '))
    invite.mutate(list, {
      onSuccess: () => { setEmails(''); setMsg(''); toast(list.length + (list.length === 1 ? ' invitation' : ' invitations') + ' ready. Send each one with Email, or copy its link.') },
      onError: (e) => setMsg((e as Error).message),
    })
  }
  const copy = async (l: string) => {
    try { await navigator.clipboard.writeText(l); toast('Link copied. Paste it into a browser to open the assessment.') }
    catch { window.prompt('Copy this link:', l) }
  }
  const loadQuestionnaires = async (files: File[]) => {
    for (const f of files) {
      if (useInsideOut.getState().qFiles.some((q) => q.name === f.name && q.size === f.size)) { toast(f.name + ' is already in the list.'); continue }
      try {
        const r = await parseQuestionnaire(f, j.q), cnt = r.answers.filter((x) => (x || '').trim()).length
        if (!cnt) { toast(f.name + ' has no answers, so it was not added.'); continue }
        useInsideOut.getState().addQFile({ name: f.name, size: f.size, answers: r.answers, ratings: r.ratings, n: cnt })
      } catch (err) { toast(`Could not read ${f.name}: ${(err as Error).message}`) }
    }
  }

  return (
    <Card className="acc" id="survey">
      <h3>3. Board self-assessment</h3>
      <p className="muted">Invite directors to answer {numWord(j.q.length)} short questions about how the board works. Each person receives a personal link. Answers are pooled and never attributed to anyone.</p>
      {v.local && <p className="muted">These links open only on this computer. To invite directors on other devices, host the app and set BOARD_PUBLIC_URL.</p>}
      <div className="svmeter">
        <div style={{ flex: '0 0 min(220px, 40%)' }}><Meter pct={(n / (v.min || 1)) * 100} /></div>
        <span><b>{n} of {v.min}</b> responses{need ? ` · ${need} more needed before the inside-out view can be prepared` : ' · enough to prepare the inside-out view'}</span>
      </div>
      <label htmlFor="svemails">Invite by email</label>
      <div className="svadd">
        <input type="text" id="svemails" value={emails} onChange={(e) => setEmails(e.target.value)} onKeyDown={(e) => { if (e.key === 'Enter') { e.preventDefault(); doInvite() } }}
          placeholder="name@company.com, another@company.com" aria-label="Email addresses" />
        <Button icon="plus" disabled={!apiOn || invite.isPending} onClick={doInvite}>Add invitations</Button>
      </div>
      <div className="muted err" role="alert">{msg}</div>
      {v.invites.length > 0 && (
        <>
          <div className="scroll"><table className="tbl svt"><thead><tr><th>Invited</th><th>Status</th><th>Personal link</th><th></th></tr></thead><tbody>
            {v.invites.map((x) => (
              <tr key={x.token}>
                <td>{x.email}</td>
                <td>{x.responded ? <span className="st-on_track">Responded</span> : <span className="muted">Invited {x.created}</span>}</td>
                <td><code className="svlink">{x.link}</code></td>
                <td className="ra"><div className="row nowrap" style={{ flexWrap: 'nowrap', justifyContent: 'flex-end' }}>
                  <Button variant="sec" size="sm" onClick={() => void copy(x.link)}>Copy link</Button>
                  <ButtonLink size="sm" icon="mail" href={mailtoFor(x, j.meta.company, j.meta.period, j.q.length)}>Email</ButtonLink>
                  {!x.responded && <Button variant="sec" size="sm" aria-label={`Withdraw the invitation to ${x.email}`} onClick={() => uninvite.mutate(x.token, { onError: (e) => toast((e as Error).message) })}>×</Button>}
                </div></td>
              </tr>))}
          </tbody></table></div>
          <p className="ks">“Responded” shows only that someone has answered, never what they said: answers are stored separately, in random order, with no link to the invitation.</p>
        </>
      )}
      <h4 className="svh">Paper returns</h4>
      <p className="muted">Directors can also complete the Word questionnaire. Each returned file counts as one anonymous response.</p>
      <div className="row"><DlButton files={j.files} k="quest" label="Questionnaire (Word)" icon="doc" /></div>
      <div className="frow">
        <input type="file" id="qfile" accept=".docx" multiple className="fileinput" aria-label="Returned questionnaires" value=""
          onChange={(e) => { const fs = sizeOk(Array.from(e.target.files || [])); if (fs.length) void loadQuestionnaires(fs) }} />
      </div>
      {qFiles.length > 0 && <div className="chips">{qFiles.map((f, k) => <Chip key={f.name + k} label={`Remove ${f.name}`} onRemove={() => useInsideOut.getState().removeQFile(k)}>{f.name} <span className="muted" style={{ marginLeft: 6 }}>{f.n} answers</span></Chip>)}</div>}
    </Card>
  )
}

