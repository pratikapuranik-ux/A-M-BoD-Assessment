"""Read scanned pages and images with Claude.

A scanned PDF has no text layer, and Claude can only take about 100 PDF pages (and ~32 MB) as pages in one request, so a scan that
does not fit beside the other PDFs, and every image file, is turned into text here: each page is rendered to a JPEG and the model
transcribes it. The text then goes into the research like any other document, with no page limit. Runs inside the job, with progress.
"""
from __future__ import annotations

import base64
import io
import os
from typing import Callable

from app.log import get_logger

log = get_logger(__name__)
Progress = Callable[[str], None]

PAGES_PER_CALL = 8  # pages sent in one request
MAX_SIDE = 1600  # longest side of a rendered page, in pixels (enough to read small print)
MAX_PAGES = max(1, int(os.environ.get("BOARD_OCR_MAX_PAGES") or 400))  # scanned pages transcribed per request, all documents together

PROMPT = (
    "These images are consecutive pages of a scanned document named \"{name}\" (page {first} to page {last}). Transcribe the text of "
    "each page exactly as written, in reading order. Keep every number, unit, date and name as printed, and keep table rows on one line "
    "with ' | ' between columns. Do not summarise, interpret, correct or add commentary. Where a page has a chart or picture, write "
    "[figure: what it shows, with any labelled values] in its place. Start each page with a line '[page N]' using the page numbers given."
)


class OcrError(RuntimeError):
    """A scan or image could not be transcribed; the message is fit to show the user."""


def render_pdf_pages(raw: bytes, first: int, count: int) -> list[bytes]:
    """JPEGs of pages first..first+count-1 (0-based) of a PDF, scaled so the longest side is about MAX_SIDE pixels."""
    import pypdfium2 as pdfium
    pdf = pdfium.PdfDocument(raw)
    try:
        out: list[bytes] = []
        for i in range(first, min(first + count, len(pdf))):
            page = pdf[i]
            try:
                w, h = page.get_size()
                img = page.render(scale=max(0.5, min(3.0, MAX_SIDE / max(w, h, 1)))).to_pil().convert("RGB")
            finally:
                page.close()
            buf = io.BytesIO(); img.save(buf, "JPEG", quality=72); out.append(buf.getvalue())
        return out
    finally:
        pdf.close()


def prepare_image(data: bytes) -> bytes:
    """Any image file -> a JPEG the model accepts (at most ~2000 px a side, no transparency)."""
    from PIL import Image
    im = Image.open(io.BytesIO(data)); im.load()
    if im.mode in ("RGBA", "LA", "P"):
        im = im.convert("RGBA"); bg = Image.new("RGB", im.size, "white"); bg.paste(im, mask=im.split()[-1]); im = bg
    else:
        im = im.convert("RGB")
    im.thumbnail((2000, 2000))
    buf = io.BytesIO(); im.save(buf, "JPEG", quality=80)
    return buf.getvalue()


def _ask(images: list[bytes], name: str, first_page: int, label: str) -> str:
    """One model call: transcribe these page images. Raises OcrError with a user-facing reason."""
    from app.agents import client as C, settings as cfg
    content: list[dict] = [{"type": "text", "text": PROMPT.format(name=name, first=first_page, last=first_page + len(images) - 1)}]
    for data in images:
        content.append({"type": "image", "source": {"type": "base64", "media_type": "image/jpeg", "data": base64.b64encode(data).decode("ascii")}})
    try:
        resp = C.call_with_retry(lambda: C.get_client().messages.create(model=cfg.OCR_MODEL, max_tokens=16000, messages=[{"role": "user", "content": content}]), label)
    except Exception as e:  # noqa: BLE001 - any failure is reported against the file, not raised through the job
        sdk = getattr(C, "anthropic", None)
        if sdk is not None and isinstance(e, sdk.AnthropicError): raise OcrError(str(C.api_error(e, label))) from e
        raise OcrError(f"{type(e).__name__}: {e}") from e
    return "".join(getattr(b, "text", "") for b in resp.content if getattr(b, "type", "") == "text").strip()


def transcribe_pending(docs: list[dict], progress: Progress | None = None) -> tuple[list[str], list[str]]:
    """Fill in `text` for every document marked needs_ocr. Returns (problems, notes); a file that cannot be read is a problem
    naming the reason, and pages beyond MAX_PAGES are left out and noted."""
    problems: list[str] = []; notes: list[str] = []; budget = MAX_PAGES
    for d in docs:
        if not d.get("needs_ocr"): continue
        name = d["name"]; raw = d.pop("_raw", None); image = d.pop("_image", None)
        kind = "scanned PDF" if raw is not None else "image"
        try:
            if image is not None:
                if progress: progress(f"Reading the image {name}")
                texts = [_ask([image], name, 1, f"reading {name}")]; done = total = 1
            else:
                import pypdfium2 as pdfium
                pdf = pdfium.PdfDocument(raw)
                try: total = len(pdf)
                finally: pdf.close()
                done = min(total, budget); texts = []; at = 0
                while at < done:
                    n = min(PAGES_PER_CALL, done - at)
                    if progress: progress(f"Reading scanned pages {at + 1}-{at + n} of {total} in {name}")
                    texts.append(_ask(render_pdf_pages(raw, at, n), name, at + 1, f"reading {name}"))
                    at += n
            budget -= done
            text = "\n\n".join(t for t in texts if t).strip()
            if not text: raise OcrError("no text could be made out on the pages")
            d.update(text=text, pdf_b64=None, pdf_big=False, needs_ocr=False, transcribed=True)
            if done < total: notes.append(f"{name}: read the first {done} of {total} scanned pages (the limit is {MAX_PAGES} scanned pages per request)")
        except Exception as e:  # noqa: BLE001
            label = f"a {kind} ({d.get('pages') or 1} page{'s' if (d.get('pages') or 1) != 1 else ''})" if kind == "scanned PDF" else "an image"
            problems.append(f"{name}: {label} with no readable text could not be transcribed ({e})")
    return problems, notes
