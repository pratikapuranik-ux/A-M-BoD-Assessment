import { Fragment } from 'react';
import * as Tabs from '@radix-ui/react-tabs';
import * as Tooltip from '@radix-ui/react-tooltip';
import { motion } from 'framer-motion';
import type { View } from '../api/viewTypes';
import { useReportUi, type ReportTab, type Stage } from '../store/reportUi';
import { ActionPlan, Dashboard, DimensionDetail, MethodAppendix, PeersAppendix, SourcesAppendix } from './AppendixViews';
import { IndicatorHeatmap } from './charts';
import { DIMS, DIMN, DRAFT, RUN_CIRC, ReportProvider, firstSentence, typo, useReport } from './context';
import { ReportDialogs } from './dialogs';
import { Arrow, BackOnTrackItem, CodeButton, Codes, DTable, DeltaCell, Eb, EvText, GradeCell, GradeChip, GradeTile, H2, IndButton, KV, Muted, PriorActionsTable, ScoreCell, ScoreChip, Section, btnCls, td, th } from './parts';

/* The board report: cover, executive summary, scorecard, evidence, peers and actions (js/report.js tReport),
   with the appendices and the dashboard as further tabs. */

export type ReportMode = 'outside_in' | 'inside_out' | 'combined';

/* ------------------------------------------------------------------ sections */

function Cover() {
  const { view, io, cofull, tk, peerFull, evWindow } = useReport();
  const m = view.meta;
  const date = io ? (view.io?.date || m.date) : m.date;
  return (
    <>
      <div className="mb-6 border border-l-[6px] border-[#ECECEC] border-l-[#002B49] bg-white px-6 py-10 sm:px-11 print:break-inside-avoid">
        <div className="mb-10 text-[0.72rem] font-bold uppercase tracking-[0.16em] text-[#0085CA]">Alvarez &amp; Marsal</div>
        <h1 className="mb-4 text-4xl font-bold leading-tight text-[#002B49]">
          Day 1 / Day 2
          <br />
          Board Assessment
        </h1>
        <div className="mb-1 text-[1.08rem]">
          {typo(cofull)} ({tk}) &nbsp;·&nbsp; {m.period}
        </div>
        <div className="max-w-[640px] text-[0.95rem] text-[#646464]">
          {io ? 'Inside-out update on top of an outside-in assessment from public information, benchmarked against ' : 'Outside-in assessment from public information, benchmarked against '}
          {typo(peerFull.join(', ').replace(/\.$/, ''))}.
        </div>
        <div className="my-8 h-0.5 w-[90px] bg-[#0085CA]" />
        <div className="text-[0.92rem] font-bold text-[#002B49]">{date}</div>
      </div>
      <DTable className="mb-6" caption="About this report">
        <tbody>
          <KV k="Purpose">Grade the board of {typo(cofull)} A–F on six Day 1 / Day 2 dimensions and 22 indicators, attributing what the company did under the board’s watch to the board, against a named peer set.</KV>
          <KV k="Basis">
            {io ? 'Public information plus board documents and a director self-assessment. ' : 'Public information only. '}
            {typo(view.modes?.[m.mode] ?? '')}.
          </KV>
          <KV k="Circulation">{RUN_CIRC[m.mode] ?? ''}.</KV>
          <KV k="Evidence window">{evWindow}</KV>
        </tbody>
      </DTable>
    </>
  );
}

