import { createContext, useContext, useMemo, type ReactNode } from 'react';
import type {
  Action,
  Evidence,
  Grade,
  HistoryEntry,
  Model,
  OverallResult,
  PriorAction,
  Score,
  ScoreSet,
  DimResult,
  View,
} from '../api/viewTypes';
import type { Stage } from '../store/reportUi';

/* ------------------------------------------------------------------ constants (js/engine.js, js/report.js) */

export const DIMS = ['1', '2', '3', '4', '5', '6'] as const;
export const DIMN: Record<string, string> = {
  '1': 'Customer Obsession',
  '2': 'Resisting Proxies',
  '3': 'Embracing External Trends',
  '4': 'High-Velocity Decision-Making',
  '5': 'Building over Protecting',
  '6': 'Liquidity and Capital Management',
};
export const GV: Record<string, number> = { A: 5, B: 4, C: 3, D: 2, F: 1 };
export const DRAFT = 'DRAFT ONLY - Requires review and approval by a qualified Alvarez and Marsal professional before use.';
export const RUN_CIRC: Record<string, string> = {
  director_request: 'Requesting director and engagement team',
  internal_dry_run: 'A&M team only',
  methodology_pilot: 'Methodology team only',
};
export const PEER_RELATIVE = ['3.2', '5.1', '6.1', '6.2'];

/** A&M palette: grades and scores are data highlights. */
export const GRADE_COLOR: Record<string, string> = { A: '#00677F', B: '#0085CA', C: '#5E8AB4', D: '#CF7F00', F: '#A6192E', NA: '#969696' };
export const SCORE_COLOR: Record<string, string> = { '1': '#A6192E', '2': '#CF7F00', '3': '#5E8AB4', '4': '#0085CA', '5': '#00677F', NA: '#969696' };
export const PEER_COLORS = ['#5E8AB4', '#CF7F00', '#722282', '#29702A', '#C8187D'];
export const NAVY = '#002B49';

export function gradeColor(g: string | null | undefined): string {
  return GRADE_COLOR[g || 'NA'] || GRADE_COLOR.NA;
}
export function scoreColor(s: Score | undefined): string {
  return s == null ? SCORE_COLOR.NA : SCORE_COLOR[String(s)] || SCORE_COLOR.NA;
}
export function gval(g: string | null | undefined): number {
  return (g && GV[g]) || 0;
}

