import { useRef, type KeyboardEvent, type ReactNode } from 'react';
import { Group } from '@visx/group';
import { scaleBand, scaleLinear } from '@visx/scale';
import { TooltipWithBounds, defaultStyles, useTooltip } from '@visx/tooltip';
import {
  Bar,
  BarChart,
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  PolarAngleAxis,
  PolarGrid,
  PolarRadiusAxis,
  Radar,
  RadarChart,
  ResponsiveContainer,
  Tooltip as RTooltip,
  XAxis,
  YAxis,
} from 'recharts';
import type { Score } from '../api/viewTypes';
import { useReportUi } from '../store/reportUi';
import { DIMS, NAVY, PEER_COLORS, SCORE_COLOR, gval, scoreColor, typo, useReport } from './context';
import { Tip } from './parts';

/* Charts of the board dashboard. Standard charts use Recharts; the matrix and dot plot are drawn with visx.
   Every chart has an accessible name and a visually hidden data table with the same numbers. */

const LETTER: Record<number, string> = { 5: 'A', 4: 'B', 3: 'C', 2: 'D', 1: 'F', 0: '' };
const letterTick = (v: number) => LETTER[v] ?? '';

function SrTable({ caption, head, rows }: { caption: string; head: string[]; rows: (string | number | null)[][] }) {
  return (
    <table className="sr-only">
      <caption>{caption}</caption>
      <thead>
        <tr>
          {head.map((h) => (
            <th key={h} scope="col">
              {h}
            </th>
          ))}
        </tr>
      </thead>
      <tbody>
        {rows.map((r, i) => (
          <tr key={i}>
            {r.map((c, j) => (j === 0 ? <th key={j} scope="row">{c}</th> : <td key={j}>{c ?? 'n/a'}</td>))}
          </tr>
        ))}
      </tbody>
    </table>
  );
}

function Figure({ label, children, className = '' }: { label: string; children: ReactNode; className?: string }) {
  return (
    <figure className={`m-0 ${className}`} aria-label={label}>
      {children}
    </figure>
  );
}

/* ------------------------------------------------------------------ at a glance: indicator matrix (visx) */

export function IndicatorHeatmap({ scores }: { scores: Record<string, Score> }) {
  const { ids, dimOf, indName, dimLabel } = useReport();
  const openInd = useReportUi((s) => s.openInd);
  const rows = DIMS.map((d) => ({ d, ids: ids.filter((i) => dimOf[i] === d) }));
  const cols = Math.max(1, ...rows.map((r) => r.ids.length));
  const LABEL = 270;
  const ROW = 58;
  const W = LABEL + cols * 54;
  const H = rows.length * ROW;
  const x = scaleBand<number>({ domain: Array.from({ length: cols }, (_, k) => k), range: [LABEL, W], padding: 0.12 });
  const y = scaleBand<string>({ domain: rows.map((r) => r.d), range: [0, H], padding: 0.1 });
  const cell = Math.min(x.bandwidth(), y.bandwidth(), 46);
  const act = (e: KeyboardEvent, id: string) => {
    if (e.key === 'Enter' || e.key === ' ') {
      e.preventDefault();
      openInd(id);
    }
  };
  return (
    <Figure label="Indicator heatmap: the score of each of the 22 indicators, grouped by dimension. Select a square for the rationale and evidence.">
      <svg viewBox={`0 0 ${W} ${H}`} className="block h-auto w-full max-w-[820px]" role="group" aria-label="Indicator scores by dimension">
        {rows.map(({ d, ids: rid }) => (
          <Group key={d} top={y(d) ?? 0}>
            <text x={0} y={y.bandwidth() / 2} dominantBaseline="middle" className="fill-[#002B49] text-[15px] font-bold">
              {d}. {typo(dimLabel(d))}
            </text>
            {rid.map((i, k) => {
              const s = scores[i];
              const label = `${i} ${indName(i)}, ${s == null ? 'not assessable' : 'score ' + s}`;
              return (
                <Tip key={i} label={`${i} ${typo(indName(i))}`}>
                  <g
                    role="button"
                    tabIndex={0}
                    aria-label={label}
                    onClick={() => openInd(i)}
                    onKeyDown={(e) => act(e, i)}
                    className="cursor-pointer outline-none [&:focus-visible>rect]:stroke-[#002B49] [&:focus-visible>rect]:stroke-[3px] hover:opacity-90"
                  >
                    <rect x={x(k) ?? 0} y={(y.bandwidth() - cell) / 2} width={cell} height={cell} rx={6} fill={scoreColor(s)} stroke="transparent" />
                    <text x={(x(k) ?? 0) + cell / 2} y={y.bandwidth() / 2} textAnchor="middle" dominantBaseline="middle" className="fill-white text-[14px] font-bold" pointerEvents="none">
                      {i}
                    </text>
                  </g>
                </Tip>
              );
            })}
          </Group>
        ))}
      </svg>
      <div className="mt-2 flex flex-wrap gap-x-4 gap-y-1 text-[0.8rem] text-[#646464]" aria-hidden="true">
        {[
          ['5', '5 Day 1'],
          ['4', '4'],
          ['3', '3 Mixed'],
          ['2', '2'],
          ['1', '1 Day 2'],
        ].map(([k, l]) => (
          <span key={k} className="inline-flex items-center gap-1.5">
            <i className="inline-block h-3 w-3 rounded-sm" style={{ background: SCORE_COLOR[k] }} />
            {l}
          </span>
        ))}
      </div>
      <SrTable caption="Indicator scores" head={['Indicator', 'Score']} rows={ids.map((i) => [`${i} ${indName(i)}`, scores[i] ?? null])} />
    </Figure>
  );
}

