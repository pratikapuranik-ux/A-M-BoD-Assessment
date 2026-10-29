/**
 * The "view" model: the JSON the server returns for a company (shape of server/convert.py `to_view`,
 * sample in tests/fixtures/example_view.js). The browser renders it and never grades.
 *
 * Grades are computed by the backend. Where the server includes them they arrive as `model` (the result of
 * backend engine.model(view)) and `history` (engine.build_history); both accept the legacy key names
 * (`dims`, `avg`, `n`) and the backend names (`dimensions`, `average`, `numeric_average`, `dimensions_reported`).
 */

export type Grade = 'A' | 'B' | 'C' | 'D' | 'F';
/** An indicator score: 1 (Day 2) to 5 (Day 1); null = not assessable. */
export type Score = number | null;
export type Confidence = 'High' | 'Medium' | 'Low' | string | null;
export type RunMode = 'director_request' | 'internal_dry_run' | 'methodology_pilot' | string;
export type RunStage = 'outside_in' | 'inside_out';
export type ActionStatus = 'completed' | 'on_track' | 'behind' | 'not_started' | 'no_public_evidence' | string;

export interface Meta {
  id: string;
  company: string;
  short: string;
  ticker: string;
  period: string;
  date: string;
  peers: string[];
  peer_short: string[];
  mode: RunMode;
  /** evidence-code letter prefix -> subject short name */
  prefixes?: Record<string, string>;
  source?: string;
}

/** An outside-in indicator cell for the company. */
export interface Cell {
  name: string;
  score: Score;
  rationale: string;
  conf: Confidence;
  ev: string[];
  /** not-assessable cause */
  na?: string | null;
}

export interface PeerCell {
  score: Score;
  rationale: string;
  ev: string[];
  na?: string | null;
}

export interface Subject {
  /** six dimension grades then the overall grade */
  grades: (Grade | null)[];
  ind: Record<string, PeerCell>;
  summary: string;
}
/** A peer is a Subject (name comes from meta.peers / meta.peer_short by position). */
export type Peer = Subject;

export interface Evidence {
  doc: string;
  date: string;
  cls?: string | null;
  origin?: string | null;
  recent?: boolean;
  excerpt?: string;
  url?: string;
  question?: string;
  search?: unknown;
  used?: string;
}

export interface Action {
  n: string;
  heading: string;
  description: string;
  measures: string[];
  target: string;
}

export interface ScorecardRow {
  dim: string;
  grade: Grade | null;
  line: string;
}

export interface IndSummary {
  name: string;
  score: Score;
  line: string;
}

export interface DimText {
  title: string;
  text: string;
  limit: string;
}

export interface Dimension {
  id: string;
  name: string;
}

export interface Def {
  def: string;
  prompt: string;
  anchors: Record<'1' | '3' | '5', string>;
}

export interface ScaleBand {
  min: number;
  grade: Grade;
  label: string;
}

export interface IoCell {
  score: number;
  conf: Confidence;
  rationale: string;
  ev: string[];
  carried?: boolean;
}

export interface PriorAction {
  id: string | null;
  heading: string;
  status: ActionStatus;
  note: string;
  metrics: string;
}

export interface BackOnTrack {
  id: string | null;
  heading: string;
  what: string;
  impact: string;
  cause: string;
  prevent: string;
  measures: string[];
}

export interface InsideOut {
  /** only the indicators the board's own material re-scored; the rest carry forward */
  cells: Record<string, IoCell>;
  ev: Record<string, Evidence>;
  headline: string;
  drives: string;
  better: string[];
  worse: string[];
  actions: Action[];
  prior_actions: PriorAction[];
  back: BackOnTrack[];
  sa: string[];
  ratings: Record<string, number>;
  date?: string;
}

export interface PriorActionSource {
  id?: string;
  heading: string;
  description?: string;
  measures?: string[];
  target_by?: string;
}

/** An earlier assessment on file (view.prior / view.priors). */
export interface Prior {
  period: string;
  stage: RunStage;
  scores: Record<string, Score>;
  actions: PriorActionSource[];
}

// ---- grades computed by the backend ----

export interface DimResult {
  assessed: number;
  of: number;
  reported: boolean;
  grade: Grade | null;
  label: string;
  avg?: number | null;
  average?: number | null;
}
export interface OverallResult {
  grade: Grade | null;
  label: string;
  provisional?: boolean;
  n?: number;
  dimensions_reported?: number;
  avg?: number | null;
  numeric_average?: number | null;
}
export interface ScoreSet {
  dims?: Record<string, DimResult>;
  dimensions?: Record<string, DimResult>;
  overall: OverallResult;
  assessed?: number;
}
export interface PeerModel {
  name: string;
  full: string;
  sc: Record<string, Score>;
  c: ScoreSet;
}
export interface Model {
  oiSc: Record<string, Score>;
  ioSc: Record<string, Score>;
  oi: ScoreSet;
  io: ScoreSet;
  peers: PeerModel[];
}
export interface HistoryEntry {
  period: string;
  stage: RunStage;
  ind: Record<string, Score>;
  dims?: Record<string, DimResult>;
  dimensions?: Record<string, DimResult>;
  overall: OverallResult;
  actions: PriorActionSource[];
}

export interface ReconciliationRow {
  subject: string;
  role: 'company' | 'peer';
  indicator: string;
  name: string;
  a: number | null;
  b: number | null;
  final: number | null;
  chosen: 'A' | 'B';
  reason: string;
}
/** Two independent scoring runs and how their disagreements were settled. */
export interface Reconciliation {
  models: { A: { model: string; effort: string }; B: { model: string; effort: string } };
  agreed: number;
  total: number;
  rows: ReconciliationRow[];
}

export interface View {
  reconciliation?: Reconciliation;
  meta: Meta;
  headline: string;
  overall_line: string;
  drives: string;
  actions: Action[];
  /** [metric, why it matters, now] */
  metrics: [string, string, string][];
  position: string;
  position_lines: string[];
  /** six dimension rows then an "Overall" row */
  scorecard: ScorecardRow[];
  coverage_note: string;
  ind_summary: IndSummary[];
  /** header row, six dimension rows, overall row; the last column is the written comparison */
  peer_table: (string | Grade | null)[][];
  addl: string[];
  dimtext: Record<string, DimText>;
  ind: Record<string, Cell>;
  peers: Peer[];
  read: string[];
  method: string[];
  ev: Record<string, Evidence>;
  defs: Record<string, Def>;
  io: InsideOut | null;
  prior: Prior | null;
  priors?: Prior[];
  docs: [string, string][] | string[][];
  q: [string, string, string][] | string[][];
  modes: Record<string, string>;
  scale: ScaleBand[];
  findings_oi: string[];
  findings_io: string[];
  overall?: { oi?: OverallResult; io?: OverallResult };
  /** deliverable key (oi_docx, io_docx, oi_html, io_html, quest ...) -> download URL */
  files?: Record<string, string>;
  /** backend-computed grades (engine.model); preferred over any local fallback */
  model?: Model;
  /** backend-computed trend entries for the earlier assessments the user picked (oldest first) */
  history?: HistoryEntry[];
}

// ---- survey page (GET/POST /api/survey/{token}) ----

export interface SurveyQuestion {
  n: number;
  dimension: string;
  dimension_name: string;
  text: string;
}
export interface SurveyForm {
  company: string;
  period: string;
  responded: boolean;
  min: number;
  questions: SurveyQuestion[];
}
