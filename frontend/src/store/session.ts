import { create } from 'zustand'
import { persist, createJSONStorage } from 'zustand/middleware'
import { nameFromEmail } from '../lib/journey'

/** Who is signed in and which company/assessment the director is working on. The browser holds no grades. */
interface SessionState {
  email: string
  name: string
  companyId: string | null
  mode: string
  /** the outside-in stage has been opened/completed for the selected company in this session */
  oiDone: boolean
  /** the director has seen the stage-3 actions page */
  seen3: boolean
  /** earlier periods picked to show the trend (max two) */
  priorSel: string[]
  /** "I confirm the company and its peers are listed" */
  listed: boolean
  /** set once the first company list has been reconciled after a page load */
  booted: boolean

  signIn: (email: string) => void
  signOut: () => void
  selectCompany: (id: string | null) => void
  /** start a new assessment: the selected company stays, the run is reset */
  startFresh: () => void
  markOiDone: () => void
  markSeen3: () => void
  togglePrior: (period: string, on: boolean) => void
  setListed: (v: boolean) => void
  setBooted: () => void
}

export const useSession = create<SessionState>()(
  persist(
    (set) => ({
      email: '', name: '', companyId: null, mode: 'director_request',
      oiDone: false, seen3: false, priorSel: [], listed: false, booted: false,
      signIn: (email) => set({ email, name: nameFromEmail(email) }),
      signOut: () => set({ email: '', name: '', companyId: null, oiDone: false, seen3: false, priorSel: [], listed: false, booted: false }),
      selectCompany: (id) => set((s) => (id === s.companyId && s.oiDone ? s : { companyId: id, oiDone: id != null, seen3: false, priorSel: [] })),
      startFresh: () => set({ oiDone: false, seen3: false, priorSel: [] }),
      markOiDone: () => set({ oiDone: true }),
      markSeen3: () => set({ seen3: true }),
      togglePrior: (period, on) => set((s) => {
        const has = s.priorSel.includes(period)
        if (on && !has && s.priorSel.length < 2) return { priorSel: [...s.priorSel, period] }
        if (!on && has) return { priorSel: s.priorSel.filter((p) => p !== period) }
        return s
      }),
      setListed: (listed) => set({ listed }),
      setBooted: () => set({ booted: true }),
    }),
    {
      name: 'am-board-session',
      storage: createJSONStorage(() => sessionStorage),
      partialize: (s) => ({ email: s.email, name: s.name, companyId: s.companyId, mode: s.mode, oiDone: s.oiDone, seen3: s.seen3, priorSel: s.priorSel }),
    },
  ),
)