function ExecutiveSummary() {
  const { view, io, co, model, O, last, headline, actions } = useReport();
  const gr = (o: { grade: string | null; label: string }) => (o.grade ? `${o.grade} (${o.label})` : 'no overall grade');
  const ioO = model.io.overall;
  return (
    <Section id="exec-summary">
      <Eb>Executive summary</Eb>
      <H2>{typo(headline)}</H2>
      <div className="mb-4 flex flex-wrap gap-4">
        <GradeTile
          label="Outside-in"
          grade={O.overall.grade}
          sub={`${O.overall.n} of 6 dimensions reported`}
          note={last ? (
            <>
              <Arrow now={O.overall.grade} prev={last.overall.grade} /> ({last.period})
            </>
          ) : undefined}
        />
        {io ? <GradeTile label="After inside-out" grade={ioO.grade} sub={`${ioO.n} of 6 dimensions reported`} note={<><Arrow now={ioO.grade} prev={O.overall.grade} /> vs outside-in</>} /> : null}
      </div>
      <p className="mb-3 text-[1.05rem]">
        {io ? (
          <>
            {typo(co)}’s board {ioO.grade ? 'grades ' + gr(ioO) : 'has no overall grade'} once board documents and a director self-assessment are added, against {gr(O.overall)} from public information alone.
            {!ioO.grade || !O.overall.grade ? ' An overall grade needs at least three dimensions with enough evidence to be reported.' : ''}
          </>
        ) : (
          typo(view.overall_line)
        )}
      </p>
      <Eb>What drives the rating</Eb>
      <p className="mb-3">{typo(io ? view.io?.drives : view.drives)}</p>
      {io && view.io ? (
        <>
          <Eb>Inside view against the public record</Eb>
          <div className="grid gap-6 md:grid-cols-2">
            <div>
              <b>Better than the public record</b>
              <ul className="ml-5 list-disc">
                {(view.io.better || []).map((x, k) => (
                  <li key={k}>
                    <Codes text={x} />
                  </li>
                ))}
              </ul>
            </div>
            <div>
              <b>Worse than the public record</b>
              <ul className="ml-5 list-disc">
                {(view.io.worse || []).map((x, k) => (
                  <li key={k}>
                    <Codes text={x} />
                  </li>
                ))}
              </ul>
            </div>
          </div>
        </>
      ) : null}
      <Eb>Key actions</Eb>
      {actions.map((a, k) => (
        <p key={k} className="mb-2">
          <span className="text-[#0085CA]">▸</span> <b>{typo(a.heading)}.</b> <Codes text={a.description} />
        </p>
      ))}
      <Eb>Metrics worth tracking</Eb>
      <DTable caption="Metrics worth tracking">
        <thead>
          <tr>
            <th className={th}>Metric</th>
            <th className={th}>Why it matters</th>
            <th className={th}>Now</th>
          </tr>
        </thead>
        <tbody>
          {(view.metrics || []).map((r, k) => (
            <tr key={k}>
              <td className={td}>
                <b>{typo(r[0])}</b>
              </td>
              <td className={td}>{typo(r[1])}</td>
              <td className={td}>{typo(r[2])}</td>
            </tr>
          ))}
        </tbody>
      </DTable>
      <Eb>Position relative to peers</Eb>
      <p className="mb-3">{typo(view.position)}</p>
      {(view.position_lines || []).map((x, k) => (
        <p key={k} className="mb-1 pl-3">
          {typo(x)}
        </p>
      ))}
      {io ? <Muted>Peers are compared on outside-in grades only; they are never re-scored with inside-out information.</Muted> : null}
    </Section>
  );
}

function AtAGlance() {
  const { now } = useReport();
  return (
    <Section id="at-a-glance">
      <Eb>At a glance</Eb>
      <H2>Twenty-two indicators</H2>
      <Muted>Select a square for the rationale and evidence.</Muted>
      <IndicatorHeatmap scores={now} />
    </Section>
  );
}

