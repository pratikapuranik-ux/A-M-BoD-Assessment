import { Fragment, useMemo, type ReactNode } from 'react';
import * as Accordion from '@radix-ui/react-accordion';
import * as Tabs from '@radix-ui/react-tabs';
import { motion } from 'framer-motion';
import { useReportUi, type DashTab } from '../store/reportUi';
import { PeerBars, PeerDotPlot, TrendLines, type Series, type TrendPoint } from './charts';
import { DIMS, DIMN, NAVY, PEER_COLORS, PEER_RELATIVE, firstSentence, gradeColor, listJoin, typo, useReport } from './context';
import { Arrow, Codes, DTable, DeltaCell, Eb, EvText, GradeCell, GradeChip, H2, H3, IndButton, Kpi, Muted, Notice, ScoreCell, Section, StatusText, btnCls, td, th } from './parts';

/* Appendices 1, 2, 3, 4, 5 and 6, the board dashboard and the action plan (js/report.js, js/dashboard.js). */

/* ------------------------------------------------------------------ Appendix 1: dimension detail */

export function DimensionDetail() {
  const { view, io, ids, dimOf, O, model, ioCell, dimLabel } = useReport();
  return (
    <>
      <Notice>Each indicator is scored once, for the board, against written anchors. Evidence codes open the source.</Notice>
      {DIMS.map((d) => {
        const t = view.dimtext?.[d];
        return (
          <Section key={d} id={`detail-${d}`}>
            <Eb>Appendix 1 · Detailed indicator view</Eb>
            <H2>
              {d}. {typo(dimLabel(d))} &nbsp;·&nbsp; Outside-in <GradeChip grade={O.dims[d].grade} />
              {io ? (
                <>
                  {' '}
                  &nbsp;→&nbsp; after inside-out <GradeChip grade={model.io.dims[d].grade} />
                </>
              ) : null}
            </H2>
            <p className="mb-3">
              <Codes text={t?.text} />
            </p>
            <Muted>
              <b>Where this grade is limited:</b> <Codes text={(t?.limit || '').replace(/^Where this grade is limited:\s*/, '')} />
            </Muted>
            <DTable caption={`Indicators of dimension ${d}, ${dimLabel(d)}`}>
              <thead>
                <tr>
                  <th className={th}>Indicator</th>
                  <th className={th}>Outside-in</th>
                  {io ? <th className={th}>Post inside-out</th> : null}
                  <th className={th}>Rationale and sources</th>
                  <th className={th}>Conf.</th>
                </tr>
              </thead>
              <tbody>
                {ids
                  .filter((i) => dimOf[i] === d)
                  .map((i) => {
                    const o = view.ind[i];
                    const c = io ? ioCell(i) : null;
                    return (
                      <tr key={i}>
                        <td className={td}>
                          <b>
                            <IndButton id={i} /> {typo(o.name)}
                          </b>
                        </td>
                        <ScoreCell score={o.score} />
                        {c ? <ScoreCell score={c.score} /> : null}
                        <td className={td}>
                          <Codes text={o.rationale} />
                          {c ? (
                            <div className="mt-2 rounded-md bg-[#EFF3F8] px-2.5 py-2 text-[0.86rem]">
                              <b>Inside-out:</b> <Codes text={c.rat} />
                            </div>
                          ) : null}
                        </td>
                        <td className={td}>{(c ? c.conf : o.conf) ?? ''}</td>
                      </tr>
                    );
                  })}
              </tbody>
            </DTable>
          </Section>
        );
      })}
    </>
  );
}

/* ------------------------------------------------------------------ Appendix 2: peers */

export function PeersAppendix() {
  const { view, io, model, ids, indName } = useReport();
  return (
    <>
      <Notice>
        Peers are graded outside-in from public information with the same rubric and depth as the company.
        {io ? ' They are not re-scored with inside-out information.' : ''}
      </Notice>
      {model.peers.map((p, pi) => {
        const pd = view.peers[pi];
        return (
          <Section key={p.name + pi} id={`peer-${pi}`}>
            <Eb>
              Appendix 2 · {pi + 1} of {model.peers.length}
            </Eb>
            <H2>{typo(p.full)}: outside-in indicator view</H2>
            <DTable className="text-center" caption={`${p.full} grades by dimension`}>
              <tbody>
                <tr>
                  {DIMS.map((d) => (
                    <GradeCell key={d} grade={p.c.dims[d].grade} />
                  ))}
                  <GradeCell grade={p.c.overall.grade} />
                </tr>
                <tr>
                  {DIMS.map((d) => (
                    <td key={d} className="px-1 py-1 text-[0.76rem] text-[#646464]">
                      {d}. {typo(DIMN[d])}
                    </td>
                  ))}
                  <td className="px-1 py-1 text-[0.76rem] text-[#646464]">Overall</td>
                </tr>
              </tbody>
            </DTable>
            <p className="mb-3"><Codes text={pd?.summary} /></p>
            <DTable caption={`${p.full} indicator scores`}>
              <thead>
                <tr>
                  <th className={th}>Indicator</th>
                  <th className={th}>Score</th>
                  <th className={th}>Rationale and sources</th>
                </tr>
              </thead>
              <tbody>
                {ids.map((i) => (
                  <tr key={i}>
                    <td className={td}>
                      <b>
                        {i} {typo(indName(i))}
                      </b>
                    </td>
                    <ScoreCell score={pd?.ind?.[i]?.score} />
                    <td className={td}>
                      <Codes text={pd?.ind?.[i]?.rationale} />
                    </td>
                  </tr>
                ))}
              </tbody>
            </DTable>
          </Section>
        );
      })}
    </>
  );
}