/* ------------------------------------------------------------------ dimension radar (Recharts) */

interface Series {
  name: string;
  /** grade per dimension */
  grades: (string | null)[];
  color: string;
}

export function DimensionRadar({ series }: { series: Series[] }) {
  const { dimLabel } = useReport();
  const data = DIMS.map((d, k) => {
    const row: Record<string, string | number> = { dim: `${d}. ${dimLabel(d)}` };
    series.forEach((s) => (row[s.name] = gval(s.grades[k])));
    return row;
  });
  return (
    <Figure label={`Radar chart of dimension grades for ${series.map((s) => s.name).join(', ')} (A at the outer ring, F at the centre).`} className="h-[340px] w-full">
      <ResponsiveContainer width="100%" height="100%">
        <RadarChart data={data} outerRadius="68%">
          <PolarGrid />
          <PolarAngleAxis dataKey="dim" tick={{ fontSize: 11, fill: NAVY }} />
          <PolarRadiusAxis angle={90} domain={[0, 5]} tickCount={6} tickFormatter={letterTick} tick={{ fontSize: 10 }} />
          {series.map((s) => (
            <Radar key={s.name} name={s.name} dataKey={s.name} stroke={s.color} fill={s.color} fillOpacity={0.12} isAnimationActive={false} />
          ))}
          <RTooltip formatter={(v) => letterTick(Number(v)) || 'n/a'} />
          <Legend wrapperStyle={{ fontSize: 12 }} />
        </RadarChart>
      </ResponsiveContainer>
      <SrTable caption="Dimension grades" head={['Dimension', ...series.map((s) => s.name)]} rows={DIMS.map((d, k) => [`${d}. ${dimLabel(d)}`, ...series.map((s) => s.grades[k] ?? null)])} />
    </Figure>
  );
}

/* ------------------------------------------------------------------ peer comparison bars (Recharts) */

function shortDim(d: string, label: string): string {
  return label.length > 15 ? `${d}. ${label.slice(0, 14).trim()}…` : `${d}. ${label}`;
}

