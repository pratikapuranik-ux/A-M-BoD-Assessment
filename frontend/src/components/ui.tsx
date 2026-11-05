import { useEffect, useRef, useState, type ButtonHTMLAttributes, type AnchorHTMLAttributes, type ReactNode } from 'react'
import * as Dialog from '@radix-ui/react-dialog'
import * as Tooltip from '@radix-ui/react-tooltip'
import * as Accordion from '@radix-ui/react-accordion'
import * as Tabs from '@radix-ui/react-tabs'
import { AnimatePresence, motion } from 'framer-motion'
import { create } from 'zustand'
import { Icon, type IconName } from './Icon'
import { downloadUrl } from '../lib/journey'
import type { FileKey, JobView } from '../api/types'

/* ---------- toasts ---------- */
interface ToastState { items: { id: number; msg: string }[]; push: (m: string) => void }
let tid = 0
export const useToasts = create<ToastState>()((set) => ({
  items: [],
  push: (msg) => {
    const id = ++tid
    set((s) => ({ items: [...s.items, { id, msg }] }))
    setTimeout(() => set((s) => ({ items: s.items.filter((x) => x.id !== id) })), 2800)
  },
}))
export const toast = (msg: string) => useToasts.getState().push(msg)

export function Toaster() {
  const items = useToasts((s) => s.items)
  return (
    <div className="toasts" role="status" aria-live="polite">
      <AnimatePresence>
        {items.map((t) => (
          <motion.div key={t.id} className="toast" initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: 8 }}>{t.msg}</motion.div>
        ))}
      </AnimatePresence>
    </div>
  )
}

/* ---------- buttons ---------- */
type Variant = '' | 'sec' | 'inv' | 'ghost'
const bcls = (v: Variant, size?: 'sm' | 'lg', block?: boolean, extra?: string) => ['btn', v, size, block && 'block', extra].filter(Boolean).join(' ')

export function Button({ variant = '', size, block, icon, className, children, ...p }: ButtonHTMLAttributes<HTMLButtonElement> & { variant?: Variant; size?: 'sm' | 'lg'; block?: boolean; icon?: IconName }) {
  return <button type="button" className={bcls(variant, size, block, className)} {...p}>{icon && <Icon name={icon} size={size === 'sm' ? 14 : 16} />}{children}</button>
}
/** Primary "go on" button with a trailing arrow. */
export function NextButton({ children, ...p }: ButtonHTMLAttributes<HTMLButtonElement> & { variant?: Variant; size?: 'sm' | 'lg' }) {
  return <Button {...p}>{children}<Icon name="arrow" size={16} /></Button>
}
export function ButtonLink({ variant = 'sec', size, icon, children, ...p }: AnchorHTMLAttributes<HTMLAnchorElement> & { variant?: Variant; size?: 'sm' | 'lg'; icon?: IconName }) {
  return <a className={bcls(variant, size)} {...p}>{icon && <Icon name={icon} size={16} />}{children}</a>
}

/** Download button for a deliverable the backend has built; renders nothing until the file exists. */
export function DlButton({ files, k, label, icon = 'dl', variant = 'sec' }: { files?: Partial<Record<FileKey, string>>; k: FileKey; label: string; icon?: IconName; variant?: Variant }) {
  const url = files?.[k]
  if (!url) return null
  return <Button variant={variant} icon={icon} onClick={() => { downloadUrl(url); toast('Downloading…') }}>{label}</Button>
}

/** The one control for adding files or a folder. The browser's own "Choose file" control looks different on every machine, so this is a button
 *  that opens the same dialog; the chosen files go to `onFiles`. */
export function AddFiles({ onFiles, accept, multiple = true, folder = false, label = 'Add files', icon = 'upload', variant = 'sec', size = 'sm', ariaLabel }: {
  onFiles: (files: FileList | null) => void; accept?: string; multiple?: boolean; folder?: boolean; label?: string; icon?: IconName; variant?: Variant; size?: 'sm' | 'lg'; ariaLabel?: string
}) {
  const ref = useRef<HTMLInputElement>(null)
  return (
    <>
      <Button variant={variant} size={size} icon={icon} onClick={() => ref.current?.click()}>{label}</Button>
      <input ref={ref} type="file" hidden multiple={multiple} accept={accept} aria-label={ariaLabel || label} value="" onChange={(e) => onFiles(e.target.files)}
        {...(folder ? ({ webkitdirectory: '', directory: '' } as Record<string, string>) : {})} />
    </>
  )
}

/* ---------- bits ---------- */
export const Card = ({ className = '', children, ...p }: { className?: string; children: ReactNode } & React.HTMLAttributes<HTMLDivElement>) => <div className={`card ${className}`} {...p}>{children}</div>

