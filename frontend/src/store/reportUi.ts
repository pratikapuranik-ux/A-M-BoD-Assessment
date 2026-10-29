import { create } from 'zustand';

export type Stage = 'oi' | 'io';
export type DashTab = 'overview' | 'indicators' | 'inside' | 'peers' | 'trend' | 'actions';
export type Dialog = { kind: 'ev'; id: string } | { kind: 'ind'; id: string } | null;

interface ReportUi {
  /** the reading stage when the view has an inside-out result (combined mode) */
  stage: Stage;
  /** sub-tab of the dashboard, which is still shown in its own dialog */
  dashTab: DashTab;
  /** sources filter: 'all', an evidence prefix, or 'io' */
  srcFilter: string;
  srcQuery: string;
  /** scorecard dimensions that are expanded to their indicators */
  openDims: string[];
  dialog: Dialog;
  setStage: (s: Stage) => void;
  setDashTab: (t: DashTab) => void;
  setSrcFilter: (f: string) => void;
  setSrcQuery: (q: string) => void;
  toggleDim: (d: string) => void;
  openEv: (code: string) => void;
  openInd: (id: string) => void;
  closeDialog: () => void;
  reset: () => void;
}

const initial = {
  stage: 'io' as Stage,
  dashTab: 'overview' as DashTab,
  srcFilter: 'all',
  srcQuery: '',
  openDims: [] as string[],
  dialog: null as Dialog,
};

/** UI state of the report: reading stage, filters and the open dialog. Holds no assessment data. */
export const useReportUi = create<ReportUi>((set) => ({
  ...initial,
  setStage: (stage) => set({ stage }),
  setDashTab: (dashTab) => set({ dashTab }),
  setSrcFilter: (srcFilter) => set({ srcFilter }),
  setSrcQuery: (srcQuery) => set({ srcQuery }),
  toggleDim: (d) => set((s) => ({ openDims: s.openDims.includes(d) ? s.openDims.filter((x) => x !== d) : [...s.openDims, d] })),
  openEv: (id) => set({ dialog: { kind: 'ev', id } }),
  openInd: (id) => set({ dialog: { kind: 'ind', id } }),
  closeDialog: () => set({ dialog: null }),
  reset: () => set({ ...initial }),
}));