/* ------------------------------------------------------------------ Appendix 5: sources */

export function SourcesAppendix() {
  const { view, io, prefixes } = useReport();
  const f = useReportUi((s) => s.srcFilter);
  const setF = useReportUi((s) => s.setSrcFilter);
  const q = useReportUi((s) => s.srcQuery);
  const setQ = useReportUi((s) => s.setSrcQuery);
  const filters: [string, string][] = [['all', 'All'], ...Object.keys(prefixes).map((k): [string, string] => [k, prefixes[k]]), ...(io ? ([['io', 'Inside-out and self-assessment']] as [string, string][]) : [])];
  const all = useMemo(() => ({ ...(view.ev || {}), ...(view.io?.ev || {}) }), [view]);
  const isIO = (k: string) => k.indexOf('IO') === 0 || k.indexOf('SA') === 0;
  const pre = Object.keys(prefixes);
  const order = (k: string) => (isIO(k) ? (k[0] === 'I' ? 90 : 91) : pre.indexOf(k[0])) * 1000 + parseInt(k.replace(/\D/g, ''), 10);
  const needle = q.trim().toLowerCase();
  const keys = Object.keys(all)
    .filter((k) => f === 'all' || (f === 'io' && isIO(k)) || (!isIO(k) && k[0] === f))
    .filter((k) => !needle || `${k} ${all[k].doc} ${k.startsWith('SA') ? '' : all[k].excerpt || ''} ${all[k].used || ''}`.toLowerCase().includes(needle))
    .sort((a, b) => order(a) - order(b));
  return (
    <Section id="sources">
      <Eb>Appendix 5</Eb>
      <H2 className="!mt-1">Sources consulted</H2>
      <Muted>Each entry is referenced from the tables by its code. Verbatim excerpts are kept under 15 words.</Muted>
      <div className="my-3 flex flex-wrap items-center gap-2 print:hidden">
        {filters.map(([k, l]) => (
          <button
            key={k}
            type="button"
            aria-pressed={f === k}
            onClick={() => setF(k)}
            className={`rounded-full border px-4 py-1.5 text-[0.84rem] focus-visible:outline focus-visible:outline-2 focus-visible:outline-[#0085CA] ${f === k ? 'border-[#002B49] bg-[#002B49] text-white' : 'border-[#D9D9D9] bg-white text-[#002B49]'}`}
          >
            {typo(l)}
          </button>
        ))}
        <input
          type="search"
          value={q}
          onChange={(e) => setQ(e.target.value)}
          placeholder="Search sources"
          aria-label="Search sources"
          className="max-w-[260px] flex-1 rounded-lg border border-[#D9D9D9] px-3 py-1.5 text-sm focus-visible:outline focus-visible:outline-2 focus-visible:outline-[#0085CA]"
        />
      </div>
      <div aria-live="polite">
        <Muted>
          {keys.length} of {Object.keys(all).length} sources shown.
        </Muted>
        {keys.map((k) => {
          const e = all[k];
          return (
            <div key={k} id={`src_${k}`} className="border-b border-[#ECECEC] py-3 text-[0.9rem] print:break-inside-avoid">
              <div>
                <b>{k}</b> &nbsp; {typo(e.doc)}
              </div>
              <div className="text-[#646464]">
                {e.date}
                {e.recent ? (
                  <>
                    {' · '}
                    <b className="text-[#002B49]">RECENT</b>
                  </>
                ) : null}
              </div>
              {k.startsWith('SA') ? <div className="text-[#646464]">Director responses are synthesised, not quoted.</div> : <div>“{typo(e.excerpt || '')}”</div>}
              {e.question ? <div className="text-[#646464]">Question: {typo(e.question)}</div> : null}
              {e.url ? <div className="break-all text-[#646464]">{e.url}</div> : null}
              {e.used ? <div className="text-[#646464]">Used in: {typo(e.used)}</div> : null}
            </div>
          );
        })}
      </div>
    </Section>
  );
}

/* ------------------------------------------------------------------ Appendices 3, 4, 6: method */

