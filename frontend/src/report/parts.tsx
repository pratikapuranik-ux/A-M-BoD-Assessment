import type { ReactNode } from 'react';
import * as Tooltip from '@radix-ui/react-tooltip';
import type { Score, View } from '../api/viewTypes';
import { useReportUi } from '../store/reportUi';
import { gradeColor, gval, scoreColor, typo, useReport } from './context';

/* Shared building blocks of the report: type, tables, grade and score cells, evidence codes. */

export const NAVY = '#002B49';
export const th = 'bg-[#EFF3F8] px-3 py-2 text-left align-bottom text-[0.78rem] font-bold text-[#002B49] border-b border-[#D9D9D9]';
export const td = 'px-3 py-2 align-top border-b border-[#ECECEC] text-[0.9rem] leading-relaxed';
export const btnCls =
  'inline-flex items-center justify-center gap-2 rounded-lg border border-[#D9D9D9] bg-white px-4 py-2 text-sm font-bold text-[#002B49] hover:border-[#0085CA] focus-visible:outline focus-visible:outline-2 focus-visible:outline-[#0085CA] print:hidden';

export function Eb({ children, className = '' }: { children: ReactNode; className?: string }) {
  return <div className={`mb-2 mt-6 text-[0.72rem] font-bold uppercase tracking-[0.16em] text-[#0085CA] ${className}`}>{children}</div>;
}
export function H2({ children, className = '' }: { children: ReactNode; className?: string }) {
  return <h2 className={`mb-4 text-[1.5rem] font-bold leading-snug tracking-tight text-[#002B49] ${className}`}>{children}</h2>;
}
export function H3({ children, className = '' }: { children: ReactNode; className?: string }) {
  return <h3 className={`mb-2 mt-4 text-[1.08rem] font-bold text-[#002B49] ${className}`}>{children}</h3>;
}
export function Muted({ children, className = '', as: As = 'p' }: { children: ReactNode; className?: string; as?: 'p' | 'div' | 'span' }) {
  return <As className={`mb-3 text-[0.9rem] text-[#646464] ${className}`}>{children}</As>;
}
export function Section({ children, id, className = '' }: { children: ReactNode; id?: string; className?: string }) {
  return (
    <section id={id} className={`mb-8 rounded-xl border border-[#ECECEC] bg-white px-6 py-5 shadow-sm print:break-inside-avoid-page print:border-0 print:shadow-none ${className}`}>
      {children}
    </section>
  );
}
export function Notice({ children, tone = 'info' }: { children: ReactNode; tone?: 'info' | 'bad' }) {
  return (
    <div role={tone === 'bad' ? 'alert' : undefined} className={`mb-4 rounded-r-lg border-l-[3px] px-4 py-3 text-[0.9rem] text-[#002B49] ${tone === 'bad' ? 'border-[#002B49] bg-[#EFF3F8]' : 'border-[#5E8AB4] bg-[#EFF3F8]'}`}>
      {children}
    </div>
  );
}
/** a table in its own horizontal scroll container */
export function DTable({ children, className = '', caption }: { children: ReactNode; className?: string; caption?: string }) {
  return (
    <div className="mb-3 overflow-x-auto">
      <table className={`w-full border-collapse ${className}`}>
        {caption ? <caption className="sr-only">{caption}</caption> : null}
        {children}
      </table>
    </div>
  );
}

/* ---------------------------------------------------------------- tooltips */

export function Tip({ label, children }: { label: ReactNode; children: ReactNode }) {
  return (
    <Tooltip.Root delayDuration={150}>
      <Tooltip.Trigger asChild>{children}</Tooltip.Trigger>
      <Tooltip.Portal>
        <Tooltip.Content sideOffset={6} className="z-[70] max-w-xs rounded-md bg-[#002B49] px-3 py-2 text-xs leading-snug text-white shadow-lg">
          {label}
          <Tooltip.Arrow className="fill-[#002B49]" />
        </Tooltip.Content>
      </Tooltip.Portal>
    </Tooltip.Root>
  );
}

/* ---------------------------------------------------------------- grades and scores */