function Scorecard() {
  const { view, io, ids, dimOf, model, O, L, history, last, now, ioCell, indName, indLine, dimLabel } = useReport();
  const openDims = useReportUi((s) => s.openDims);
  const toggleDim = useReportUi((s) => s.toggleDim);
  return (
    <Section id="scorecard">
      <Eb>Scorecard and trend</Eb>
      <H2>Grades by dimension</H2>
      <Muted>Select a dimension to see its indicators.</Muted>
      <DTable caption="Grades by dimension, with the indicators of each dimension on expansion">
        <thead>
          <tr>
            <th className={th}>Dimension</th>
            {history.map((x) => (
              <th key={x.period} className={th}>
                {x.period}
              </th>
            ))}
            <th className={th}>{io ? 'Outside-in' : view.meta.period}</th>
            {io ? <th className={th}>After inside-out</th> : null}
            {last ? <th className={th}>Change</th> : null}
            <th className={th}>Evidence in this run</th>
          </tr>
        </thead>
        <tbody>
          {DIMS.map((d, k) => {
            const open = openDims.includes(d);
            return (
              <Fragment key={d}>
                <tr className={open ? 'bg-[#F7F9FB]' : ''}>
                  <td className={td}>
                    <button type="button" aria-expanded={open} aria-controls={`dim-rows-${d}`} onClick={() => toggleDim(d)} className="cursor-pointer border-0 bg-transparent p-0 text-left font-bold text-[#002B49] focus-visible:outline focus-visible:outline-2 focus-visible:outline-[#0085CA]">
                      <span className={`mr-1.5 inline-block text-[#0085CA] transition-transform ${open ? 'rotate-90' : ''}`} aria-hidden="true">
                        ▸
                      </span>
                      {d}. {typo(dimLabel(d) || DIMN[d])}
                    </button>
                  </td>
                  {history.map((x) => (
                    <GradeCell key={x.period} grade={x.dims[d]?.grade} />
                  ))}
                  <GradeCell grade={O.dims[d].grade} />
                  {io ? <GradeCell grade={model.io.dims[d].grade} /> : null}
                  {last ? (
                    <td className={td}>
                      <Arrow now={L.dims[d].grade} prev={last.dims[d]?.grade} />
                    </td>
                  ) : null}
                  <td className={td}>
                    <Codes text={view.scorecard?.[k]?.line} />
                  </td>
                </tr>
                {ids
                  .filter((i) => dimOf[i] === d)
                  .map((i) => {
                    const c = io ? ioCell(i) : null;
                    return (
                      <tr key={i} id={`dim-rows-${d}`} className={open ? '' : 'hidden print:table-row'}>
                        <td className={`${td} pl-8`}>
                          <IndButton id={i} /> {typo(indName(i))}
                        </td>
                        {history.map((x) => (
                          <ScoreCell key={x.period} score={x.ind[i]} />
                        ))}
                        <ScoreCell score={model.oiSc[i]} />
                        {io ? <ScoreCell score={model.ioSc[i]} /> : null}
                        {last ? <DeltaCell a={last.ind[i]} b={now[i]} /> : null}
                        <td className={td}>{c && !c.carried ? <EvText text={firstSentence(c.rat)} ev={c.ev} /> : <EvText text={indLine(i)} ev={view.ind[i].ev} />}</td>
                      </tr>
                    );
                  })}
              </Fragment>
            );
          })}
          <tr className="font-bold">
            <td className={`${td} bg-[#EFF3F8]`}>Overall</td>
            {history.map((x) => (
              <GradeCell key={x.period} grade={x.overall.grade} />
            ))}
            <GradeCell grade={O.overall.grade} />
            {io ? <GradeCell grade={model.io.overall.grade} /> : null}
            {last ? (
              <td className={td}>
                <Arrow now={L.overall.grade} prev={last.overall.grade} />
              </td>
            ) : null}
            <td className={td}>
              <i>Rounded average of dimension letters (midpoints round down).</i>
            </td>
          </tr>
        </tbody>
      </DTable>
      {io ? null : (
        <Muted>
          <i>{typo(view.coverage_note)}</i>
        </Muted>
      )}
    </Section>
  );
}

function WhatChanged() {
  const { view, io, ids, last, now, ioCell, indName } = useReport();
  if (!last) return null;
  const ch = ids.filter((i) => last.ind[i] != null && now[i] != null && last.ind[i] !== now[i]);
  return (
    <Section id="what-changed">
      <Eb>What changed since {last.period}</Eb>
      <H2>Indicators that moved</H2>
      {ch.length ? (
        <DTable caption="Indicators that moved">
          <thead>
            <tr>
              <th className={th}>Indicator</th>
              <th className={th}>Prior</th>
              <th className={th}>Now</th>
              <th className={th}>Δ</th>
              <th className={th}>Evidence that moved the score</th>
            </tr>
          </thead>
          <tbody>
            {ch.map((i) => {
              const c = io ? ioCell(i) : null;
              return (
                <tr key={i}>
                  <td className={td}>
                    <b>
                      {i} {typo(indName(i))}
                    </b>
                  </td>
                  <ScoreCell score={last.ind[i]} />
                  <ScoreCell score={now[i]} />
                  <DeltaCell a={last.ind[i]} b={now[i]} />
                  <td className={td}>{c && !c.carried ? <EvText text={c.rat} ev={c.ev} /> : <EvText text={view.ind[i].rationale} ev={view.ind[i].ev} />}</td>
                </tr>
              );
            })}
          </tbody>
        </DTable>
      ) : (
        <Muted>No indicator score changed.</Muted>
      )}
    </Section>
  );
}

