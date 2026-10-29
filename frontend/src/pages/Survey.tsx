import { useEffect, useRef, useState, type ReactNode } from 'react';
import { useParams } from 'react-router-dom';
import { AnimatePresence, motion } from 'framer-motion';
import type { SurveyForm } from '../api/viewTypes';

/* The anonymous board self-assessment a director opens from a personal link (js/survey.js, respondent's page).
   It shows only the questions, never the assessment itself. Uses plain fetch against /api/survey/{token}. */

const DRAFT = 'DRAFT ONLY - Requires review and approval by a qualified Alvarez and Marsal professional before use.';
const NUMW = ['no', 'one', 'two', 'three', 'four', 'five', 'six', 'seven', 'eight', 'nine', 'ten', 'eleven', 'twelve', 'thirteen', 'fourteen', 'fifteen', 'sixteen', 'seventeen', 'eighteen', 'nineteen', 'twenty'];
const numWord = (n: number) => NUMW[n] ?? String(n);
const cap = (s: string) => s.charAt(0).toUpperCase() + s.slice(1);
const typo = (s: string) => s.replace(/(\w)'(\w)/g, '$1’$2').replace(/(\w)'(\s)/g, '$1’$2');

const RATING_OPTIONS: [number, string][] = [
  [1, 'Mostly Day 2'],
  [3, 'Mixed'],
  [5, 'Mostly Day 1'],
];

/** Language guardrails (references/guardrails.md): the board as a body, non-accusatory, no legal conclusions or investment advice. */
function guardrailScan(text: string): string[] {
  const w: string[] = [];
  const t = text || '';
  if (/\b(Mr|Mrs|Ms|Mx|Dr|Prof)\.?\s+[A-Z][a-z]+/.test(t) || /\b(director|chair|chairman|CEO|CFO)\s+[A-Z][a-z]+\s+[A-Z][a-z]+/.test(t)) w.push('Names an individual. Grades apply to the board as a body; refer to roles or the board.');
  if (/\b(incompetent|corrupt|lazy|dishonest|lying|liar)\b/i.test(t)) w.push('Characterises people. Keep language evidence-based and non-accusatory.');
  if (/breach(ed|es)?\s+(of\s+|its\s+|their\s+|the\s+)?(fiduciary\s+)?dut|\bfraud|\billegal|\bunlawful|negligen|\bliable\b|violat(ed|ion) of (the )?(law|securities)/i.test(t)) w.push('Reads as a legal conclusion. Describe what the record shows instead.');
  if (/\b(buy|sell|short)\s+(the\s+)?(stock|shares)|price target|will (rise|fall|outperform|underperform)|undervalued|overvalued/i.test(t)) w.push('Reads as investment advice or a share-price view.');
  return w;
}

class ApiFail extends Error {
  status: number;
  constructor(message: string, status: number) {
    super(message);
    this.status = status;
  }
}

async function call<T>(path: string, init?: RequestInit): Promise<T> {
  const r = await fetch('/api' + path, { headers: { 'Content-Type': 'application/json' }, ...init });
  let j: unknown = null;
  try {
    j = await r.json();
  } catch {
    /* no body */
  }
  if (!r.ok) {
    const o = (j || {}) as { error?: string; detail?: unknown };
    const detail = typeof o.detail === 'string' ? o.detail : undefined;
    throw new ApiFail(o.error || detail || `Request failed (${r.status})`, r.status);
  }
  return j as T;
}

type Step = 'loading' | 'intro' | 'form' | 'done' | 'error';

function Card({ children, className = '' }: { children: ReactNode; className?: string }) {
  return <div className={`mb-5 rounded-xl border border-[#ECECEC] bg-white p-6 shadow-sm sm:p-9 ${className}`}>{children}</div>;
}
const Peb = ({ children }: { children: ReactNode }) => <div className="mb-2 text-[0.72rem] font-bold uppercase tracking-[0.16em] text-[#0085CA]">{children}</div>;
const primaryBtn =
  'inline-flex items-center justify-center gap-2 rounded-lg bg-[#002B49] px-6 py-3 text-base font-bold text-white hover:bg-[#1A405B] disabled:cursor-not-allowed disabled:opacity-50 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[#0085CA]';