export function MethodAppendix() {
  const { view, ids, dimOf, indName, dimLabel } = useReport();
  const scale = view.scale || [];
  return (
    <>
      <Section id="how-to-read">
        <Eb>Appendix 3</Eb>
        <H2>How to read this report</H2>
        {(view.read || []).map((x, k) => (
          <p key={k} className="mb-3">
            {typo(x)}
          </p>
        ))}
        <DTable caption="Grade scale">
          <thead>
            <tr>
              <th className={th}>Average indicator score</th>
              <th className={th}>Grade</th>
              <th className={th}>Classification</th>
            </tr>
          </thead>
          <tbody>
            {scale.map((b, i) => (
              <tr key={b.grade}>
                <td className={td}>{b.min > 0 ? b.min.toFixed(2) + ' – ' + (i === 0 ? '5.00' : (scale[i - 1].min - 0.01).toFixed(2)) : 'below 2.00'}</td>
                <GradeCell grade={b.grade} />
                <td className={td}>{typo(b.label)}</td>
              </tr>
            ))}
          </tbody>
        </DTable>
      </Section>
      <Section id="methodology">
        <Eb>Appendix 4</Eb>
        <H2>Methodology and scoring rules</H2>
        {/* the internal quality-control rules (evidence de-duplication, repeat runs) are omitted, as in the legacy report */}
        <ol className="ml-6 list-decimal space-y-2">
          {(view.method || [])
            .filter((_, k) => k !== 9 && k !== 12)
            .map((x, k) => (
              <li key={k}>{typo(x.replace(/^\d+\s+/, ''))}</li>
            ))}
        </ol>
      </Section>
      <Section id="definitions">
        <Eb>Appendix 6</Eb>
        <H2>Indicator definitions and anchors</H2>
        {DIMS.map((d) => (
          <Fragment key={d}>
            <H3>
              {d}. {typo(dimLabel(d))}
            </H3>
            <Accordion.Root type="multiple" className="space-y-2">
              {ids
                .filter((i) => dimOf[i] === d)
                .map((i) => {
                  const x = view.defs[i];
                  if (!x) return null;
                  return (
                    <Accordion.Item key={i} value={i} className="rounded-lg border border-[#ECECEC] bg-white">
                      <Accordion.Header className="m-0">
                        <Accordion.Trigger className="group flex w-full items-center justify-between px-4 py-2 text-left font-bold text-[#002B49] focus-visible:outline focus-visible:outline-2 focus-visible:outline-[#0085CA]">
                          <span>
                            {i} {typo(indName(i))}
                          </span>
                          <span aria-hidden="true" className="text-[#0085CA] transition-transform group-data-[state=open]:rotate-90">
                            ▸
                          </span>
                        </Accordion.Trigger>
                      </Accordion.Header>
                      <Accordion.Content className="px-4 pb-3 print:block">
                        <p className="mb-2">{typo(x.def)}</p>
                        <Muted>{typo(x.prompt)}</Muted>
                        <DTable caption={`Scoring anchors for ${i}`}>
                          <thead>
                            <tr>
                              <th className={th}>1 – Day 2</th>
                              <th className={th}>3 – Mixed</th>
                              <th className={th}>5 – Day 1</th>
                            </tr>
                          </thead>
                          <tbody>
                            <tr>
                              <td className={td}>{typo(x.anchors['1'])}</td>
                              <td className={td}>{typo(x.anchors['3'])}</td>
                              <td className={td}>{typo(x.anchors['5'])}</td>
                            </tr>
                          </tbody>
                        </DTable>
                      </Accordion.Content>
                    </Accordion.Item>
                  );
                })}
            </Accordion.Root>
          </Fragment>
        ))}
      </Section>
    </>
  );
}

/* ------------------------------------------------------------------ coverage, themes, guardrails (accordions) */

function Acc({ items }: { items: { k: string; title: ReactNode; body: ReactNode }[] }) {
  return (
    <Accordion.Root type="multiple" className="space-y-2">
      {items.map((x) => (
        <Accordion.Item key={x.k} value={x.k} className="rounded-lg border border-[#ECECEC] bg-white">
          <Accordion.Header className="m-0">
            <Accordion.Trigger className="group flex w-full items-center justify-between px-4 py-2 text-left font-bold text-[#002B49] focus-visible:outline focus-visible:outline-2 focus-visible:outline-[#0085CA]">
              <span>{x.title}</span>
              <span aria-hidden="true" className="text-[#0085CA] transition-transform group-data-[state=open]:rotate-90">
                ▸
              </span>
            </Accordion.Trigger>
          </Accordion.Header>
          <Accordion.Content className="px-4 pb-3 print:block">{x.body}</Accordion.Content>
        </Accordion.Item>
      ))}
    </Accordion.Root>
  );
}

