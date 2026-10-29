import * as Dialog from '@radix-ui/react-dialog';
import { AnimatePresence, motion } from 'framer-motion';
import type { ReactNode } from 'react';
import { useReportUi } from '../store/reportUi';
import { Codes, DTable, ScoreChip, btnCls, td, th } from './parts';
import { typo, useReport } from './context';

function Shell({ title, description, children }: { title: string; description: string; children: ReactNode }) {
  const close = useReportUi((s) => s.closeDialog);
  return (
    <Dialog.Root open onOpenChange={(o) => !o && close()}>
      <Dialog.Portal forceMount>
        <AnimatePresence>
          <Dialog.Overlay asChild forceMount>
            <motion.div className="fixed inset-0 z-[60] bg-[#002B49]/50 print:hidden" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} transition={{ duration: 0.15 }} />
          </Dialog.Overlay>
          <Dialog.Content asChild forceMount>
            <motion.div
              className="fixed left-1/2 top-1/2 z-[61] max-h-[85vh] w-[min(640px,92vw)] -translate-x-1/2 -translate-y-1/2 overflow-y-auto rounded-xl bg-white p-6 shadow-2xl print:hidden"
              initial={{ opacity: 0, y: 8 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: 8 }}
              transition={{ duration: 0.18 }}
            >
              <Dialog.Title className="mb-2 text-[1.08rem] font-bold text-[#002B49]">{title}</Dialog.Title>
              <Dialog.Description className="sr-only">{description}</Dialog.Description>
              {children}
              <div className="mt-4">
                <Dialog.Close className={btnCls}>Close</Dialog.Close>
              </div>
            </motion.div>
          </Dialog.Content>
        </AnimatePresence>
      </Dialog.Portal>
    </Dialog.Root>
  );
}

function AnchorTable({ anchors }: { anchors: Record<'1' | '3' | '5', string> }) {
  return (
    <DTable caption="Scoring anchors">
      <thead>
        <tr>
          <th className={th}>1 – Day 2</th>
          <th className={th}>3 – Mixed</th>
          <th className={th}>5 – Day 1</th>
        </tr>
      </thead>
      <tbody>
        <tr>
          <td className={td}>{typo(anchors['1'])}</td>
          <td className={td}>{typo(anchors['3'])}</td>
          <td className={td}>{typo(anchors['5'])}</td>
        </tr>
      </tbody>
    </DTable>
  );
}

/** indicator definition, scores and anchors (legacy showInd) */
function IndicatorDialog({ id }: { id: string }) {
  const { view, stage, ioCell } = useReport();
  const o = view.ind[id];
  const x = view.defs[id];
  if (!o || !x) return <EvidenceMissing id={id} />;
  const io = stage === 'io' ? ioCell(id) : null;
  return (
    <Shell title={`${id} ${typo(o.name)}`} description={`Definition, scores and scoring anchors for indicator ${id}`}>
      <p className="mb-3 text-[0.9rem] text-[#646464]">{typo(x.def)}</p>
      <p className="mb-3">
        Outside-in <ScoreChip score={o.score} />
        {io ? (
          <>
            {' '}
            → after inside-out <ScoreChip score={io.score} />
          </>
        ) : null}{' '}
        <span className="text-[0.9rem] text-[#646464]">{o.conf} confidence</span>
      </p>
      <p className="mb-3">
        <Codes text={o.rationale} />
      </p>
      {io ? (
        <p className="mb-3">
          <b>Inside-out:</b> <Codes text={io.rat} />
        </p>
      ) : null}
      <AnchorTable anchors={x.anchors} />
    </Shell>
  );
}

function EvidenceMissing({ id }: { id: string }) {
  return (
    <Shell title={id} description="Source not available">
      <p className="text-[0.9rem] text-[#646464]">This item is not available: the source was not supplied in this run.</p>
    </Shell>
  );
}

/** one evidence item (legacy showEv) */
function EvidenceDialog({ code }: { code: string }) {
  const { evOf } = useReport();
  const e = evOf(code);
  if (!e) return <EvidenceMissing id={code} />;
  return (
    <Shell title={code} description={`Source document for evidence code ${code}`}>
      <p className="mb-2">
        <b>{typo(e.doc)}</b>
      </p>
      <p className="mb-2 text-[0.9rem] text-[#646464]">
        {e.date || ''}
        {e.recent ? ' · RECENT' : ''}
      </p>
      {e.question ? (
        <p className="mb-2">
          <b>Question:</b> {typo(e.question)}
        </p>
      ) : null}
      {/* self-assessment items hold director free text: never shown, only the question */}
      {code.startsWith('SA') ? <p className="mb-2 text-[0.9rem] text-[#646464]">Director responses are synthesised, not quoted.</p> : <p className="mb-2">“{typo(e.excerpt || '')}”</p>}
      {e.url ? <p className="mb-2 break-all text-[0.9rem] text-[#646464]">{e.url}</p> : null}
      {e.used ? <p className="mb-2 text-[0.9rem] text-[#646464]">Used in: {typo(e.used)}</p> : null}
    </Shell>
  );
}

/** mounted once by ReportView; shows whichever dialog the store has open */
export function ReportDialogs() {
  const dialog = useReportUi((s) => s.dialog);
  if (!dialog) return null;
  return dialog.kind === 'ind' ? <IndicatorDialog id={dialog.id} /> : <EvidenceDialog code={dialog.id} />;
}
