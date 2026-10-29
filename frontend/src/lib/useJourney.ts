import { useEffect } from 'react'
import { useCompanies, useCompanyView, useHealth } from '../api/queries'
import { useSession } from '../store/session'
import { selectIoBusy, useInsideOut } from '../store/insideOut'
import { asJourney, priorActionsList, PATHS } from './journey'
import type { JourneyView } from '../api/types'

export interface OpenAction { icon: 'plus' | 'check' | 'upload' | 'clip' | 'brief'; tone: 'o' | 'g' | ''; title: string; text: string; when: string; label: string; to: string }

/** Everything the journey pages need to know about where the director is, derived from server state plus session flags. */
export function useJourney() {
  const session = useSession()
  const health = useHealth()
  const companies = useCompanies(health.isSuccess)
  const viewQ = useCompanyView(session.companyId)
  const raw = viewQ.data
  const j: JourneyView | undefined = raw ? asJourney(raw) : undefined
  const ioBusy = useInsideOut(selectIoBusy(session.companyId))

  const apiOn = health.isSuccess
  const research = health.data?.research ?? { enabled: false, reason: 'The assessment service is not connected.' }
  const list = companies.data ?? []

  // After a page load (and after a delete) make sure the selected company exists; the first company is the default.
  useEffect(() => {
    if (!companies.isSuccess) return
    const s = useSession.getState()
    const exists = list.some((c) => c.id === s.companyId)
    if (!s.booted || !exists) {
      if (exists) s.selectCompany(s.companyId)
      else s.selectCompany(list[0]?.id ?? null)
      s.setBooted()
    }
  }, [companies.isSuccess, companies.data]) // eslint-disable-line react-hooks/exhaustive-deps

  const hasCompany = !!session.companyId && !!j
  const oiDone = hasCompany && session.oiDone
  const ioDone = oiDone && !!j?.io
  const period = j?.meta.period || ''
  const cur = list.find((c) => c.id === session.companyId)

  const actions: OpenAction[] = []
  if (!session.companyId) {
    if (apiOn) actions.push({ icon: 'plus', tone: 'o', title: 'Add the first company', text: 'Research a listed company’s board from public information, or add it from assessment files prepared by the A&M team.', when: 'To start', label: 'Add a company', to: PATHS.setup })
  } else if (j) {
    const co = j.meta.short || j.meta.company
    const final = ioDone
    if (final) actions.push({ icon: 'check', tone: 'g', title: 'Review the board’s five actions', text: `The ${period} board assessment of ${co} is complete and saved to your Briefcase.`, when: 'Ready', label: 'Open board actions', to: PATHS.actions })
    else if (oiDone) actions.push({ icon: 'upload', tone: 'o', title: 'Add board material to complete the assessment', text: 'Board documents and the directors’ anonymous self-assessment refine the grades and the board’s five actions.', when: 'Inside-out', label: 'Continue', to: PATHS.ioInput })
    else actions.push({ icon: 'clip', tone: 'o', title: `Complete the ${period} assessment of ${co}`, text: 'Outside-in from public information, then inside-out with your board’s own material.', when: 'Outside-in', label: 'Start', to: PATHS.setup })
    const behind = final ? priorActionsList(j, session.priorSel).filter((x) => x.status === 'behind' || x.status === 'not_started').length : 0
    const prior = j.prior as { period?: string; actions?: unknown[] } | null
    if (behind) actions.push({ icon: 'clip', tone: 'o', title: `${behind} of last quarter’s actions need attention`, text: 'Behind plan or not started. Your readout sets out what happened and how to get back on track.', when: 'Next board meeting', label: 'Review', to: PATHS.ioRead })
    else if (!final && prior?.actions?.length) actions.push({ icon: 'brief', tone: '', title: 'Check progress on last quarter’s actions', text: `The ${prior.period} readout set ${prior.actions.length} board actions. Their status is reviewed in the inside-out stage.`, when: 'Before inside-out', label: 'Open Briefcase', to: '/briefcase' })
  }

  return {
    session, apiOn, research, health, companies: list, companiesQ: companies, viewQ, raw, j, cur, hasCompany, oiDone, ioDone, ioBusy, period, actions,
  }
}