export function PeerBars({ series }: { series: Series[] }) {
  const { dimLabel } = useReport();
  const data = DIMS.map((d, k) => {
    const row: Record<string, string | number> = { dim: shortDim(d, dimLabel(d)) };
    series.forEach((s) => (row[s.name] = gval(s.grades[k])));
    return row;
  });
  return (
    <Figure label={`Bar chart comparing dimension grades of ${series.map((s) => s.name).join(', ')}.`} className="h-[320px] w-full">
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={data} margin={{ top: 8, right: 8, bottom: 8, left: 0 }}>
          <CartesianGrid strokeDasharray="3 3" vertical={false} />
          <XAxis dataKey="dim" tick={{ fontSize: 11 }} interval={0} />
          <YAxis domain={[0, 5]} ticks={[1, 2, 3, 4, 5]} tickFormatter={letterTick} width={28} />
          <RTooltip formatter={(v) => letterTick(Number(v)) || 'n/a'} />
          <Legend wrapperStyle={{ fontSize: 12 }} />
          {series.map((s) => (
            <Bar key={s.name} dataKey={s.name} fill={s.color} radius={[3, 3, 0, 0]} isAnimationActive={false} />
          ))}
        </BarChart>
      </ResponsiveContainer>
      <SrTable caption="Dimension grades against the peer set" head={['Dimension', ...series.map((s) => s.name)]} rows={DIMS.map((d, k) => [`${d}. ${dimLabel(d)}`, ...series.map((s) => s.grades[k] ?? null)])} />
    </Figure>
  );
}

/* ------------------------------------------------------------------ grades by quarter (Recharts) */

const DIM_LINE_COLORS = ['#002B49', '#0085CA', '#00677F', '#CF7F00', '#722282', '#29702A'];

export interface TrendPoint {
  period: string;
  grades: (string | null)[];
  overall: string | null;
}

export function TrendLines({ points }: { points: TrendPoint[] }) {
  const { dimLabel } = useReport();
  const data = points.map((p) => {
    const row: Record<string, string | number | undefined> = { period: p.period };
    DIMS.forEach((d, k) => (row[`d${d}`] = p.grades[k] ? gval(p.grades[k]) : undefined));
    row.overall = p.overall ? gval(p.overall) : undefined;
    return row;
  });
  return (
    <Figure label="Line chart of dimension grades and the overall grade by quarter." className="h-[340px] w-full">
      <ResponsiveContainer width="100%" height="100%">
        <LineChart data={data} margin={{ top: 8, right: 16, bottom: 8, left: 0 }}>
          <CartesianGrid strokeDasharray="3 3" vertical={false} />
          <XAxis dataKey="period" tick={{ fontSize: 12 }} />
          <YAxis domain={[0, 5]} ticks={[1, 2, 3, 4, 5]} tickFormatter={letterTick} width={28} />
          <RTooltip formatter={(v) => letterTick(Number(v)) || 'n/a'} />
          <Legend wrapperStyle={{ fontSize: 11 }} />
          {DIMS.map((d, k) => (
            <Line key={d} type="monotone" dataKey={`d${d}`} name={`${d}. ${dimLabel(d)}`} stroke={DIM_LINE_COLORS[k]} strokeWidth={2} dot={{ r: 3 }} connectNulls isAnimationActive={false} />
          ))}
          <Line type="monotone" dataKey="overall" name="Overall" stroke="#646464" strokeWidth={3} strokeDasharray="6 4" dot={{ r: 4 }} connectNulls isAnimationActive={false} />
        </LineChart>
      </ResponsiveContainer>
      <SrTable
        caption="Grades by quarter"
        head={['Dimension', ...points.map((p) => p.period)]}
        rows={[...DIMS.map((d, k) => [`${d}. ${dimLabel(d)}`, ...points.map((p) => p.grades[k] ?? null)]), ['Overall', ...points.map((p) => p.overall)]]}
      />
    </Figure>
  );
}

/* ------------------------------------------------------------------ peer-relative indicator dot plot (visx) */

interface DotTip {
  text: string;
}