/** coverage note and the documents the run had / lacked; both stages, never inside-out content in outside-in */
export function CoverageAccordion() {
  const { view, io } = useReport();
  const cv = (view as unknown as { coverage?: { docs_available?: string[]; docs_unavailable?: string[] } }).coverage || {}; // the backend nests them under coverage
  const sup = (view.documents_provided?.[io ? 'io' : 'oi'] || []).map((d) => `Supplied by you: ${d.name}`);
  const have = [...sup, ...(cv.docs_available || view.docs_available || [])];
  const lack = cv.docs_unavailable || view.docs_unavailable || [];
  if (!view.coverage_note && !have.length && !lack.length) return null;
  const list = (t: string, a: string[]) => (a.length ? (
    <>
      <b>{t}</b>
      <ul className="mb-2 ml-5 list-disc">
        {a.map((x, k) => (
          <li key={k}>{typo(x)}</li>
        ))}
      </ul>
    </>
  ) : null);
  return (
    <Section id="coverage">
      <Acc items={[{ k: 'cov', title: 'Coverage and limitations', body: (
        <>
          {view.coverage_note ? <p className="mb-2"><i>{typo(view.coverage_note)}</i></p> : null}
          {list('Documents available', have)}
          {list('Documents not available', lack)}
        </>
      ) }]} />
    </Section>
  );
}

/** synthesised self-assessment themes (inside-out only) and guardrails; nothing when absent */
export function ThemesAndGuardrails() {
  const { view, io, dimLabel } = useReport();
  const th_ = io ? view.self_assessment_themes || [] : [];
  const gr = view.guardrails || [];
  if (!th_.length && !gr.length) return null;
  return (
    <Section id="themes-guardrails">
      {th_.length ? (
        <>
          <Eb>Appendix 7</Eb>
          <H2>Director self-assessment themes</H2>
          <Muted>Director responses are synthesised, not quoted.</Muted>
          <Acc items={th_.map((t, k) => ({ k: 'th' + k, title: `${t.dimension}${DIMN[t.dimension] ? '. ' + typo(dimLabel(t.dimension)) : ''}: ${typo(t.theme)}`, body: <p>{typo(t.summary)}</p> }))} />
        </>
      ) : null}
      {gr.length ? (
        <>
          <Eb>Appendix 8</Eb>
          <H2>Guardrails</H2>
          <Acc items={gr.map((g, k) => ({ k: 'gr' + k, title: typo(g.group), body: <ul className="ml-5 list-disc">{(g.items || []).map((x, j) => <li key={j}>{typo(x)}</li>)}</ul> }))} />
        </>
      ) : null}
    </Section>
  );
}

/* ------------------------------------------------------------------ dashboard */

function Card({ title, children, tone }: { title?: string; children: ReactNode; tone?: 'pos' | 'neg' }) {
  const border = tone === 'pos' ? 'border-l-4 border-l-[#00677F]' : tone === 'neg' ? 'border-l-4 border-l-[#A6192E]' : '';
  return (
    <div className={`mb-5 rounded-xl border border-[#ECECEC] bg-white px-6 py-5 shadow-sm print:break-inside-avoid ${border}`}>
      {title ? <H3 className="!mt-0">{title}</H3> : null}
      {children}
    </div>
  );
}

function useSeries(): { oi: Series; io: Series | null; peers: Series[] } {
  const { co, io, O, model, view } = useReport();
  return {
    oi: { name: io ? `${co} (outside-in)` : co, grades: DIMS.map((d) => O.dims[d].grade), color: NAVY },
    io: view.io ? { name: `${co} (after inside-out)`, grades: DIMS.map((d) => model.io.dims[d].grade), color: '#0085CA' } : null,
    peers: model.peers.map((p, k) => ({ name: p.name, grades: DIMS.map((d) => p.c.dims[d].grade), color: PEER_COLORS[k % PEER_COLORS.length] })),
  };
}

function DashOverview() {
  const { view, io, L, O, last, model, stage, dimLabel } = useReport();
  const findings = (stage === 'io' ? view.findings_io : view.findings_oi) || [];
  const g = L.overall.grade;
  return (
    <>
      <div className="mb-5 grid gap-4 md:grid-cols-2">
        <Kpi
          label={`Overall grade · ${io ? 'after inside-out' : 'outside-in'}`}
          value={
            <span className="flex items-center gap-3">
              <span className="inline-flex h-12 w-12 items-center justify-center rounded-lg text-2xl font-bold text-white" style={{ background: gradeColor(g) }}>
                {g || '–'}
              </span>
              <span>
                <b>{L.overall.label}</b>
                <span className="block text-[0.82rem] font-normal text-[#646464]">{L.overall.avg != null ? L.overall.avg.toFixed(2) + ' of 5.00' : 'n/a'}</span>
              </span>
            </span>
          }
        />
        <Kpi
          label={io ? 'Change vs outside-in' : 'Change vs earlier quarter'}
          value={io ? <Arrow now={model.io.overall.grade} prev={O.overall.grade} /> : last ? <Arrow now={O.overall.grade} prev={last.overall.grade} /> : <span className="text-[0.9rem] font-normal text-[#646464]">No earlier quarter selected</span>}
          sub={io ? (
            <>
              Outside-in <GradeChip grade={O.overall.grade} />
            </>
          ) : last ? (
            last.period
          ) : undefined}
        />
      </div>
      <Card>
        <div className="text-[0.72rem] font-bold uppercase tracking-[0.16em] text-[#0085CA]">Headline</div>
        <p className="my-2 text-[1.1rem] font-bold">{typo(io ? view.io?.headline : view.headline)}</p>
        <ol className="ml-5 list-decimal space-y-1">
          {findings.map((x, k) => (
            <li key={k}>
              <Codes text={x} />
            </li>
          ))}
        </ol>
      </Card>
      <Card title="Grades by dimension">
        <div className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_minmax(0,1.2fr)]">
          <DTable caption="Grades by dimension">
            <thead>
              <tr>
                <th className={th}>Dimension</th>
                <th className={th}>Outside-in</th>
                {io ? <th className={th}>After inside-out</th> : null}
                <th className={th}>Evidence</th>
              </tr>
            </thead>
            <tbody>
              {DIMS.map((d, k) => (
                <tr key={d}>
                  <td className={td}>
                    <b>
                      {d}. {typo(dimLabel(d))}
                    </b>
                  </td>
                  <GradeCell grade={O.dims[d].grade} />
                  {io ? <GradeCell grade={model.io.dims[d].grade} /> : null}
                  <td className={`${td} min-w-[240px]`}>
                    <Codes text={view.scorecard?.[k]?.line || ''} />
                  </td>
                </tr>
              ))}
              <tr className="font-bold">
                <td className={`${td} bg-[#EFF3F8]`}>Overall</td>
                <GradeCell grade={O.overall.grade} />
                {io ? <GradeCell grade={model.io.overall.grade} /> : null}
                <td className={td}>Rounded average of the dimension grades (A = 5 to F = 1).</td>
              </tr>
            </tbody>
          </DTable>
        </div>
      </Card>
    </>
  );
}