function Anon({ min }: { min: number }) {
  return (
    <div className="my-2 mb-6 rounded-[10px] border border-[#5E8AB4] bg-[#EFF3F8] px-5 py-4">
      <div className="mb-1.5 flex items-center gap-2.5 text-[#002B49]">
        <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
          <rect x="5" y="11" width="14" height="10" rx="2" />
          <path d="M8 11V8a4 4 0 0 1 8 0v3" />
        </svg>
        <b>Your response is anonymous</b>
      </div>
      <ul className="ml-5 mt-1.5 list-disc">
        <li className="my-1.5">
          {(min || 3) >= 3 ? 'Your answers are pooled with those of at least two other directors before anyone reads them. ' : 'Your answers are pooled with other directors’ responses. '}
          They are never attributed to you, and nothing in the results can be traced back to you or to this invitation.
        </li>
        <li className="my-1.5">The questions are about how the board works as a body, not about any individual. Please describe practices and examples rather than naming colleagues.</li>
      </ul>
    </div>
  );
}

export default function SurveyPage(): JSX.Element {
  const { token = '' } = useParams<{ token: string }>();
  const [form, setForm] = useState<SurveyForm | null>(null);
  const [step, setStep] = useState<Step>('loading');
  const [answers, setAnswers] = useState<Record<number, string>>({});
  const [ratings, setRatings] = useState<Record<string, number>>({});
  const [err, setErr] = useState('');
  const [warnings, setWarnings] = useState<string[]>([]);
  const [warned, setWarned] = useState(false);
  const [busy, setBusy] = useState(false);
  const warnRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    document.title = 'Board self-assessment';
  }, []);

  useEffect(() => {
    let live = true;
    setStep('loading');
    call<SurveyForm>('/survey/' + encodeURIComponent(token))
      .then((f) => {
        if (!live) return;
        setForm(f);
        setStep(f.responded ? 'done' : 'intro');
      })
      .catch((e: Error) => {
        if (!live) return;
        setErr(e.message);
        setStep('error');
      });
    return () => {
      live = false;
    };
  }, [token]);

  useEffect(() => {
    if (warnings.length) warnRef.current?.scrollIntoView({ behavior: 'smooth', block: 'center' });
  }, [warnings]);

  const submit = async () => {
    const filled = Object.keys(answers).filter((k) => (answers[Number(k)] || '').trim());
    if (!filled.length) {
      setErr('Please answer at least one question.');
      return;
    }
    const warn: string[] = [];
    filled.forEach((k) => guardrailScan(answers[Number(k)]).forEach((m) => warn.push(`Question ${k}: ${m}`)));
    if (warn.length && !warned) {
      setWarned(true);
      setErr('');
      setWarnings(warn);
      return;
    }
    setBusy(true);
    setErr('');
    try {
      await call<{ ok: boolean }>('/survey/' + encodeURIComponent(token), { method: 'POST', body: JSON.stringify({ answers, ratings }) });
      setStep('done');
    } catch (e) {
      const m = (e as Error).message;
      setErr(m);
      if (/already been received/.test(m)) setStep('done');
    }
    setBusy(false);
    window.scrollTo(0, 0);
  };

  const dims: string[] = [];
  form?.questions.forEach((q) => {
    if (!dims.includes(q.dimension)) dims.push(q.dimension);
  });

  return (
    <div className="min-h-screen bg-[#F7F9FB] text-[15px] leading-relaxed text-[#002B49]">
      <header className="border-b border-[#ECECEC] bg-white">
        <div className="mx-auto flex max-w-[860px] items-center gap-3 px-4 py-3 sm:px-8">
          <img src="/logo-wordmark.png" alt="Alvarez & Marsal" className="h-8 w-auto" />
          <span className="h-6 w-px bg-[#D9D9D9]" aria-hidden="true" />
          <span className="font-bold">Board Assessment</span>
        </div>
      </header>
      <main className="mx-auto max-w-[860px] px-4 py-9 sm:px-8">
        <AnimatePresence mode="wait">
          <motion.div key={step} initial={{ opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0 }} transition={{ duration: 0.18 }}>
            {step === 'loading' ? (
              <Card>
                <p className="m-0 text-[#646464]" role="status">
                  Loading…
                </p>
              </Card>
            ) : null}

            {step === 'error' ? (
              <Card>
                <h2 className="mb-2 text-[1.3rem] font-bold">This link cannot be used</h2>
                <p className="mb-3 text-[0.9rem] text-[#646464]">{typo(err)}</p>
                <p className="m-0 text-[0.9rem] text-[#646464]">If you think this is a mistake, ask the person who invited you for a new link.</p>
              </Card>
            ) : null}

            {step === 'done' ? (
              <Card>
                <Peb>Board self-assessment</Peb>
                <h2 className="mb-2 text-[1.3rem] font-bold">Thank you</h2>
                <p className="mb-3">Your response has been received. It will be pooled with other directors’ responses and is not attributed to you.</p>
                <p className="m-0 text-[0.9rem] text-[#646464]">You can close this page.</p>
              </Card>
            ) : null}

            {step === 'intro' && form ? (
              <Card>
                <Peb>Board self-assessment</Peb>
                <h1 className="mb-1 mt-1.5 text-[2rem] font-bold leading-tight text-[#002B49]">Take the assessment</h1>
                <p className="mb-4 text-base text-[#646464]">
                  {typo(form.company)}
                  {form.period ? ' · ' + form.period : ''}
                </p>
                <Anon min={form.min} />
                <p className="mb-4 text-[0.9rem] text-[#646464]">{cap(numWord(form.questions.length))} questions across six themes · about 15 minutes</p>
                <button
                  type="button"
                  className={primaryBtn}
                  onClick={() => {
                    setStep('form');
                    window.scrollTo(0, 0);
                  }}
                >
                  Take the assessment <span aria-hidden="true">→</span>
                </button>
              </Card>
            ) : null}

            {step === 'form' && form ? (
              <>
                <div className="mb-5">
                  <Peb>Board self-assessment · {typo(form.company)}</Peb>
                  <h1 className="mb-1.5 mt-1.5 text-[2rem] font-bold leading-tight text-[#002B49]">How the board works</h1>
                  <p className="m-0 text-[0.9rem] text-[#646464]">Anonymous. Answer as many questions as you can; you can leave a question blank.</p>
                </div>
                {dims.map((d) => {
                  const qs = form.questions.filter((q) => q.dimension === d);
                  return (
                    <Card key={d}>
                      <h3 className="mb-2 text-[1.08rem] font-bold">
                        {d}. {typo(qs[0].dimension_name)}
                      </h3>
                      {qs.map((q) => (
                        <div key={q.n} className="mb-1.5">
                          <label htmlFor={`ra${q.n}`} className="mb-1.5 mt-3.5 block text-[0.95rem] font-bold">
                            {q.n}. {typo(q.text)}
                          </label>
                          <textarea
                            id={`ra${q.n}`}
                            value={answers[q.n] || ''}
                            onChange={(e) => {
                              setAnswers((a) => ({ ...a, [q.n]: e.target.value }));
                              setWarned(false);
                              setWarnings([]);
                            }}
                            rows={4}
                            className="w-full rounded-lg border border-[#D9D9D9] px-3 py-2 text-[0.95rem] focus-visible:outline focus-visible:outline-2 focus-visible:outline-[#0085CA]"
                          />
                        </div>
                      ))}
                      <fieldset className="mt-3.5 border-0 p-0">
                        <legend className="mb-1.5 text-[0.95rem] font-bold">Overall, how would you describe the board on this theme?</legend>
                        <div className="flex flex-wrap gap-6">
                          {RATING_OPTIONS.map(([v, l]) => (
                            <label key={v} className="inline-flex cursor-pointer items-center gap-2">
                              <input type="radio" name={`rr${d}`} value={v} checked={ratings[d] === v} onChange={() => setRatings((r) => ({ ...r, [d]: v }))} className="h-4 w-4 accent-[#002B49]" /> {l}
                            </label>
                          ))}
                        </div>
                      </fieldset>
                    </Card>
                  );
                })}
                <div ref={warnRef}>
                  {warnings.length ? (
                    <div role="alert" className="mb-4 rounded-r-lg border-l-[3px] border-[#5E8AB4] bg-[#EFF3F8] px-4 py-3 text-[0.9rem]">
                      <b>Before you submit.</b> To keep the assessment about the board as a body:
                      <ul className="ml-5 mt-1 list-disc">
                        {warnings.map((w, k) => (
                          <li key={k}>{typo(w)}</li>
                        ))}
                      </ul>
                      You can edit your answers, or submit them as they are.
                    </div>
                  ) : null}
                </div>
                <div className="mb-3 min-h-[1.2rem] text-[0.9rem] font-bold text-[#002B49]" role={err ? 'alert' : undefined}>
                  {typo(err)}
                </div>
                <div className="flex flex-wrap items-center justify-between gap-3">
                  <span className="text-[0.9rem] text-[#646464]">Your response is anonymous.</span>
                  <button type="button" className={primaryBtn} disabled={busy} onClick={submit}>
                    Submit my response <span aria-hidden="true">→</span>
                  </button>
                </div>
              </>
            ) : null}
          </motion.div>
        </AnimatePresence>
      </main>
      <footer className="px-4 pb-8 text-center text-[0.78rem] italic text-[#646464]">
        <div className="mx-auto max-w-[860px]">{DRAFT}</div>
      </footer>
    </div>
  );
}