/** table cell holding a letter grade on its colour */
export function GradeCell({ grade, className = '' }: { grade: string | null | undefined; className?: string }) {
  const { labelOf } = useReport();
  const label = labelOf(grade);
  const cell = (
    <td
      className={`border-b border-[#ECECEC] px-2 py-2 text-center align-middle font-bold text-white ${className}`}
      style={{ background: gradeColor(grade), minWidth: 52 }}
      aria-label={grade ? `Grade ${grade}${label ? ', ' + label : ''}` : 'Not graded'}
    >
      {grade || 'n/a'}
    </td>
  );
  return label ? <Tip label={label}>{cell}</Tip> : cell;
}
export function ScoreCell({ score, className = '' }: { score: Score | undefined; className?: string }) {
  return (
    <td
      className={`border-b border-[#ECECEC] px-2 py-2 text-center align-middle font-bold text-white ${className}`}
      style={{ background: scoreColor(score), minWidth: 52 }}
      aria-label={score == null ? 'Not assessable' : `Score ${score} of 5`}
    >
      {score == null ? 'n/a' : score}
    </td>
  );
}
export function GradeChip({ grade }: { grade: string | null | undefined }) {
  return (
    <span className="inline-block min-w-[1.6rem] rounded px-2 py-0.5 text-center text-[0.85rem] font-bold text-white" style={{ background: gradeColor(grade) }}>
      {grade || 'n/a'}
    </span>
  );
}
export function ScoreChip({ score }: { score: Score | undefined }) {
  return (
    <span className="inline-block min-w-[1.6rem] rounded px-2 py-0.5 text-center text-[0.85rem] font-bold text-white" style={{ background: scoreColor(score) }} aria-label={score == null ? 'Not assessable' : `Score ${score}`}>
      {score == null ? 'n/a' : score}
    </span>
  );
}
/** the score change cell: up / down by n, or a dash */
export function DeltaCell({ a, b }: { a: Score | undefined; b: Score | undefined }) {
  if (a == null || b == null || a === b) return <td className="w-[52px] border-b border-[#ECECEC] px-2 py-2 text-center text-[0.85rem]">–</td>;
  const d = b - a;
  return (
    <td className={`w-[52px] border-b border-[#ECECEC] px-2 py-2 text-center text-[0.85rem] ${d > 0 ? 'text-[#29702A]' : 'text-[#A6192E]'}`} aria-label={`${d > 0 ? 'Up' : 'Down'} ${Math.abs(d)}`}>
      {d > 0 ? '▲' : '▼'}
      <b className="block">{Math.abs(d)}</b>
    </td>
  );
}
/** grade movement in words */
export function Arrow({ now, prev }: { now: string | null | undefined; prev: string | null | undefined }) {
  if (!now || !prev) return null;
  const d = gval(now) - gval(prev);
  if (d > 0) return <span className="font-bold text-[#00677F]">▲ up from {prev}</span>;
  if (d < 0) return <span className="font-bold text-[#A6192E]">▼ down from {prev}</span>;
  return <span className="text-[0.9rem] text-[#646464]">▬ unchanged</span>;
}
export function GradeTile({ label, grade, sub, note }: { label: ReactNode; grade: string | null | undefined; sub: ReactNode; note?: ReactNode }) {
  const { labelOf } = useReport();
  return (
    <div className="min-w-[260px] flex-1 rounded-lg bg-[#EFF3F8] px-5 py-4">
      <Eb className="!mt-0">{label}</Eb>
      <div className="flex items-baseline gap-3">
        <span className="text-5xl font-bold leading-none" style={{ color: gradeColor(grade) }} aria-hidden="true">
          {grade || '–'}
        </span>
        <b>{labelOf(grade)}</b>
      </div>
      <div className="text-[0.9rem] text-[#646464]">{sub}</div>
      {note ? <div className="text-[0.9rem] text-[#646464]">{note}</div> : null}
    </div>
  );
}
export function Kpi({ label, value, sub, className = '' }: { label: ReactNode; value: ReactNode; sub?: ReactNode; className?: string }) {
  return (
    <div className={`rounded-xl border border-[#ECECEC] bg-white px-5 py-4 shadow-sm ${className}`}>
      <div className="text-[0.72rem] font-bold uppercase tracking-[0.12em] text-[#646464]">{label}</div>
      <div className="mt-1 text-xl font-bold text-[#002B49]">{value}</div>
      {sub ? <div className="text-[0.82rem] text-[#646464]">{sub}</div> : null}
    </div>
  );
}

/* ---------------------------------------------------------------- evidence codes */

const CODE_RE = /\[((?:IO|SA|[A-Z])\d{2,3})\]/;