function DashIndicators() {
  const { view, io, ids, dimOf, O, model, ioCell, indLine, dimLabel } = useReport();
  return (
    <Card title="Rationale per indicator">
      <Muted>Each indicator is scored 1 (Day 2) to 5 (Day 1) against written anchors. Select an indicator for its definition and anchors; evidence codes open the source.</Muted>
      <DTable caption="Rationale per indicator">
        <thead>
          <tr>
            <th className={th}>Indicator</th>
            <th className={th}>Outside-in</th>
            {io ? <th className={th}>After inside-out</th> : null}
            <th className={th}>Summary of the evidence</th>
          </tr>
        </thead>
        <tbody>
          {DIMS.map((d) => (
            <Fragment key={d}>
              <tr>
                <td colSpan={io ? 4 : 3} className={`${td} bg-[#EFF3F8]`}>
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
                  const o = view.ind[i];
                  const c = io ? ioCell(i) : null;
                  const moved = !!c && !c.carried;
                  return (
                    <tr key={i}>
                      <td className={td}>
                        <IndButton id={i} /> {typo(o.name)}
                      </td>
                      <ScoreCell score={o.score} />
                      {c ? <ScoreCell score={c.score} /> : null}
                      <td className={`${td} min-w-[300px]`}>
                        {c && moved ? (
                          <>
                            <b>Inside-out:</b> <EvText text={firstSentence(c.rat)} ev={c.ev} />
                            <div className="text-[0.82rem] text-[#646464]">
                              Outside-in: <EvText text={indLine(i)} ev={o.ev} />
                            </div>
                          </>
                        ) : (
                          <>
                            <EvText text={indLine(i)} ev={o.ev} />
                            {io ? <div className="text-[0.82rem] text-[#646464]">Carried forward: nothing supplied settles this indicator.</div> : null}
                          </>
                        )}
                      </td>
                    </tr>
                  );
                })}
            </Fragment>
          ))}
        </tbody>
      </DTable>
    </Card>
  );
}

