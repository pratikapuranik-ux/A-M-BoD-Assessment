"""Text extraction from uploaded board documents: .pdf, .docx, .xlsx, .pptx, web pages and plain text read directly; scanned PDFs
and images are marked for transcription (services/ocr.py).

Port of the legacy server/extract.py onto pypdf + pdfplumber, python-docx and openpyxl.
Names, limits and the PDF page/byte budget logic are unchanged.
"""
from __future__ import annotations

import base64
import io
import os

TEXT_EXT = {".txt", ".md", ".csv", ".tsv", ".json"}
IMAGE_EXT = {".png", ".jpg", ".jpeg", ".webp", ".gif", ".bmp", ".tif", ".tiff"}  # read by transcription, like a scanned page
HTML_EXT = {".html", ".htm"}
MIME_EXT = {"application/pdf": ".pdf", "application/vnd.openxmlformats-officedocument.wordprocessingml.document": ".docx",
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": ".xlsx", "text/plain": ".txt", "text/markdown": ".md", "text/csv": ".csv",
            "application/vnd.openxmlformats-officedocument.presentationml.presentation": ".pptx", "text/html": ".html", "image/png": ".png",
            "image/jpeg": ".jpg", "image/webp": ".webp", "image/gif": ".gif", "image/bmp": ".bmp", "image/tiff": ".tiff"}
SUPPORTED = sorted(TEXT_EXT | IMAGE_EXT | HTML_EXT | {".pdf", ".docx", ".xlsx", ".pptx"})
MAX_FILE = 100 * 1024 * 1024  # any one uploaded file
MAX_ZIP = 500 * 1024 * 1024  # a .zip of documents (its contents are still limited to MAX_FILE each and MAX_UPLOAD in all)
MAX_ZIP_MEMBERS = 3000  # files inside one .zip
MAX_UPLOAD = 2 * 1024 * 1024 * 1024  # all documents of one request together (files are sent one at a time, so the browser is not the limit)
# Claude reads a PDF as pages only within one request's limits (about 32 MB encoded, 100 pages);
# PDFs beyond this budget are sent as their extracted text instead.
PDF_INLINE_BYTES, PDF_INLINE_PAGES = 18 * 1024 * 1024, 100


class ExtractError(ValueError):
    pass


def _docx(data: bytes) -> str:
    from docx import Document
    from docx.table import Table
    from docx.text.paragraph import Paragraph
    doc = Document(io.BytesIO(data)); out = []
    for el in doc.element.body.iterchildren():  # body order, so tables stay next to their headings
        tag = el.tag.rsplit("}", 1)[-1]
        if tag == "p":
            t = Paragraph(el, doc).text.strip()
            if t: out.append(t)
        elif tag == "tbl":
            for row in Table(el, doc).rows:
                cells, seen = [], set()
                for c in row.cells:  # merged cells repeat; keep each once
                    if id(c._tc) in seen: continue
                    seen.add(id(c._tc)); cells.append(c.text.strip().replace("\n", " "))
                if any(cells): out.append(" | ".join(cells))
    return "\n".join(out)


def _pdf_plumber_pages(data: bytes, wanted: set[int]) -> dict[int, str]:
    """pdfplumber fallback for pages pypdf could not read text from (1-based page numbers)."""
    if not wanted: return {}
    try:
        import pdfplumber
        out: dict[int, str] = {}
        with pdfplumber.open(io.BytesIO(data)) as pdf:
            for k in sorted(wanted):
                if k <= len(pdf.pages): out[k] = (pdf.pages[k - 1].extract_text() or "").strip()
        return out
    except Exception:  # noqa: BLE001 - fallback only; pypdf result stands
        return {}


def _pdf_pdfium(data: bytes) -> list[str]:
    """Text of every page with pdfium: slower to set up than pypdf but it does not trip over very large or odd PDFs."""
    import pypdfium2 as pdfium
    pdf = pdfium.PdfDocument(data)
    try:
        out: list[str] = []
        for i in range(len(pdf)):
            page = pdf[i]
            try:
                tp = page.get_textpage()
                try: out.append(tp.get_text_range().replace("\r\n", "\n").replace("\r", "\n").strip())
                finally: tp.close()
            except Exception:  # noqa: BLE001
                out.append("")
            finally:
                page.close()
        return out
    finally:
        pdf.close()