export function CodeButton({ code }: { code: string }) {
  const openEv = useReportUi((s) => s.openEv);
  return (
    <button type="button" onClick={() => openEv(code)} aria-label={`Open source ${code}`} className="mx-px cursor-pointer rounded border border-[#ECECEC] bg-[#EFF3F8] px-1.5 text-[0.72rem] font-bold text-[#002B49] hover:border-[#0085CA] focus-visible:outline focus-visible:outline-2 focus-visible:outline-[#0085CA]">
      {code}
    </button>
  );
}
/** text with its bracketed evidence codes turned into buttons that open the source */
export function Codes({ text }: { text: string | null | undefined }) {
  const parts = typo(text).split(new RegExp(CODE_RE.source, 'g'));
  return (
    <>
      {parts.map((p, i) => (i % 2 ? <CodeButton key={i} code={p} /> : p))}
    </>
  );
}
/** text plus chips for any cited codes the text does not mention */
export function EvText({ text, ev }: { text: string | null | undefined; ev?: string[] | null }) {
  const x = String(text || '');
  const extra = (ev || []).filter((c) => !x.includes(c));
  return (
    <>
      <Codes text={x} />
      {extra.length ? (
        <>
          {' '}
          {extra.map((c) => (
            <CodeButton key={c} code={c} />
          ))}
        </>
      ) : null}
    </>
  );
}
/** a button that opens the indicator definition dialog */
export function IndButton({ id }: { id: string }) {
  const openInd = useReportUi((s) => s.openInd);
  return (
    <button type="button" onClick={() => openInd(id)} className="cursor-pointer border-0 bg-transparent p-0 font-bold text-[#002B49] underline decoration-dotted underline-offset-2 hover:text-[#0085CA] focus-visible:outline focus-visible:outline-2 focus-visible:outline-[#0085CA]">
      {id}
    </button>
  );
}

/** the prominent draft notice at the foot of the report */
export function DraftNote({ text }: { text: string }) {
  return <div className="mt-6 border-t border-[#ECECEC] pt-3 text-[0.78rem] italic text-[#646464]">{text}</div>;
}

/* ---------------------------------------------------------------- shared report fragments */

const STATUS_COLOR: Record<string, string> = { completed: '#00677F', behind: '#A6192E', not_started: '#A6192E', on_track: '#0085CA' };
export function StatusText({ status }: { status: string }) {
  return (
    <span className="font-bold capitalize" style={{ color: STATUS_COLOR[status] || '#002B49' }}>
      {status.replace(/_/g, ' ')}
    </span>
  );
}

export function KV({ k, children }: { k: string; children: ReactNode }) {
  return (
    <tr>
      <th className={`${th} w-40 align-top`} scope="row">
        {k}
      </th>
      <td className={td}>{children}</td>
    </tr>
  );
}


export function PriorActionsTable() {
  const { priorActions } = useReport();
  return (
    <DTable caption="Status of prior actions">
      <thead>
        <tr>
          <th className={th}>Prior action</th>
          <th className={th}>Status</th>
          <th className={th}>Evidence</th>
        </tr>
      </thead>
      <tbody>
        {priorActions.map((a, k) => (
          <tr key={a.id ?? k}>
            <td className={td}>
              <b>{typo(a.heading)}</b>
            </td>
            <td className={td}>
              <StatusText status={a.status} />
            </td>
            <td className={td}>
              <Codes text={a.note} />
              <div className="text-[0.9rem] text-[#646464]">{typo(a.metrics)}</div>
            </td>
          </tr>
        ))}
      </tbody>
    </DTable>
  );
}


export function BackOnTrackItem({ b }: { b: NonNullable<View['io']>['back'][number] }) {
  return (
    <details className="mb-2 rounded-lg border border-[#ECECEC] bg-white open:shadow-sm">
      <summary className="cursor-pointer px-4 py-2 font-bold text-[#002B49]">{typo(b.heading)}</summary>
      <div className="px-4 pb-3">
        <DTable caption={`Getting back on track: ${b.heading}`}>
          <tbody>
            <KV k="What happened">{typo(b.what)}</KV>
            <KV k="Impact">{typo(b.impact)}</KV>
            <KV k="Root cause">{typo(b.cause)}</KV>
            <KV k="Mechanism to prevent">{typo(b.prevent)}</KV>
            <KV k="Measures">{typo((b.measures || []).join('; '))}</KV>
          </tbody>
        </DTable>
      </div>
    </details>
  );
}

