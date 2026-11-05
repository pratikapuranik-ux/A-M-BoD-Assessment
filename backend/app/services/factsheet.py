"""Stage one of the supplied-documents path: a fact sheet for each document, and a cross-document review per subject.

Each document is read once, in sections, by a smaller model that lists the facts a board assessment can use (every figure with its
unit and period, with the page it came from). The sheet is stored with the document in the assessment's library, so a re-run does
not read it again. Then, per subject (the company or a peer), the sheets are set side by side and a review lists what the documents
agree on, where they disagree (with file and page for each value) and what is missing. The original text stays in the library and
is reachable through search and page-read tools, so any figure on a sheet can be checked against the source.
"""
from __future__ import annotations

import os
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Callable

from app.log import get_logger

log = get_logger(__name__)
Progress = Callable[[str], None]

ENABLED = (os.environ.get("BOARD_FACTSHEETS") or "1").lower() not in ("0", "false", "no")
CHARS_PER_TOKEN = 3.2
MIN_TOKENS = 6_000  # a document shorter than this is used as it is: a sheet would not save anything
SECTION_CHARS = 150_000  # one section sent for extraction (about 47k tokens)
PARALLEL = 8
REVIEW_BATCH_TOKENS = 120_000  # fact sheets compared in one request
MAX_INPUT_TOKENS = int(os.environ.get("BOARD_FACTSHEET_MAX_TOKENS") or 2_000_000)  # document text read for fact sheets per run; the rest is searched only

SHEET_PROMPT = (
    "Section {i} of {n} of the document \"{name}\", supplied by an advisory team that is assessing a company's board, is below. "
    "List the facts in it that could serve as evidence about a board and the company it governs. Write compact bullets under these "
    "headings and omit a heading with nothing under it: Document (type, entity, period or date); Board and governance (directors, "
    "tenure, independence, committees, evaluation, refreshment, succession, pay and incentives, shareholder rights); Strategy and "
    "performance; Capital allocation and financials (every key figure with its unit and period); Risk, controversies and adverse "
    "events; Commitments, targets and dates. One fact per line, ending with the page in the form [p.N], from the [page N] markers. "
    "Copy figures, names and dates exactly as written. Do not interpret, estimate or add anything that is not in the text.\n\n<section>\n{text}\n</section>"
)
REVIEW_PROMPT = (
    "Below are fact sheets drawn from {n} documents supplied on {subject}. Compare them and report, as short bullets with the file "
    "name and page for every value you cite: (1) Inconsistencies: the same fact or metric stated with different values, or statements "
    "that conflict, across documents or periods (note when a different date or definition could explain the difference); "
    "(2) Corroborated: key facts that two or more documents agree on; (3) Gaps: topics a board assessment needs that none of the "
    "documents covers. Quote nothing you cannot see in the sheets, and do not decide which value is right.\n\n{sheets}"
)


class FactError(RuntimeError):
    """A fact sheet or review could not be produced; the message is fit to show the user."""


def ask_text(prompt: str, label: str, max_tokens: int = 8000, say: Callable[[str], None] | None = None) -> str:
    """One model call on the scanning model (BOARD_OCR_MODEL, a Sonnet by default). Raises FactError."""
    from app.agents import client as C, settings as cfg
    try:
        resp = C.call_with_retry(lambda: C.get_client().messages.create(
            model=cfg.OCR_MODEL, max_tokens=max_tokens, messages=[{"role": "user", "content": [{"type": "text", "text": prompt}]}]), label, None, say)
    except Exception as e:  # noqa: BLE001 - reported, and the run carries on without this sheet
        sdk = getattr(C, "anthropic", None)
        if sdk is not None and isinstance(e, sdk.AnthropicError): raise FactError(str(C.api_error(e, label))) from e
        raise FactError(f"{type(e).__name__}: {e}") from e
    return "".join(getattr(b, "text", "") for b in resp.content if getattr(b, "type", "") == "text").strip()


def tokens(text: str) -> int:
    return int(len(text or "") / CHARS_PER_TOKEN)


def sections(text: str, size: int = SECTION_CHARS) -> list[str]:
    """Split at line breaks into sections of about `size` characters."""
    out: list[str] = []; cur: list[str] = []; n = 0
    for line in text.split("\n"):
        while len(line) > size:
            if cur: out.append("\n".join(cur)); cur = []; n = 0
            out.append(line[:size]); line = line[size:]
        if n + len(line) > size and cur: out.append("\n".join(cur)); cur = []; n = 0
        cur.append(line); n += len(line) + 1
    if cur: out.append("\n".join(cur))
    return out