export function PeerDotPlot({ rows }: { rows: string[] }) {
  const { model, co, indName } = useReport();
  const ref = useRef<HTMLDivElement>(null);
  const { tooltipData, tooltipLeft, tooltipTop, tooltipOpen, showTooltip, hideTooltip } = useTooltip<DotTip>();
  const subjects = [{ name: co, color: NAVY, sc: model.oiSc }, ...model.peers.map((p, k) => ({ name: p.name, color: PEER_COLORS[k % PEER_COLORS.length], sc: p.sc }))];
  const LABEL = 280;
  const W = 820;
  const ROW = 56;
  const H = rows.length * ROW + 30;
  const x = scaleLinear<number>({ domain: [1, 5], range: [LABEL + 20, W - 24] });
  const y = scaleBand<string>({ domain: rows, range: [0, rows.length * ROW], padding: 0.1 });
  const off = (k: number) => (k - (subjects.length - 1) / 2) * 11;
  return (
    <Figure label="Dot plot of the peer-relative indicator scores for the company and each peer, on a scale of 1 (Day 2) to 5 (Day 1)." className="relative">
      <div ref={ref} className="relative">
        <svg viewBox={`0 0 ${W} ${H}`} className="block h-auto w-full max-w-[860px]" role="img" aria-label="Peer-relative indicator scores">
          {[1, 2, 3, 4, 5].map((t) => (
            <g key={t}>
              <line x1={x(t)} x2={x(t)} y1={0} y2={rows.length * ROW} stroke="#ECECEC" />
              <text x={x(t)} y={rows.length * ROW + 18} textAnchor="middle" className="fill-[#646464] text-[12px]">
                {t}
              </text>
            </g>
          ))}
          {rows.map((i) => (
            <Group key={i} top={y(i) ?? 0}>
              <text x={0} y={y.bandwidth() / 2} dominantBaseline="middle" className="fill-[#002B49] text-[13px]">
                {i} {typo(indName(i)).slice(0, 36)}
                {indName(i).length > 36 ? '…' : ''}
              </text>
              <line x1={x(1)} x2={x(5)} y1={y.bandwidth() / 2} y2={y.bandwidth() / 2} stroke="#D9D9D9" />
              {subjects.map((s, k) => {
                const v = s.sc[i];
                if (v == null) return null;
                return (
                  <circle
                    key={s.name}
                    cx={x(v)}
                    cy={y.bandwidth() / 2 + off(k)}
                    r={6}
                    fill={s.color}
                    stroke="#fff"
                    strokeWidth={1.5}
                    onMouseMove={(e) => {
                      const r = ref.current?.getBoundingClientRect();
                      showTooltip({ tooltipData: { text: `${s.name}: ${v} · ${i} ${indName(i)}` }, tooltipLeft: e.clientX - (r?.left ?? 0), tooltipTop: e.clientY - (r?.top ?? 0) });
                    }}
                    onMouseLeave={hideTooltip}
                  />
                );
              })}
            </Group>
          ))}
        </svg>
        {tooltipOpen && tooltipData ? (
          <TooltipWithBounds left={tooltipLeft} top={tooltipTop} style={{ ...defaultStyles, background: NAVY, color: '#fff', fontSize: 12 }}>
            {tooltipData.text}
          </TooltipWithBounds>
        ) : null}
      </div>
      <div className="mt-1 flex flex-wrap gap-x-4 gap-y-1 text-[0.8rem] text-[#646464]" aria-hidden="true">
        {subjects.map((s) => (
          <span key={s.name} className="inline-flex items-center gap-1.5">
            <i className="inline-block h-3 w-3 rounded-full" style={{ background: s.color }} />
            {s.name}
          </span>
        ))}
      </div>
      <SrTable caption="Peer-relative indicator scores" head={['Indicator', ...subjects.map((s) => s.name)]} rows={rows.map((i) => [`${i} ${indName(i)}`, ...subjects.map((s) => s.sc[i] ?? null)])} />
    </Figure>
  );
}

export type { Series };