def _pdf(data: bytes, name: str) -> tuple[int, str]:
    texts: list[str | None] | None = None; first: Exception | None = None
    try:
        from pypdf import PdfReader
        r = PdfReader(io.BytesIO(data)); texts = []
        for p in r.pages:
            try: texts.append((p.extract_text() or "").strip())
            except Exception:  # noqa: BLE001
                texts.append(None)  # this page: use the other reader
    except Exception as ex:  # noqa: BLE001 - e.g. pypdf's LimitReachedError on a very large or unusual file
        texts, first = None, ex
    if texts is None or any(t is None for t in texts):
        try: alt = _pdf_pdfium(data)
        except Exception as ex:  # noqa: BLE001
            alt = None; first = first or ex
        if texts is None:
            if alt is None: raise first or ExtractError(f"{name}: could not be read")
            texts = list(alt)
        else:
            texts = [t if t is not None else (alt[k] if alt and k < len(alt) else "") for k, t in enumerate(texts)]
    empty = {k for k, t in enumerate(texts, 1) if not t}
    # Empty pages are usually charts or scans, which the slower reader cannot read either: retry them only when most of the
    # document came back empty (a font problem), and for a bounded number of pages, so a long report does not take minutes.
    empty = set(sorted(empty)[:40]) if len(empty) * 10 > len(texts) * 6 else set()
    for k, t in _pdf_plumber_pages(data, empty).items(): texts[k - 1] = t
    return len(texts), "\n\n".join(f"[page {k}]\n{t}" for k, t in enumerate(texts, 1))


def _xlsx_xml(data: bytes) -> str:
    """Cell values read straight from the workbook's XML: for files openpyxl cannot open (odd styles, unusual extensions)."""
    import zipfile
    from xml.etree import ElementTree as ET
    M = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
    R = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}"
    out: list[str] = []
    with zipfile.ZipFile(io.BytesIO(data)) as z:
        names = set(z.namelist())
        shared = ["".join(t.text or "" for t in si.iter(M + "t")) for si in ET.fromstring(z.read("xl/sharedStrings.xml")).iter(M + "si")] if "xl/sharedStrings.xml" in names else []
        rels = {r.get("Id"): r.get("Target") or "" for r in ET.fromstring(z.read("xl/_rels/workbook.xml.rels"))} if "xl/_rels/workbook.xml.rels" in names else {}
        for sh in ET.fromstring(z.read("xl/workbook.xml")).iter(M + "sheet"):
            target = rels.get(sh.get(R + "id"), "").lstrip("/")
            path = target if target.startswith("xl/") else "xl/" + target
            if path not in names: continue
            out.append(f"[sheet {sh.get('name')}]")
            for row in ET.fromstring(z.read(path)).iter(M + "row"):
                vals = []
                for c in row.iter(M + "c"):
                    v = c.find(M + "v"); t = c.get("t")
                    if t == "s" and v is not None and (v.text or "").isdigit(): val = shared[int(v.text)] if int(v.text) < len(shared) else ""
                    elif t == "inlineStr": val = "".join(x.text or "" for x in c.iter(M + "t"))
                    else: val = (v.text or "") if v is not None else ""
                    vals.append(val)
                if any(vals): out.append(" | ".join(vals))
    return "\n".join(out)


def _xlsx(data: bytes) -> str:
    try:
        from openpyxl import load_workbook
        wb = load_workbook(io.BytesIO(data), read_only=True, data_only=True); out = []
        for ws in wb.worksheets:
            out.append(f"[sheet {ws.title}]")
            for row in ws.iter_rows(values_only=True):
                vals = ["" if v is None else str(v) for v in row]
                if any(vals): out.append(" | ".join(vals))
        return "\n".join(out)
    except Exception:  # noqa: BLE001 - openpyxl is strict about styles and metadata: the values are all we need
        return _xlsx_xml(data)


def _pptx(data: bytes) -> str:
    """Slide and speaker-note text of a .pptx (a zip of XML), in slide order."""
    import re, zipfile
    from xml.etree import ElementTree as ET
    ns = "{http://schemas.openxmlformats.org/drawingml/2006/main}"
    out = []
    with zipfile.ZipFile(io.BytesIO(data)) as z:
        def num(n): return int(re.search(r"(\d+)\.xml$", n).group(1))
        slides = sorted((n for n in z.namelist() if re.fullmatch(r"ppt/slides/slide\d+\.xml", n)), key=num)
        notes = {num(n): n for n in z.namelist() if re.fullmatch(r"ppt/notesSlides/notesSlide\d+\.xml", n)}
        for k, n in enumerate(slides, 1):
            paras = ["".join(t.text or "" for t in p.iter(ns + "t")).strip() for p in ET.fromstring(z.read(n)).iter(ns + "p")]
            text = "\n".join(p for p in paras if p)
            note = notes.get(num(n))
            if note:
                nt = "\n".join(p for p in ("".join(t.text or "" for t in q.iter(ns + "t")).strip() for q in ET.fromstring(z.read(note)).iter(ns + "p")) if p)
                if nt: text += "\n[speaker notes] " + nt
            if text: out.append(f"[slide {k}]\n{text}")
    return "\n\n".join(out)