export function Notice({ kind = '', children }: { kind?: '' | 'ok' | 'bad'; children: ReactNode }) {
  return <div className={`notice ${kind}`} role={kind === 'bad' ? 'alert' : undefined}>{children}</div>
}

export const GradeChip = ({ g }: { g?: string | null }) => <span className={`g g${g || 'NA'}`}>{g || 'n/a'}</span>
export const GradeSquare = ({ g, size = '' }: { g?: string | null; size?: '' | 'sm' | 'xl' }) => <span className={`gsq ${size} g${g || 'NA'}`}>{g || '–'}</span>
export const Chip = ({ children, onRemove, label }: { children: ReactNode; onRemove?: () => void; label?: string }) => (
  <div className="chip">{children}{onRemove && <button type="button" onClick={onRemove} aria-label={label || 'Remove'}>×</button>}</div>
)

export function Meter({ pct }: { pct: number }) {
  return <div className="meter" role="presentation"><i style={{ width: `${Math.max(0, Math.min(100, pct))}%`, transition: 'width .25s' }} /></div>
}

export function PageHead({ title, sub, right, eyebrow }: { title: ReactNode; sub?: ReactNode; right?: ReactNode; eyebrow?: ReactNode }) {
  return (
    <div className="rh">
      <div>{eyebrow && <div className="peb">{eyebrow}</div>}<h1>{title}</h1>{sub && <p className="sub">{sub}</p>}</div>
      {right && <div className="row">{right}</div>}
    </div>
  )
}

export const KpiTile = ({ label, value, sub }: { label: string; value: ReactNode; sub: ReactNode }) => (
  <div className="kpi"><div className="kl">{label}</div><div className="kv2v">{value}</div><div className="ks">{sub}</div></div>
)

export function FadeIn({ children, delay = 0, className }: { children: ReactNode; delay?: number; className?: string }) {
  return <motion.div className={className} initial={{ opacity: 0, y: 14 }} whileInView={{ opacity: 1, y: 0 }} viewport={{ once: true, amount: 0.12 }} transition={{ duration: 0.5, delay }}>{children}</motion.div>
}

/* ---------- Radix wrappers ---------- */
export function AppDialog({ open, onOpenChange, title, description, size = '', children }: { open: boolean; onOpenChange: (o: boolean) => void; title: string; description?: string; size?: '' | 'mid' | 'wide'; children: ReactNode }) {
  return (
    <Dialog.Root open={open} onOpenChange={onOpenChange}>
      <Dialog.Portal>
        <Dialog.Overlay className="dlg-overlay" />
        <Dialog.Content className={`dlg-content ${size}`}>
          <Dialog.Title style={{ margin: '0 0 8px', color: 'var(--navy)', fontSize: '1.2rem' }}>{title}</Dialog.Title>
          {description ? <Dialog.Description className="muted">{description}</Dialog.Description> : <Dialog.Description className="sr-only">{title}</Dialog.Description>}
          {children}
          <Dialog.Close className="dlg-close" aria-label="Close">×</Dialog.Close>
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  )
}

export function Tip({ text, children }: { text: string; children: ReactNode }) {
  return (
    <Tooltip.Root delayDuration={200}>
      <Tooltip.Trigger asChild>{children}</Tooltip.Trigger>
      <Tooltip.Portal><Tooltip.Content className="tip-content" sideOffset={6}>{text}<Tooltip.Arrow fill="#002B49" /></Tooltip.Content></Tooltip.Portal>
    </Tooltip.Root>
  )
}
export const TipProvider = Tooltip.Provider

/** Collapsible "details" block. */
export function Collapsible({ summary, children, className = '' }: { summary: ReactNode; children: ReactNode; className?: string }) {
  return (
    <Accordion.Root type="single" collapsible>
      <Accordion.Item value="x" className={`acc-item ${className}`}>
        <Accordion.Header style={{ margin: 0 }}><Accordion.Trigger className="acc-trigger">{summary}</Accordion.Trigger></Accordion.Header>
        <Accordion.Content><div className="dbody">{children}</div></Accordion.Content>
      </Accordion.Item>
    </Accordion.Root>
  )
}

export function SegTabs<T extends string>({ value, onChange, tabs }: { value: T; onChange: (v: T) => void; tabs: [T, string][] }) {
  return (
    <Tabs.Root value={value} onValueChange={(v) => onChange(v as T)}>
      <Tabs.List className="seg2" aria-label="Add a company">
        {tabs.map(([v, l]) => <Tabs.Trigger key={v} value={v} className={value === v ? 'on' : ''} style={{ border: 0, background: value === v ? '#fff' : 'none' }}>{l}</Tabs.Trigger>)}
      </Tabs.List>
    </Tabs.Root>
  )
}