function EvidenceBehind() {
  const { view, io, ids, dimOf, O, model, ioCell, indName, indLine, dimLabel } = useReport();
  return (
    <Section id="evidence-behind">
      <Eb>Evidence behind each indicator</Eb>
      <H2>One line per indicator; the detailed view is in Dimension detail</H2>
      <DTable caption="Evidence behind each indicator">
        <thead>
          <tr>
            <th className={th}>Indicator</th>
            <th className={th}>Score{io ? ' (OI → IO)' : ''}</th>
            <th className={th}>Summary of the evidence</th>
          </tr>
        </thead>
        <tbody>
          {DIMS.map((d) => (
            <Fragment key={d}>
              <tr>
                <td colSpan={3} className={`${td} bg-[#EFF3F8]`}>
                  <b>
                    {d}. {typo(dimLabel(d))}
                  </b>{' '}
                  &nbsp;Outside-in <GradeChip grade={O.dims[d].grade} />
                  {io ? (
                    <>
                      {' '}
                      &nbsp;After inside-out <GradeChip grade={model.io.dims[d].grade} />
                    </>
                  ) : null}
                </td>
              </tr>
              {ids
                .filter((i) => dimOf[i] === d)
                .map((i) => {
                  const c = io ? ioCell(i) : null;
                  return (
                    <tr key={i}>
                      <td className={td}>
                        <IndButton id={i} /> {typo(indName(i))}
                      </td>
                      {c ? (
                        <td className={`${td} whitespace-nowrap`}>
                          <ScoreChip score={view.ind[i].score} />
                          {c.score !== view.ind[i].score ? ' → ' : ' = '}
                          <ScoreChip score={c.score} />
                        </td>
                      ) : (
                        <ScoreCell score={view.ind[i].score} />
                      )}
                      <td className={td}>
                        <EvText text={indLine(i)} ev={view.ind[i].ev} />
                      </td>
                    </tr>
                  );
                })}
            </Fragment>
          ))}
        </tbody>
      </DTable>
    </Section>
  );
}

function PeerComparison() {
  const { view, io, co, peers, model, O } = useReport();
  const prow = (k: number): string => {
    const r = (view.peer_table || [])[k] || [];
    return r.length ? String(r[r.length - 1] ?? '') : '';
  };
  return (
    <Section id="peer-comparison">
      <Eb>Peer comparison</Eb>
      <H2>Dimension grades against the peer set</H2>
      <DTable caption="Dimension grades against the peer set">
        <thead>
          <tr>
            <th className={th}>Dimension</th>
            <th className={th}>
              {typo(co)}
              {io ? ' (outside-in)' : ''}
            </th>
            {peers.map((p) => (
              <th key={p} className={th}>
                {typo(p)}
              </th>
            ))}
            <th className={th}>How the company compares</th>
          </tr>
        </thead>
        <tbody>
          {DIMS.map((d, k) => (
            <tr key={d}>
              <td className={td}>
                <b>
                  {d}. {typo(DIMN[d])}
                </b>
              </td>
              <GradeCell grade={O.dims[d].grade} />
              {model.peers.map((p) => (
                <GradeCell key={p.name} grade={p.c.dims[d].grade} />
              ))}
              <td className={td}>
                <Codes text={prow(k + 1)} />
              </td>
            </tr>
          ))}
          <tr className="font-bold">
            <td className={`${td} bg-[#EFF3F8]`}>Overall</td>
            <GradeCell grade={O.overall.grade} />
            {model.peers.map((p) => (
              <GradeCell key={p.name} grade={p.c.overall.grade} />
            ))}
            <td className={td}>
              <Codes text={prow(DIMS.length + 1)} />
            </td>
          </tr>
        </tbody>
      </DTable>
    </Section>
  );
}

/** Reason text; an evidence code becomes a button only when that evidence exists */
function ReasonText({ text }: { text: string }) {
  const { evOf } = useReport();
  const parts = typo(text).split(/\[((?:IO|SA|[A-Z])\d{2,3})\]/g);
  return (
    <>
      {parts.map((p, i) => (i % 2 ? (evOf(p) ? <CodeButton key={i} code={p} /> : `[${p}]`) : p))}
    </>
  );
}