/** typographic apostrophes, as the legacy esc() applied to every string it printed */
export function typo(s: unknown): string {
  return String(s == null ? '' : s)
    .replace(/(\w)'(\w)/g, '$1’$2')
    .replace(/(\w)'(\s)/g, '$1’$2');
}
export function firstSentence(t: unknown): string {
  const x = String(t || '').trim();
  const k = x.search(/\.\s/);
  return k > 0 ? x.slice(0, k + 1) : x;
}
export function listJoin(a: string[]): string {
  return a.length < 2 ? a.join('') : a.slice(0, -1).join(', ') + ' and ' + a[a.length - 1];
}

/* ------------------------------------------------------------------ normalised grade model */

export interface NDim {
  assessed: number;
  of: number;
  reported: boolean;
  grade: Grade | null;
  avg: number | null;
  label: string;
}
export interface NOverall {
  n: number;
  grade: Grade | null;
  avg: number | null;
  provisional: boolean;
  label: string;
}
export interface NScore {
  dims: Record<string, NDim>;
  overall: NOverall;
  assessed: number;
}
export interface NPeer {
  name: string;
  full: string;
  sc: Record<string, Score>;
  c: NScore;
}
export interface NModel {
  oiSc: Record<string, Score>;
  ioSc: Record<string, Score>;
  oi: NScore;
  io: NScore;
  peers: NPeer[];
}
export interface NHistory {
  period: string;
  stage: string;
  ind: Record<string, Score>;
  dims: Record<string, NDim>;
  overall: NOverall;
  actions: HistoryEntry['actions'];
}
export interface IoView {
  score: Score;
  conf: string | null;
  rat: string;
  ev: string[];
  carried: boolean;
}

const nullDim = (of = 0): NDim => ({ assessed: 0, of, reported: false, grade: null, avg: null, label: 'Insufficient evidence' });
const nullOverall = (): NOverall => ({ n: 0, grade: null, avg: null, provisional: false, label: 'No overall grade' });

function normDim(d: DimResult | undefined, of: number): NDim {
  if (!d) return nullDim(of);
  const grade = (d.grade as Grade | null) ?? null;
  return { assessed: d.assessed ?? 0, of: d.of ?? of, reported: d.reported ?? grade != null, grade, avg: d.avg ?? d.average ?? null, label: d.label || 'Insufficient evidence' };
}
function normOverall(o: OverallResult | undefined | null): NOverall {
  if (!o) return nullOverall();
  const grade = (o.grade as Grade | null) ?? null;
  return { n: o.n ?? o.dimensions_reported ?? 0, grade, avg: o.avg ?? o.numeric_average ?? null, provisional: !!o.provisional, label: o.label || (grade ? '' : 'No overall grade') };
}
function normScoreSet(s: ScoreSet | undefined, dimOf: Record<string, string>, ids: string[]): NScore {
  const raw = s?.dims ?? s?.dimensions ?? {};
  const dims: Record<string, NDim> = {};
  DIMS.forEach((d) => (dims[d] = normDim(raw[d], ids.filter((i) => dimOf[i] === d).length)));
  return { dims, overall: normOverall(s?.overall), assessed: s?.assessed ?? 0 };
}

/**
 * Grades come from the server (view.model). If an older server omits them, the grades the view already carries
 * (scorecard, peer grades, overall) are shown; nothing is graded here.
 */
function buildModel(view: View, ids: string[], dimOf: Record<string, string>, ioScores: Record<string, Score>): NModel {
  const m: Model | undefined = view.model;
  const oiSc: Record<string, Score> = {};
  ids.forEach((i) => (oiSc[i] = view.ind[i]?.score ?? null));
  if (m) {
    return {
      oiSc: m.oiSc ?? oiSc,
      ioSc: m.ioSc ?? ioScores,
      oi: normScoreSet(m.oi, dimOf, ids),
      io: normScoreSet(m.io, dimOf, ids),
      peers: (m.peers || []).map((p) => ({ name: p.name, full: p.full, sc: p.sc, c: normScoreSet(p.c, dimOf, ids) })),
    };
  }
  const count = (sc: Record<string, Score>, d: string) => ids.filter((i) => dimOf[i] === d && sc[i] != null).length;
  const of = (d: string) => ids.filter((i) => dimOf[i] === d).length;
  const scale = view.scale || [];
  const lab = (g: Grade | null) => scale.find((b) => b.grade === g)?.label || '';
  const fromGrades = (grades: (Grade | null | undefined)[], sc: Record<string, Score>, overall?: OverallResult | null): NScore => {
    const dims: Record<string, NDim> = {};
    DIMS.forEach((d, k) => {
      const g = grades[k] ?? null;
      dims[d] = { assessed: count(sc, d), of: of(d), reported: g != null, grade: g, avg: null, label: g ? lab(g) : 'Insufficient evidence' };
    });
    const og = (grades[6] ?? overall?.grade ?? null) as Grade | null;
    const n = DIMS.filter((d) => dims[d].reported).length;
    const o = overall ? normOverall(overall) : { ...nullOverall(), n, grade: og, label: og ? lab(og) : 'No overall grade', provisional: n === 3 };
    return { dims, overall: { ...o, n: o.n || n }, assessed: ids.filter((i) => sc[i] != null).length };
  };
  const oiGrades = DIMS.map((_, k) => view.scorecard?.[k]?.grade ?? null);
  oiGrades.push((view.scorecard?.[6]?.grade ?? view.overall?.oi?.grade ?? null) as Grade | null);
  const io: NScore = view.io
    ? {
        dims: Object.fromEntries(DIMS.map((d) => [d, nullDim(of(d))])),
        overall: normOverall(view.overall?.io),
        assessed: ids.filter((i) => ioScores[i] != null).length,
      }
    : normScoreSet(undefined, dimOf, ids);
  return {
    oiSc,
    ioSc: ioScores,
    oi: fromGrades(oiGrades, oiSc, view.overall?.oi),
    io,
    peers: (view.peers || []).map((p, k) => {
      const sc: Record<string, Score> = {};
      ids.forEach((i) => (sc[i] = p.ind?.[i]?.score ?? null));
      return { name: view.meta.peer_short?.[k] ?? '', full: view.meta.peers?.[k] ?? '', sc, c: fromGrades(p.grades || [], sc) };
    }),
  };
}

function buildHistory(view: View, ids: string[], dimOf: Record<string, string>): NHistory[] {
  if (view.history) {
    return view.history.map((h) => ({
      period: h.period,
      stage: h.stage,
      ind: h.ind,
      dims: normScoreSet({ dims: h.dims, dimensions: h.dimensions, overall: h.overall }, dimOf, ids).dims,
      overall: normOverall(h.overall),
      actions: h.actions || [],
    }));
  }
  const p = view.prior;
  if (!p) return [];
  return [
    {
      period: p.period,
      stage: p.stage,
      ind: p.scores,
      dims: Object.fromEntries(DIMS.map((d) => [d, nullDim(ids.filter((i) => dimOf[i] === d).length)])),
      overall: nullOverall(),
      actions: p.actions || [],
    },
  ];
}

/* ------------------------------------------------------------------ context */

export interface ReportCtx {
  view: View;
  stage: Stage;
  /** stage is inside-out and the view has an inside-out result */
  io: boolean;
  ids: string[];
  dimOf: Record<string, string>;
  model: NModel;
  history: NHistory[];
  last: NHistory | null;
  /** scores of the stage being read */
  now: Record<string, Score>;
  /** grade set of the stage being read (outside-in or post inside-out) */
  L: NScore;
  O: NScore;
  co: string;
  cofull: string;
  tk: string;
  peers: string[];
  peerFull: string[];
  headline: string;
  actions: Action[];
  indName: (i: string) => string;
  labelOf: (g: string | null | undefined) => string;
  ioCell: (i: string) => IoView;
  evOf: (c: string) => Evidence | null;
  indLine: (i: string) => string;
  prefixes: Record<string, string>;
  priorActions: PriorAction[];
  evWindow: string;
  dimLabel: (d: string) => string;
  fileUrl: (k: string) => string | null;
}

const Ctx = createContext<ReportCtx | null>(null);

export function makeReportCtx(view: View, requested: Stage): ReportCtx {
  const ids = Object.keys(view.ind || {})
    .filter((i) => /^\d+\.\d+$/.test(i))
    .sort((a, b) => a.localeCompare(b, undefined, { numeric: true }));
  const dimOf: Record<string, string> = {};
  ids.forEach((i) => (dimOf[i] = i[0]));
  const stage: Stage = requested === 'io' && view.io ? 'io' : 'oi';
  const io = stage === 'io';

  const ioCell = (i: string): IoView => {
    const o = view.ind[i];
    const c = view.io?.cells?.[i];
    if (c) return { score: c.score, conf: (c.conf as string | null) ?? null, rat: c.rationale, ev: c.ev || [], carried: !!c.carried };
    return {
      score: o?.score ?? null,
      conf: (o?.conf as string | null) ?? null,
      rat: 'Carried forward: nothing supplied settles this indicator, so the outside-in score stands.',
      ev: o?.ev || [],
      carried: true,
    };
  };
  const ioScores: Record<string, Score> = {};
  ids.forEach((i) => (ioScores[i] = ioCell(i).score));
  const model = buildModel(view, ids, dimOf, ioScores);
  const history = buildHistory(view, ids, dimOf);
  const last = history.length ? history[history.length - 1] : null;
  const co = view.meta.short || view.meta.company;
  const labelOf = (g: string | null | undefined) => view.scale?.find((b) => b.grade === g)?.label || '';

  const priorActions: PriorAction[] = (() => {
    const pa = view.io?.prior_actions;
    if (pa && pa.length) return pa.map((a) => ({ id: a.id, heading: a.heading, status: a.status, note: a.note, metrics: a.metrics }));
    if (last && last.actions && last.actions.length)
      return last.actions.map((a) => ({
        id: a.id ?? null,
        heading: a.heading,
        status: 'no_public_evidence',
        note: 'Status needs the action tracker or minutes; none supplied in this run.',
        metrics: (a.measures || []).join('; '),
      }));
    return [];
  })();

  const prefixes: Record<string, string> = (() => {
    if (view.meta.prefixes && Object.keys(view.meta.prefixes).length) return view.meta.prefixes;
    const p: Record<string, string> = { E: co };
    ['X', 'B', 'K', 'L', 'N'].slice(0, view.meta.peer_short.length).forEach((k, i) => (p[k] = view.meta.peer_short[i]));
    return p;
  })();

  const evWindow = (() => {
    const d = new Date(view.meta.date || Date.now());
    if (isNaN(d.getTime())) return 'Behaviour indicators over 24 months; trend indicators over five years.';
    return 'Behaviour indicators from ' + (d.getFullYear() - 2) + '-' + String(d.getMonth() + 1).padStart(2, '0') + '; trend indicators from FY' + (d.getFullYear() - 5) + '.';
  })();

  return {
    view,
    stage,
    io,
    ids,
    dimOf,
    model,
    history,
    last,
    now: io ? model.ioSc : model.oiSc,
    L: io ? model.io : model.oi,
    O: model.oi,
    co,
    cofull: view.meta.company,
    tk: view.meta.ticker,
    peers: view.meta.peer_short || [],
    peerFull: view.meta.peers || [],
    headline: io && view.io ? view.io.headline : view.headline,
    actions: io && view.io ? view.io.actions : view.actions,
    indName: (i) => view.ind[i]?.name ?? i,
    labelOf,
    ioCell,
    evOf: (c) => view.ev?.[c] ?? view.io?.ev?.[c] ?? null,
    indLine: (i) => {
      const x = (view.ind_summary || []).find((r) => String(r.name).split(' ')[0] === i);
      return x && x.line ? x.line : firstSentence(view.ind[i]?.rationale);
    },
    prefixes,
    priorActions,
    evWindow,
    dimLabel: (d) => {
      const row = view.scorecard?.[Number(d) - 1];
      const m = row?.dim?.match(/^\d+\.\s*(.*)$/);
      return m?.[1] || DIMN[d] || d;
    },
    fileUrl: (k) => view.files?.[k] || null,
  };
}

export function ReportProvider({ view, stage, children }: { view: View; stage: Stage; children: ReactNode }) {
  const value = useMemo(() => makeReportCtx(view, stage), [view, stage]);
  return <Ctx.Provider value={value}>{children}</Ctx.Provider>;
}

export function useReport(): ReportCtx {
  const c = useContext(Ctx);
  if (!c) throw new Error('useReport must be used inside <ReportProvider>');
  return c;
}
