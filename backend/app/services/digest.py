"""Fit the uploaded documents into what one Claude request can hold.

Everything provided goes into the research request, and a request cannot exceed about a million tokens (the research steps also
need room for their web results). When the documents are over the budget, PDFs read as pages are sent as their text instead (cheaper),
and then the largest documents are condensed section by section by a model that keeps every figure, date, name and quotation and
drops boilerplate. Runs inside the job, with progress.
"""
from __future__ import annotations

import os
from concurrent.futures import ThreadPoolExecutor
from typing import Callable

from app.log import get_logger

log = get_logger(__name__)
Progress = Callable[[str], None]

BUDGET = max(50_000, int(os.environ.get("BOARD_DOC_TOKEN_BUDGET") or 500_000))  # tokens of provided documents per request
CHARS_PER_TOKEN = 3.2  # conservative: numbers and tables cost more tokens than prose
TOKENS_PER_PDF_PAGE = 3000  # a PDF sent as pages costs its text plus the page images
CHUNK_CHARS = 180_000  # one section sent for condensing (about 56k tokens)
PARALLEL = 6
SMALL = 30_000  # tokens: a document at most this big is never condensed

PROMPT = (
    "Below is one section ({i} of {n}) of the document \"{name}\", supplied by an advisory team assessing this company's board. "
    "Condense it to about a seventh of its length for a reader who will use it as evidence on governance, strategy, capital allocation, "
    "risk, performance and the board's own decisions. Keep every figure with its unit and period, every date, name, target, commitment "
    "and decision exactly as written, and keep short direct quotations verbatim. Keep table rows that carry numbers, on one line with "
    "' | ' between columns. Drop legal boilerplate, repeated headers and footers, tables of contents and filler. Keep the [page N] "
    "markers. Do not interpret, add or correct anything, and write no commentary of your own.\n\n<section>\n{text}\n</section>"
)


class DigestError(RuntimeError):
    """The documents cannot be fitted; the message is fit to show the user."""


def tokens(d: dict) -> int:
    """Rough token cost of one document as it will be sent."""
    if d.get("pdf_b64"): return int((d.get("pages") or 1) * TOKENS_PER_PDF_PAGE)
    return int(len(d.get("text") or "") / CHARS_PER_TOKEN)


def total(docs: list[dict]) -> int:
    return sum(tokens(d) for d in docs)


def _ask(text: str, name: str, i: int, n: int, label: str) -> str:
    from app.agents import client as C, settings as cfg
    content = [{"type": "text", "text": PROMPT.format(i=i, n=n, name=name, text=text)}]
    try:
        resp = C.call_with_retry(lambda: C.get_client().messages.create(model=cfg.OCR_MODEL, max_tokens=12000, messages=[{"role": "user", "content": content}]), label)
    except Exception as e:  # noqa: BLE001 - reported against the file
        sdk = getattr(C, "anthropic", None)
        if sdk is not None and isinstance(e, sdk.AnthropicError): raise DigestError(str(C.api_error(e, label))) from e
        raise DigestError(f"{type(e).__name__}: {e}") from e
    return "".join(getattr(b, "text", "") for b in resp.content if getattr(b, "type", "") == "text").strip()


def _sections(text: str) -> list[str]:
    """Split at paragraph breaks into sections of about CHUNK_CHARS."""
    out: list[str] = []; cur: list[str] = []; size = 0
    for para in text.split("\n"):
        while len(para) > CHUNK_CHARS:  # a single huge line (e.g. an unbroken table) is cut
            if cur: out.append("\n".join(cur)); cur = []; size = 0
            out.append(para[:CHUNK_CHARS]); para = para[CHUNK_CHARS:]
        if size + len(para) > CHUNK_CHARS and cur: out.append("\n".join(cur)); cur = []; size = 0
        cur.append(para); size += len(para) + 1
    if cur: out.append("\n".join(cur))
    return out


def condense(d: dict, progress: Progress | None = None) -> None:
    name = d["name"]; parts = _sections(d["text"]); n = len(parts)
    if progress: progress(f"Condensing {name} ({n} section{'s' if n != 1 else ''})")
    with ThreadPoolExecutor(max_workers=min(PARALLEL, n)) as pool:
        got = list(pool.map(lambda ip: _ask(ip[1], name, ip[0], n, f"condensing {name}"), enumerate(parts, 1)))
    text = "\n\n".join(g for g in got if g).strip()
    if not text: raise DigestError(f"{name}: nothing came back when condensing it")
    before = tokens(d)
    d.update(text=f"[condensed extract of {name}: about {before // 1000}k tokens reduced to about {int(len(text) / CHARS_PER_TOKEN) // 1000}k]\n{text}",
             pdf_b64=None, condensed=True)


def fit(docs: list[dict], progress: Progress | None = None, budget: int | None = None) -> list[str]:
    """Bring the documents under the budget (in place). Returns notes for the job log; raises DigestError if it cannot be done."""
    budget = budget or BUDGET; notes: list[str] = []
    used = total(docs)
    if used <= budget: return notes
    # 1. PDFs that have a text layer go as text: it costs a fraction of the same pages
    for d in sorted(docs, key=tokens, reverse=True):
        if used <= budget: break
        if d.get("pdf_b64") and (d.get("text") or "").strip():
            d["pdf_b64"] = None; used = total(docs)
    if used <= budget:
        notes.append(f"The documents were over the size one request can hold, so PDFs were read as text instead of page images ({used // 1000}k tokens).")
        return notes
    # 2. condense the largest documents, largest first, until it fits
    start = used; done: list[str] = []
    for d in sorted((x for x in docs if not x.get("pdf_b64") and tokens(x) > SMALL), key=tokens, reverse=True):
        if used <= budget: break
        condense(d, progress); done.append(d["name"]); used = total(docs)
    if used > budget:
        big = ", ".join(f"{d['name']} (~{tokens(d) // 1000}k)" for d in sorted(docs, key=tokens, reverse=True)[:5])
        raise DigestError(f"the documents come to about {used // 1000}k tokens even after condensing, and one request holds about {budget // 1000}k; "
                          f"remove some of them (largest: {big}) or raise BOARD_DOC_TOKEN_BUDGET")
    notes.append(f"The documents were about {start // 1000}k tokens, over what one request can hold ({budget // 1000}k), so {len(done)} of the largest were condensed "
                 f"(figures, dates, names and quotations kept; boilerplate dropped): " + "; ".join(done))
    return notes
