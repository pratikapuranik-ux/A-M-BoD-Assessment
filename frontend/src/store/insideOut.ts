import { create } from 'zustand'
import { currentPeriod } from '../lib/journey'

/** Draft state for the Day 1 / Day 2 journey: files picked in the browser, the add-company form and runs in flight.
 *  Nothing here is persisted; files cannot be, and a reload ends the draft (as in the legacy app). */

export interface Picked { name: string; file: File }
export interface QFile { name: string; size: number; answers: string[]; ratings: Record<string, number>; n: number }
export type AddTab = 'research' | 'file' | 'import'
export interface Peer { name: string; ticker: string }

export interface AddDraft {
  tab: AddTab
  company: string
  ticker: string
  period: string
  peers: Peer[]
  files: Picked[]
  err: string
  problems: unknown[] | null
  /** busy while import files are being read or the job is being started */
  busy: boolean
  importOi: File | null
  importIo: File | null
  importPr: File[]
}

export const newAdd = (tab: AddTab = 'research'): AddDraft => ({
  tab, company: '', ticker: '', period: currentPeriod(), peers: [{ name: '', ticker: '' }, { name: '', ticker: '' }],
  files: [], err: '', problems: null, busy: false, importOi: null, importIo: null, importPr: [],
})

/** A research/import job started from the setup page. */
export interface AddJob { jobId: string; kind: 'research' | 'import'; fallbackId?: string; handled: boolean }
/** An inside-out run for one company: uploading the material, then following the server job. */
export interface IoRun { phase: 'uploading' | 'job'; jobId?: string; message: string; error?: string | null; problems?: unknown[] | null; handled: boolean; label: string }

interface IoState {
  docs: Record<number, Picked[]>
  other: Picked[]
  qFiles: QFile[]
  add: AddDraft
  addJob: AddJob | null
  ioRuns: Record<string, IoRun>

  addDocFiles: (slot: number, fs: Picked[]) => void
  removeDocFile: (slot: number, i: number) => void
  addOther: (fs: Picked[]) => void
  removeOther: (i: number) => void
  addQFile: (q: QFile) => void
  removeQFile: (i: number) => void
  dropQFile: (q: QFile) => void
  patchAdd: (p: Partial<AddDraft>) => void
  resetAdd: (tab?: AddTab) => void
  setAddJob: (j: AddJob | null) => void
  setIoRun: (cid: string, r: IoRun | null) => void
  patchIoRun: (cid: string, p: Partial<IoRun>) => void
  /** forget the material of the last run (company switched or a new assessment started) */
  resetRun: () => void
}

export const useInsideOut = create<IoState>()((set) => ({
  docs: {}, other: [], qFiles: [], add: newAdd(), addJob: null, ioRuns: {},
  addDocFiles: (slot, fs) => set((s) => ({ docs: { ...s.docs, [slot]: [...(s.docs[slot] || []), ...fs] } })),
  removeDocFile: (slot, i) => set((s) => ({ docs: { ...s.docs, [slot]: (s.docs[slot] || []).filter((_, k) => k !== i) } })),
  addOther: (fs) => set((s) => ({ other: [...s.other, ...fs] })),
  removeOther: (i) => set((s) => ({ other: s.other.filter((_, k) => k !== i) })),
  addQFile: (q) => set((s) => ({ qFiles: [...s.qFiles, q] })),
  removeQFile: (i) => set((s) => ({ qFiles: s.qFiles.filter((_, k) => k !== i) })),
  dropQFile: (q) => set((s) => ({ qFiles: s.qFiles.filter((x) => x !== q) })),
  patchAdd: (p) => set((s) => ({ add: { ...s.add, ...p } })),
  resetAdd: (tab) => set({ add: newAdd(tab) }),
  setAddJob: (addJob) => set({ addJob }),
  setIoRun: (cid, r) => set((s) => {
    const ioRuns = { ...s.ioRuns }
    if (r) ioRuns[cid] = r; else delete ioRuns[cid]
    return { ioRuns }
  }),
  patchIoRun: (cid, p) => set((s) => (s.ioRuns[cid] ? { ioRuns: { ...s.ioRuns, [cid]: { ...s.ioRuns[cid], ...p } } } : s)),
  resetRun: () => set({ docs: {}, other: [], qFiles: [] }),
}))

/** an inside-out run is in flight for this company (uploading or being scored): one paid run at a time each */
export const selectIoBusy = (cid: string | null) => (s: IoState) => {
  const r = cid ? s.ioRuns[cid] : undefined
  return !!r && !r.error
}