function Reconciliation() {
  const { view } = useReport();
  const r = view.reconciliation;
  if (!r) return null;
  const sc = (n: number | null) => (n == null ? 'n/a' : String(n));
  const run = (k: 'A' | 'B') => `Run ${k} (${r.models[k].model}, ${r.models[k].effort} effort)`;
  return (
    <Section id="reconciliation">
      <Eb>Reconciliation</Eb>
      <H2>Where the two scoring runs differed</H2>
      {r.rows.length ? (
        <>
          <Muted>
            {run('A')} and {run('B')} agreed on {r.agreed} of {r.total} indicator scores; {r.rows.length} were reconciled and the model’s recommendation is the final score.
          </Muted>
          <DTable caption="Indicator scores the two runs disagreed on, with the final score and the reason">
            <thead>
              <tr>
                <th scope="col" className={th}>Cell</th>
                <th scope="col" className={th}>Score (Run A / Run B)</th>
                <th scope="col" className={th}>Final score</th>
                <th scope="col" className={th}>Reason</th>
              </tr>
            </thead>
            <tbody>
              {r.rows.map((x, k) => (
                <tr key={k}>
                  <td className={td}>
                    <b>{typo(x.subject)}</b>
                    <br />
                    {x.indicator} {typo(x.name)}
                  </td>
                  <td className={`${td} whitespace-nowrap`}>
                    <span className={x.chosen === 'A' ? 'font-bold' : ''}>{sc(x.a)}</span> / <span className={x.chosen === 'B' ? 'font-bold' : ''}>{sc(x.b)}</span>
                  </td>
                  <ScoreCell score={x.final} />
                  <td className={td}>
                    <ReasonText text={x.reason} />
                  </td>
                </tr>
              ))}
            </tbody>
          </DTable>
        </>
      ) : (
        <Muted>Both runs agreed on every indicator score; nothing needed reconciling.</Muted>
      )}
    </Section>
  );
}

function ActionsSection() {
  const { view, io, actions, priorActions } = useReport();
  const behind = priorActions.filter((a) => a.status === 'behind' || a.status === 'not_started');
  return (
    <Section id="actions">
      <Eb>Actions</Eb>
      <H2>What the board could do next</H2>
      {actions.map((a) => (
        <div key={a.n} className="my-4 border-l-2 border-[#ECECEC] pl-4">
          <h4 className="mb-1 text-[1.02rem] font-bold text-[#002B49]">
            <span className="mr-2 text-[#0085CA]">{a.n}</span>
            {typo(a.heading)}
          </h4>
          <p className="mb-2">
            <Codes text={a.description} />
          </p>
          <Muted>
            Measures: {typo((a.measures || []).join('; ') || '–')} &nbsp; Target: {typo(a.target || '–')}
          </Muted>
        </div>
      ))}
      {io && priorActions.length ? (
        <>
          <Eb>Status of prior actions</Eb>
          <PriorActionsTable />
          {behind.length && view.io?.back
            ? (
                <>
                  <Eb>Getting back on track</Eb>
                  {view.io.back
                    .filter((b) => behind.some((a) => a.id === b.id))
                    .map((b, k) => (
                      <BackOnTrackItem key={b.id ?? k} b={b} />
                    ))}
                </>
              )
            : null}
        </>
      ) : !io ? (
        <Muted>Status of prior actions is not forced from public information; it is asked for in the inside-out stage.</Muted>
      ) : null}
    </Section>
  );
}

function Additional() {
  const { view, io } = useReport();
  if (io) return null;
  return (
    <Section id="additional-info">
      <Eb>Additional information that would sharpen the assessment</Eb>
      <H2>Only where it would change a grade or an action</H2>
      {(view.addl || []).map((x, k) => (
        <p key={k} className="mb-1 pl-3">
          {typo(x)}
        </p>
      ))}
    </Section>
  );
}

/** the Report tab: the full board report, or (executive lens) the executive summary and scorecard only */
function ReportTabBody() {
  const lens = useReportUi((s) => s.lens);
  if (lens === 'exec')
    return (
      <>
        <ExecutiveSummary />
        <Scorecard />
      </>
    );
  return (
    <>
      <Cover />
      <ExecutiveSummary />
      <AtAGlance />
      <Scorecard />
      <WhatChanged />
      <EvidenceBehind />
      <PeerComparison />
      <Reconciliation />
      <ActionsSection />
      <Additional />
    </>
  );
}

/* ------------------------------------------------------------------ shell */

const TABS: [ReportTab, string][] = [
  ['dashboard', 'Dashboard'],
  ['report', 'Report'],
  ['detail', 'Dimension detail'],
  ['peers', 'Peers'],
  ['sources', 'Sources'],
  ['method', 'Method'],
  ['plan', 'Action plan'],
];