/* ---------- job progress ---------- */
/** The steps of a research run, found from the messages the server logs; the furthest step seen is the current one. */
const RUN_STEPS: [string, RegExp][] = [
  ['Read your documents', /^(Started|Reading|Scoring ruling|Uploading)/],
  ['Summarise them', /^(Extracting key facts|Cross-checking)/],
  ['Research', /^(Researching |Starting research|Searching the documents|Reading a page|Weighing|Writing up|Reviewing .* retrieval)/],
  ['Check and grade', /^(Comparing the company|Fixing|Checking the finished|Stored as|Writing the headline)/],
  ['Build the report', /^(Building |Deliverables)/],
]
const msgOf = (l: string) => l.replace(/^\d\d:\d\d:\d\d\s+/, '')
const elapsedSince = (log: string[]) => {
  const f = log[0]?.match(/^(\d\d):(\d\d):(\d\d)/)
  if (!f) return null
  const now = new Date(), n = now.getHours() * 3600 + now.getMinutes() * 60 + now.getSeconds()
  return (n - (+f[1] * 3600 + +f[2] * 60 + +f[3]) + 86400) % 86400
}
const fmtElapsed = (s: number) => (s < 60 ? `${s} s` : `${Math.floor(s / 60)} min ${String(s % 60).padStart(2, '0')} s`)

export function JobProgress({ job, problems, onBack, leaveText = 'You can leave this page; the work continues in the background.' }: { job: JobView; problems?: unknown[]; onBack?: () => void; leaveText?: string }) {
  const pct = Math.max(2, Math.min(100, job.progress || 0))
  const log = job.log || [], msgs = log.map(msgOf)
  const live = job.status !== 'done' && job.status !== 'error'
  const [, tick] = useState(0)
  useEffect(() => { if (!live) return; const t = setInterval(() => tick((x) => x + 1), 5000); return () => clearInterval(t) }, [live])
  const isRun = msgs.some((m) => /^(Scoring ruling|Researching |Extracting key facts|Starting research)/.test(m))
  const cur = job.status === 'done' ? RUN_STEPS.length : Math.max(0, ...RUN_STEPS.map(([, re], i) => (msgs.some((m) => re.test(m)) ? i : 0)))
  const firms = [...new Set(msgs.map((m) => m.match(/^Starting research on (.+)$/)?.[1]).filter((x): x is string => !!x))]
  const scored = new Set(msgs.map((m) => m.match(/^Scored (.+)'s board on all 22/)?.[1]).filter((x): x is string => !!x))
  const el = live ? elapsedSince(log) : null
  return (
    <div className="job">
      <div className="jt"><b>{job.message || 'Working…'}</b><span>{Math.round(pct)}%</span></div>
      <div className="bar2" role="progressbar" aria-valuenow={Math.round(pct)} aria-valuemin={0} aria-valuemax={100}><i style={{ width: `${pct}%` }} /></div>
      {isRun && (
        <ol className="jsteps" aria-label="Steps">
          {RUN_STEPS.map(([name], i) => (
            <li key={name} className={i < cur ? 'done' : i === cur ? 'now' : ''} aria-current={i === cur ? 'step' : undefined}>
              <span className="jn">{i < cur ? <Icon name="check" size={12} /> : i + 1}</span>{name}
            </li>
          ))}
        </ol>
      )}
      {isRun && firms.length > 0 && (
        <div className="jfirms" aria-label="Companies">
          {firms.map((f) => <span key={f} className={`jfirm${scored.has(f) || job.status === 'done' ? ' done' : ''}`}>{scored.has(f) || job.status === 'done' ? <Icon name="check" size={12} /> : <i className="jdot" />}{f}</span>)}
        </div>
      )}
      {el != null && <p className="ks">{fmtElapsed(el)} elapsed</p>}
      <details className="jdetail"><summary>Show details</summary><ul className="jlog">{log.slice(-12).map((x, i) => <li key={i}>{x}</li>)}</ul></details>
      {job.status === 'error'
        ? <><Notice kind="bad"><b>{job.error || 'This could not be completed.'}</b>{problems && problems.length > 0 && <ul>{problems.slice(0, 10).map((p, i) => <li key={i}>{fmtProblem(p)}</li>)}</ul>}</Notice>{onBack && <Button variant="sec" onClick={onBack}>Back</Button>}</>
        : <p className="ks">{leaveText}</p>}
    </div>
  )
}
export const fmtProblem = (p: unknown) => (Array.isArray(p) ? p.join(' · ') : typeof p === 'string' ? p : JSON.stringify(p))