function DashInside() {
  const { view, ids, ioCell } = useReport();
  const ch = ids.filter((i) => !ioCell(i).carried);
  const better = view.io?.better || [];
  const worse = view.io?.worse || [];
  return (
    <>
      <Card title="What the board’s own material changed">
        <Muted>Indicators re-scored from the board documents and the directors’ anonymous self-assessment. Every other indicator keeps its outside-in score.</Muted>
        {ch.length ? (
          <DTable caption="Indicators re-scored from the board's own material">
            <thead>
              <tr>
                <th className={th}>Indicator</th>
                <th className={th}>Outside-in</th>
                <th className={th}>After inside-out</th>
                <th className={th}>Δ</th>
                <th className={th}>Evidence that moved the score</th>
              </tr>
            </thead>
            <tbody>
              {ch.map((i) => {
                const o = view.ind[i];
                const c = ioCell(i);
                return (
                  <tr key={i}>
                    <td className={td}>
                      <IndButton id={i} /> {typo(o.name)}
                    </td>
                    <ScoreCell score={o.score} />
                    <ScoreCell score={c.score} />
                    <DeltaCell a={o.score} b={c.score} />
                    <td className={td}>
                      <EvText text={c.rat} ev={c.ev} />
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </DTable>
        ) : (
          <Muted>No indicator was re-scored: nothing supplied settled an indicator.</Muted>
        )}
      </Card>
      <Card title="Better than the public record" tone="pos">
        {better.length ? (
          <ul className="ml-5 list-disc">
            {better.map((x, k) => (
              <li key={k}>
                <Codes text={x} />
              </li>
            ))}
          </ul>
        ) : (
          <Muted>None.</Muted>
        )}
      </Card>
      <Card title="Worse than the public record" tone="neg">
        {worse.length ? (
          <ul className="ml-5 list-disc">
            {worse.map((x, k) => (
              <li key={k}>
                <Codes text={x} />
              </li>
            ))}
          </ul>
        ) : (
          <Muted>None.</Muted>
        )}
      </Card>
    </>
  );
}

function DashPeers() {
  const { view, co, peers, ids, indName, model, O, indLine } = useReport();
  const s = useSeries();
  const rows = (view.peer_table || []).slice(1);
  const rel = ids.filter((i) => PEER_RELATIVE.includes(i));
  return (
    <>
      <Card title="Peer comparison">
        <Muted>Peers are graded outside-in from public information with the same rubric.</Muted>
        <PeerBars series={[{ ...s.oi, name: co }, ...s.peers]} />
        <DTable caption="Peer comparison">
          <thead>
            <tr>
              <th className={th}>Dimension</th>
              <th className={th}>{typo(co)}</th>
              {peers.map((p) => (
                <th key={p} className={th}>
                  {typo(p)}
                </th>
              ))}
              <th className={th}>How the company compares</th>
            </tr>
          </thead>
          <tbody>
            {DIMS.map((d, k) => {
              const r = rows[k] || [];
              return (
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
                    <Codes text={String((r.length ? r[r.length - 1] : '') ?? '')} />
                  </td>
                </tr>
              );
            })}
            <tr className="font-bold">
              <td className={`${td} bg-[#EFF3F8]`}>Overall</td>
              <GradeCell grade={O.overall.grade} />
              {model.peers.map((p) => (
                <GradeCell key={p.name} grade={p.c.overall.grade} />
              ))}
              <td className={td}>
                <Codes text={view.position || ''} />
              </td>
            </tr>
          </tbody>
        </DTable>
      </Card>
      <Card title="Peer-relative indicators">
        <Muted>Scored against the named peer set.</Muted>
        <PeerDotPlot rows={rel} />
        <DTable caption="Peer-relative indicators">
          <thead>
            <tr>
              <th className={th}>Indicator</th>
              <th className={th}>{typo(co)}</th>
              {peers.map((p) => (
                <th key={p} className={th}>
                  {typo(p)}
                </th>
              ))}
              <th className={th}>Evidence ({typo(co)})</th>
            </tr>
          </thead>
          <tbody>
            {rel.map((i) => (
              <tr key={i}>
                <td className={td}>
                  {i} {typo(indName(i))}
                </td>
                <ScoreCell score={view.ind[i].score} />
                {view.peers.map((p, k) => (
                  <ScoreCell key={k} score={p.ind?.[i]?.score} />
                ))}
                <td className={td}>
                  <EvText text={indLine(i)} ev={view.ind[i].ev} />
                </td>
              </tr>
            ))}
          </tbody>
        </DTable>
      </Card>
    </>
  );
}

function DashTrend() {
  const { view, io, ids, O, model, history, last, now, ioCell, indName } = useReport();
  if (!last)
    return (
      <Card title="Trend">
        <Muted>No earlier quarter is selected for this readout. Choose up to two earlier assessments on the outside-in page to see the trend.</Muted>
      </Card>
    );
  const ch = ids.filter((i) => last.ind[i] != null && now[i] != null && last.ind[i] !== now[i]);
  const points: TrendPoint[] = [
    ...history.map((x) => ({ period: x.period, grades: DIMS.map((d) => x.dims[d]?.grade ?? null), overall: x.overall.grade })),
    { period: view.meta.period, grades: DIMS.map((d) => O.dims[d].grade), overall: O.overall.grade },
    ...(io ? [{ period: 'Inside-out', grades: DIMS.map((d) => model.io.dims[d].grade), overall: model.io.overall.grade }] : []),
  ];
  return (
    <>
      <Card title="Grades by quarter">
        <TrendLines points={points} />
        <DTable caption="Grades by quarter">
          <thead>
            <tr>
              <th className={th}>Dimension</th>
              {history.map((x) => (
                <th key={x.period} className={th}>
                  {x.period}
                </th>
              ))}
              <th className={th}>{view.meta.period}</th>
              {io ? <th className={th}>Inside-out</th> : null}
            </tr>
          </thead>
          <tbody>
            {DIMS.map((d) => (
              <tr key={d}>
                <td className={td}>
                  {d}. {typo(DIMN[d])}
                </td>
                {history.map((x) => (
                  <GradeCell key={x.period} grade={x.dims[d]?.grade} />
                ))}
                <GradeCell grade={O.dims[d].grade} />
                {io ? <GradeCell grade={model.io.dims[d].grade} /> : null}
              </tr>
            ))}
            <tr className="font-bold">
              <td className={`${td} bg-[#EFF3F8]`}>Overall</td>
              {history.map((x) => (
                <GradeCell key={x.period} grade={x.overall.grade} />
              ))}
              <GradeCell grade={O.overall.grade} />
              {io ? <GradeCell grade={model.io.overall.grade} /> : null}
            </tr>
          </tbody>
        </DTable>
      </Card>
      <Card title={`What changed since ${last.period}`}>
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
                      {i} {typo(indName(i))}
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
      </Card>
    </>
  );
}

function DashActions() {
  const { io, actions, priorActions } = useReport();
  const pal = io ? priorActions : [];
  return (
    <>
      <Card title="What the board could do next">
        {actions.map((a) => (
          <div key={a.n} className="flex gap-3 border-b border-[#ECECEC] py-3 last:border-b-0">
            <span className="font-bold text-[#0085CA]">{a.n}</span>
            <div>
              <b>{typo(a.heading)}</b>
              <p className="m-0">
                <Codes text={a.description} />
              </p>
              <div className="text-[0.82rem] text-[#646464]">
                Target {typo(a.target || '–')}
                {(a.measures || []).length ? ' · ' + typo(a.measures.join('; ')) : ''}
              </div>
            </div>
          </div>
        ))}
      </Card>
      {pal.length ? (
        <Card title="Last quarter’s actions">
          <DTable caption="Last quarter's actions">
            <thead>
              <tr>
                <th className={th}>Action</th>
                <th className={th}>Status</th>
                <th className={th}>Evidence</th>
              </tr>
            </thead>
            <tbody>
              {pal.map((a, k) => (
                <tr key={a.id ?? k}>
                  <td className={td}>{typo(a.heading)}</td>
                  <td className={td}>
                    <StatusText status={a.status} />
                  </td>
                  <td className={td}>
                    <Codes text={a.note || ''} />
                    <div className="text-[0.82rem] text-[#646464]">{typo(a.metrics || '')}</div>
                  </td>
                </tr>
              ))}
            </tbody>
          </DTable>
        </Card>
      ) : null}
    </>
  );
}

export function Dashboard() {
  const { io, cofull, tk, view, peers, fileUrl } = useReport();
  const dashTab = useReportUi((s) => s.dashTab);
  const setDashTab = useReportUi((s) => s.setDashTab);
  const tabs: [DashTab, string][] = [['overview', 'Overview'], ['indicators', 'Indicators'], ...(io ? ([['inside', 'Inside-out changes']] as [DashTab, string][]) : []), ['peers', 'Peers'], ['trend', 'Trend'], ['actions', 'Actions']];
  const active: DashTab = tabs.some((t) => t[0] === dashTab) ? dashTab : 'overview';
  const html = fileUrl(io ? 'io_html' : 'oi_html');
  return (
    <div>
      <div className="mb-4 flex flex-wrap items-start justify-between gap-4 rounded-xl bg-[#002B49] px-6 py-5 text-white">
        <div>
          <div className="text-[0.72rem] font-bold uppercase tracking-[0.16em] text-[#80C2E4]">Board dashboard · {io ? 'After inside-out' : 'Outside-in'}</div>
          <h2 className="my-1 text-2xl font-bold">
            {typo(cofull)} <span className="ml-1.5 text-[0.95rem] font-normal text-[#AEC4DA]">{tk} · {view.meta.period}</span>
          </h2>
          <div className="text-[0.9rem] text-[#AEC4DA]">Benchmarked against {typo(listJoin(peers))}</div>
        </div>
        <div className="flex gap-2 print:hidden">
          {html ? (
            <a className={`${btnCls} !bg-transparent !text-white`} href={html} download>
              Download
            </a>
          ) : null}
        </div>
      </div>
      <Tabs.Root value={active} onValueChange={(v) => setDashTab(v as DashTab)}>
        <Tabs.List aria-label="Dashboard sections" className="mb-4 flex gap-1 overflow-x-auto border-b border-[#ECECEC] print:hidden">
          {tabs.map(([k, l]) => (
            <Tabs.Trigger key={k} value={k} className="whitespace-nowrap border-b-2 border-transparent px-4 py-3 text-[0.95rem] font-bold text-[#646464] outline-none focus-visible:ring-2 focus-visible:ring-[#0085CA] data-[state=active]:border-[#002B49] data-[state=active]:text-[#002B49]">
              {l}
            </Tabs.Trigger>
          ))}
        </Tabs.List>
        {tabs.map(([k]) => (
          <Tabs.Content key={k} value={k} className="outline-none">
            <motion.div initial={{ opacity: 0, y: 4 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.18 }}>
              {k === 'overview' ? <DashOverview /> : null}
              {k === 'indicators' ? <DashIndicators /> : null}
              {k === 'inside' ? <DashInside /> : null}
              {k === 'peers' ? <DashPeers /> : null}
              {k === 'trend' ? <DashTrend /> : null}
              {k === 'actions' ? <DashActions /> : null}
            </motion.div>
          </Tabs.Content>
        ))}
      </Tabs.Root>
    </div>
  );
}

/* ------------------------------------------------------------------ action plan */

export function ActionPlan() {
  const { view, io, cofull, tk, actions, priorActions, fileUrl } = useReport();
  const pal = io ? priorActions : [];
  const back = io && view.io?.back ? view.io.back : [];
  const targets = actions.map((a) => a.target).filter(Boolean).sort();
  const measures = actions.reduce((n, a) => n + (a.measures || []).length, 0);
  const docx = fileUrl(io ? 'io_docx' : 'oi_docx');
  return (
    <div>
      <div className="mb-4 flex flex-wrap items-start justify-between gap-4 rounded-xl bg-[#002B49] px-6 py-5 text-white">
        <div>
          <div className="text-[0.72rem] font-bold uppercase tracking-[0.16em] text-[#80C2E4]">Board action plan · {io ? 'After inside-out' : 'Outside-in'}</div>
          <h2 className="my-1 text-2xl font-bold">
            {typo(cofull)} <span className="ml-1.5 text-[0.95rem] font-normal text-[#AEC4DA]">{tk} · {view.meta.period}</span>
          </h2>
          <div className="text-[0.9rem] text-[#AEC4DA]">What the board could do next, each action tied to a finding, with measures and a target date.</div>
        </div>
        {docx ? (
          <a className={`${btnCls} !bg-transparent !text-white`} href={docx} download>
            Report (Word)
          </a>
        ) : null}
      </div>
      <div className="mb-5 grid gap-4 md:grid-cols-3">
        <Kpi label="Actions" value={actions.length} sub="Up to five per readout" />
        <Kpi label="First target" value={typo(targets[0] || '–')} sub={targets.length > 1 ? `Last ${typo(targets[targets.length - 1])}` : undefined} />
        <Kpi label="Measures" value={measures} sub="To track progress quarter by quarter" />
      </div>
      {actions.map((a) => (
        <div key={a.n} className="mb-4 flex gap-4 rounded-xl border border-[#ECECEC] bg-white px-5 py-4 shadow-sm print:break-inside-avoid">
          <div className="text-2xl font-bold text-[#0085CA]">{a.n}</div>
          <div className="min-w-0 flex-1">
            <div className="mb-1 flex flex-wrap items-baseline justify-between gap-2">
              <h3 className="m-0 text-[1.08rem] font-bold text-[#002B49]">{typo(a.heading)}</h3>
              <span className="rounded-full bg-[#EFF3F8] px-3 py-0.5 text-[0.8rem] font-bold">Target {typo(a.target || '–')}</span>
            </div>
            <p className="mb-2">
              <Codes text={a.description} />
            </p>
            {(a.measures || []).length ? (
              <>
                <div className="text-[0.72rem] font-bold uppercase tracking-[0.12em] text-[#646464]">How progress is measured</div>
                <ul className="ml-5 list-disc">
                  {a.measures.map((x, k) => (
                    <li key={k}>{typo(x)}</li>
                  ))}
                </ul>
              </>
            ) : null}
          </div>
        </div>
      ))}
      {pal.length ? (
        <>
          <H3>Last quarter’s actions</H3>
          <Card>
            {pal.map((a, k) => {
              const b = back.find((x) => x.id === a.id);
              return (
                <div key={a.id ?? k} className="flex gap-3 border-b border-[#ECECEC] py-3 last:border-b-0">
                  <i className="mt-1.5 h-2.5 w-2.5 flex-none rounded-full" style={{ background: a.status === 'completed' ? '#00677F' : a.status === 'behind' || a.status === 'not_started' ? '#A6192E' : a.status === 'on_track' ? '#0085CA' : '#969696' }} aria-hidden="true" />
                  <div className="min-w-0">
                    <b>{typo(a.heading)}</b>
                    <div className="text-[0.82rem] text-[#646464]">
                      <StatusText status={a.status} />
                      {a.note ? (
                        <>
                          {' · '}
                          <Codes text={a.note} />
                        </>
                      ) : null}
                    </div>
                    {b ? (
                      <details className="mt-2">
                        <summary className="cursor-pointer font-bold text-[#002B49]">How to get back on track</summary>
                        <div className="mt-1 text-[0.9rem]">
                          <p className="mb-1">
                            <b>What happened.</b> {typo(b.what)}
                          </p>
                          <p className="mb-1">
                            <b>Root cause.</b> {typo(b.cause)}
                          </p>
                          <p className="mb-1">
                            <b>To prevent it recurring.</b> {typo(b.prevent)}
                          </p>
                          {(b.measures || []).length ? (
                            <p className="mb-1">
                              <b>Measures.</b> {typo(b.measures.join('; '))}
                            </p>
                          ) : null}
                        </div>
                      </details>
                    ) : null}
                  </div>
                </div>
              );
            })}          </Card>
        </>
      ) : (
        <Muted>Progress on these actions is reviewed in the inside-out stage and in next quarter’s assessment.</Muted>
      )}
    </div>
  );
}