function Toggle<T extends string>({ value, onChange, options, label }: { value: T; onChange: (v: T) => void; options: [T, string][]; label: string }) {
  return (
    <div role="radiogroup" aria-label={label} className="inline-flex rounded-[10px] border border-[#ECECEC] bg-[#EFF3F8] p-1">
      {options.map(([k, l]) => (
        <button
          key={k}
          type="button"
          role="radio"
          aria-checked={value === k}
          onClick={() => onChange(k)}
          className={`rounded-md px-3 py-1.5 text-sm font-bold focus-visible:outline focus-visible:outline-2 focus-visible:outline-[#0085CA] ${value === k ? 'bg-white text-[#002B49] shadow-sm' : 'text-[#646464]'}`}
        >
          {l}
        </button>
      ))}
    </div>
  );
}

function Shell({ mode }: { mode: ReportMode }) {
  const { view, io, stage, fileUrl } = useReport();
  const tab = useReportUi((s) => s.tab);
  const setTab = useReportUi((s) => s.setTab);
  const lens = useReportUi((s) => s.lens);
  const setLens = useReportUi((s) => s.setLens);
  const setStage = useReportUi((s) => s.setStage);
  const html = fileUrl(io ? 'io_html' : 'oi_html');
  const docx = fileUrl(io ? 'io_docx' : 'oi_docx');
  return (
    <div className="text-[15px] leading-relaxed text-[#002B49]">
      <div className="mb-4 flex flex-wrap items-center justify-between gap-3 print:hidden">
        <div className="flex flex-wrap items-center gap-3">
          {mode === 'combined' && view.io ? (
            <Toggle<Stage> label="Reading stage" value={stage} onChange={setStage} options={[['oi', 'Outside-in'], ['io', 'After inside-out']]} />
          ) : null}
          <Toggle label="Report lens" value={lens} onChange={setLens} options={[['board', 'Board report'], ['exec', 'Executive view']]} />
        </div>
        <div className="flex flex-wrap items-center gap-2">
          {html ? (
            <a className={btnCls} href={html} download>
              Download
            </a>
          ) : null}
          {docx ? (
            <a className={btnCls} href={docx} download>
              Report (Word)
            </a>
          ) : null}
          <button type="button" className={btnCls} onClick={() => window.print()}>
            Print
          </button>
        </div>
      </div>
      <Tabs.Root value={tab} onValueChange={(v) => setTab(v as ReportTab)}>
        <Tabs.List aria-label="Report sections" className="mb-5 flex gap-1 overflow-x-auto border-b border-[#ECECEC] print:hidden">
          {TABS.map(([k, l]) => (
            <Tabs.Trigger
              key={k}
              value={k}
              className="whitespace-nowrap border-b-2 border-transparent px-4 py-3 text-[0.95rem] font-bold text-[#646464] outline-none focus-visible:ring-2 focus-visible:ring-[#0085CA] data-[state=active]:border-[#002B49] data-[state=active]:text-[#002B49]"
            >
              {l}
            </Tabs.Trigger>
          ))}
        </Tabs.List>
        {TABS.map(([k]) => (
          <Tabs.Content key={k} value={k} className="outline-none">
            <motion.div initial={{ opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.2 }}>
              {k === 'dashboard' ? <Dashboard /> : null}
              {k === 'report' ? <ReportTabBody /> : null}
              {k === 'detail' ? <DimensionDetail /> : null}
              {k === 'peers' ? <PeersAppendix /> : null}
              {k === 'sources' ? <SourcesAppendix /> : null}
              {k === 'method' ? <MethodAppendix /> : null}
              {k === 'plan' ? <ActionPlan /> : null}
            </motion.div>
          </Tabs.Content>
        ))}
      </Tabs.Root>
      <div className="mt-6 border-t border-[#ECECEC] pt-3 text-[0.78rem] italic text-[#646464]">{DRAFT}</div>
      <ReportDialogs />
    </div>
  );
}

export default function ReportView({ view, mode = 'combined' }: { view: View; mode?: ReportMode }): JSX.Element {
  const storeStage = useReportUi((s) => s.stage);
  const requested: Stage = mode === 'outside_in' ? 'oi' : mode === 'inside_out' ? 'io' : storeStage;
  return (
    <Tooltip.Provider>
      <ReportProvider view={view} stage={requested}>
        <Shell mode={mode} />
      </ReportProvider>
    </Tooltip.Provider>
  );
}