def _html(data: bytes) -> str:
    import html as H, re
    s = _text(data)
    s = re.sub(r"(?is)<(script|style|noscript|svg)\b.*?</\1>", " ", s)
    s = re.sub(r"(?i)<br\s*/?>|</(p|div|li|tr|h[1-6]|table|section)>", "\n", s)
    s = re.sub(r"(?s)<[^>]+>", " ", s)
    return "\n".join(re.sub(r"[ \t]+", " ", ln).strip() for ln in H.unescape(s).splitlines() if ln.strip())


def _text(data: bytes) -> str:
    for enc in ("utf-8-sig", "cp1252", "latin-1"):
        try: return data.decode(enc)
        except UnicodeDecodeError: continue
    return data.decode("utf-8", "replace")


def ext_of(name: str, mime: str | None = None) -> str:
    e = os.path.splitext(name or "")[1].lower()
    return e if e else MIME_EXT.get((mime or "").split(";")[0].strip().lower(), "")


def extract(name: str, data: bytes, slot: int = 0, mime: str | None = None) -> dict:
    """-> {name, slot, text, pdf_b64|None, pages, size}. Raises ExtractError for unsupported or unreadable files."""
    e = ext_of(name, mime); pages = 0
    if len(data) > MAX_FILE: raise ExtractError(f"{name}: {len(data) / 2**20:.0f} MB; the limit is {MAX_FILE // 2**20} MB per file")
    try:
        if e == ".docx": text = _docx(data)
        elif e == ".pdf": pages, text = _pdf(data, name)
        elif e == ".xlsx": text = _xlsx(data)
        elif e == ".pptx": text = _pptx(data)
        elif e in HTML_EXT: text = _html(data)
        elif e in IMAGE_EXT:
            from app.services import ocr
            return {"name": name, "slot": int(slot), "text": "", "pdf_b64": None, "pdf_big": False, "pages": 1, "size": len(data), "needs_ocr": True, "_image": ocr.prepare_image(data)}
        elif e in TEXT_EXT: text = _text(data)
        else: raise ExtractError(f"{name}: unsupported file type (supported: {', '.join(SUPPORTED)})")
    except ExtractError: raise
    except Exception as ex:  # noqa: BLE001
        raise ExtractError(f"{name}: could not be read ({type(ex).__name__}: {ex})") from ex
    if e != ".pdf" and not text.strip(): raise ExtractError(f"no readable text in {name}; export it as PDF or text")
    inline = e == ".pdf" and len(data) <= PDF_INLINE_BYTES  # a PDF over the page budget is never sent as pages: do not hold a base64 copy
    out = {"name": name, "slot": int(slot), "text": text.strip(), "pdf_b64": base64.b64encode(data).decode("ascii") if inline else None,
           "pdf_big": e == ".pdf" and not inline, "pages": pages, "size": len(data)}
    if e == ".pdf" and not _has_text(out["text"]): out["_raw"] = data  # a scan: keep the bytes in case it has to be transcribed
    return out


def _has_text(text: str) -> bool:
    return bool("".join(l for l in (text or "").splitlines() if not l.startswith("[page ")).strip())


def fit_pdfs(docs: list[dict]) -> list[dict]:
    """Keep PDFs as pages while they fit one request, smallest first; send the rest as text. A scanned PDF with no text that does
    not fit is marked needs_ocr: services/ocr.py turns its pages into text."""
    used_b = used_p = 0
    for d in sorted((d for d in docs if d.get("pdf_b64") or d.get("pdf_big")), key=lambda d: d["size"]):
        if used_b + d["size"] <= PDF_INLINE_BYTES and used_p + d["pages"] <= PDF_INLINE_PAGES:
            used_b += d["size"]; used_p += d["pages"]; d.pop("_raw", None); continue
        d["pdf_b64"] = None
        if not _has_text(d["text"]) and d.get("_raw") is not None: d["needs_ocr"] = True  # keeps _raw for the transcription
        else: d.pop("_raw", None)
    return docs


def extract_b64(doc: dict) -> dict:
    """API document {slot, name, mime, data_b64} -> extract()."""
    try: data = base64.b64decode(doc.get("data_b64") or "", validate=False)
    except Exception as ex: raise ExtractError(f"{doc.get('name')}: data_b64 is not valid base64") from ex
    if not data: raise ExtractError(f"{doc.get('name') or 'document'}: empty file")
    return extract(doc.get("name") or "document", data, int(doc.get("slot") or 0), doc.get("mime"))