def build_sheets(docs: list[dict], progress: Progress | None = None, ask: Callable[..., str] | None = None,
                 on_sheet: Callable[[dict], None] | None = None) -> list[str]:
    """Give each long document without one a `facts` sheet (in place), smaller documents first, up to MAX_INPUT_TOKENS of text. Each sheet
    is handed to `on_sheet` the moment it is complete, so a stall or a restart loses nothing already done. Returns notes for the job
    log: a document whose sheet fails, or is over the cap, is noted and left to search alone."""
    ask = ask or (lambda prompt, label: ask_text(prompt, label, say=progress)); notes: list[str] = []
    todo = sorted((d for d in docs if not d.get("facts") and tokens(d.get("text")) >= MIN_TOKENS), key=lambda d: len(d["text"]))
    if not ENABLED or not todo: return notes
    chosen: list[dict] = []; used = 0
    for d in todo:
        if used + tokens(d["text"]) > MAX_INPUT_TOKENS: notes.append(f"{d['name']}: no fact sheet (over the {MAX_INPUT_TOKENS // 1000}k-token limit for one run); it can still be searched"); continue
        chosen.append(d); used += tokens(d["text"])
    parts_of = {id(d): sections(d["text"]) for d in chosen}
    jobs = [(d, i, len(parts_of[id(d)]), p) for d in chosen for i, p in enumerate(parts_of[id(d)], 1)]
    got: dict[int, dict[int, str]] = {id(d): {} for d in chosen}; bad: dict[int, str] = {}; finished = [0]

    def run(j):
        d, i, n, part = j
        try: return j, ask(SHEET_PROMPT.format(i=i, n=n, name=d["name"], text=part), f"fact sheet for {d['name']}"), ""
        except FactError as e: return j, None, str(e)

    if progress: progress(f"Extracting key facts from {len(chosen)} document(s), {len(jobs)} sections, about {used // 1000}k tokens")
    with ThreadPoolExecutor(max_workers=min(PARALLEL, len(jobs) or 1)) as pool:
        for fut in as_completed([pool.submit(run, j) for j in jobs]):
            (d, i, n, _), out, err = fut.result()
            if out is None: bad.setdefault(id(d), err)
            else: got[id(d)][i] = out
            if len(got[id(d)]) == n and id(d) not in bad:  # the last section of this document: its sheet is complete
                d["facts"] = "\n".join(got[id(d)][k] for k in sorted(got[id(d)]) if got[id(d)][k])
                if on_sheet: on_sheet(d)
            finished[0] += 1
            if progress and (finished[0] % 3 == 0 or finished[0] == len(jobs)):
                progress(f"Extracting key facts: {finished[0]} of {len(jobs)} sections done, {sum(1 for x in chosen if x.get('facts'))} of {len(chosen)} documents complete")
    for d in chosen:
        if id(d) in bad: notes.append(f"{d['name']}: no fact sheet ({bad[id(d)][:160]}); it can still be searched")
    return notes


def review(subject: str, docs: list[dict], progress: Progress | None = None, ask: Callable[..., str] | None = None) -> str:
    """The cross-document review for one subject, from the documents' fact sheets (batched when they are many). '' when there is
    nothing to compare."""
    ask = ask or (lambda prompt, label: ask_text(prompt, label, say=progress))
    sheets = [f'<fact_sheet file="{d["name"]}">\n{d["facts"]}\n</fact_sheet>' for d in docs if d.get("facts")]
    if len(sheets) < 2 or not ENABLED: return ""
    batches: list[list[str]] = [[]]; used = 0
    for s in sheets:
        if used + tokens(s) > REVIEW_BATCH_TOKENS and batches[-1]: batches.append([]); used = 0
        batches[-1].append(s); used += tokens(s)
    if progress: progress(f"Cross-checking the documents supplied on {subject}")
    try:
        parts = [ask(REVIEW_PROMPT.format(n=len(b), subject=subject, sheets="\n".join(b)), f"review of {subject}'s documents") for b in batches]
        if len(parts) > 1:  # many documents: compare the batch reviews too
            parts = [ask(REVIEW_PROMPT.format(n=len(parts), subject=subject, sheets="\n".join(f"<fact_sheet file='batch {k + 1}'>\n{p}\n</fact_sheet>" for k, p in enumerate(parts))),
                         f"review of {subject}'s documents")]
    except FactError as e:
        log.warning("review_failed", subject=subject, error=str(e)); return ""
    return parts[0]


def prepare(docs: list[dict], subject_names: list[str], progress: Progress | None = None, ask: Callable[..., str] | None = None,
            on_sheet: Callable[[dict], None] | None = None) -> tuple[dict[int, str], list[str]]:
    """Sheets for every long document, then a review per subject. Returns ({subject index: review}, notes)."""
    notes = build_sheets(docs, progress, ask, on_sheet); findings: dict[int, str] = {}
    for i, name in enumerate(subject_names):
        mine = [d for d in docs if int(d.get("subject") or 0) == i]
        if (text := review(name, mine, progress, ask)): findings[i] = text
    return findings, notes
