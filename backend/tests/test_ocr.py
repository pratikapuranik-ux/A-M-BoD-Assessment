"""Scanned PDFs and images are turned into text by transcription (the model call is replaced here)."""
import base64
import io

import pytest
from pypdf import PdfWriter
from PIL import Image

from app.api import uploads as U
from app.services import documents as X, ocr


def blank_pdf(pages):
    w = PdfWriter()
    for _ in range(pages): w.add_blank_page(300, 400)
    b = io.BytesIO(); w.write(b); return b.getvalue()


def scan(pages):
    return {"name": "scan.pdf", "pages": pages, "needs_ocr": True, "_raw": blank_pdf(pages), "text": "", "pdf_b64": None}


@pytest.fixture
def asked(monkeypatch):
    calls = []
    def ask(images, name, first, label):
        calls.append((len(images), first)); return "\n".join(f"[page {first + i}] text" for i in range(len(images)))
    monkeypatch.setattr(ocr, "_ask", ask)
    return calls


def test_scan_is_transcribed_in_batches(asked):
    d = scan(20); seen = []
    probs, notes = ocr.transcribe_pending([d], seen.append)
    assert asked == [(8, 1), (8, 9), (4, 17)] and not probs and not notes
    assert d["text"].startswith("[page 1] text") and "[page 20] text" in d["text"] and d["transcribed"] and not d["needs_ocr"] and "_raw" not in d
    assert any("pages 9-16 of 20 in scan.pdf" in m for m in seen)


def test_page_limit_failures_and_empty_results(asked, monkeypatch):
    monkeypatch.setattr(ocr, "MAX_PAGES", 10)
    d = scan(20); probs, notes = ocr.transcribe_pending([d])
    assert asked == [(8, 1), (2, 9)] and not probs and "first 10 of 20 scanned pages" in notes[0]
    def no_key(*a, **k): raise ocr.OcrError("no key")
    monkeypatch.setattr(ocr, "_ask", no_key)
    probs, _ = ocr.transcribe_pending([scan(3)])
    assert probs == ["scan.pdf: a scanned PDF (3 pages) with no readable text could not be transcribed (no key)"]
    monkeypatch.setattr(ocr, "_ask", lambda *a, **k: "")
    probs, _ = ocr.transcribe_pending([scan(2)]); assert "no text could be made out" in probs[0]


def test_image_files_are_read_through_the_same_path(monkeypatch):
    png = io.BytesIO(); Image.new("RGB", (80, 60), "white").save(png, "PNG")
    monkeypatch.setattr(ocr, "_ask", lambda images, name, first, label: "Revenue 12")
    out, probs = U.extract_documents([{"name": "table.png", "data_b64": base64.b64encode(png.getvalue()).decode()}], progress=lambda m: None)
    assert not probs and out[0]["text"] == "Revenue 12" and "_image" not in out[0] and "_raw" not in out[0]


def test_oversize_scan_beside_other_pdfs_is_read_not_refused(monkeypatch):
    """The reported case: a small scan that no longer fits the shared 100-page budget used to be refused."""
    from reportlab.pdfgen import canvas
    b = io.BytesIO(); c = canvas.Canvas(b)
    for k in range(100): c.drawString(72, 750, f"Report page {k}"); c.showPage()
    c.save()
    monkeypatch.setattr(ocr, "_ask", lambda images, name, first, label: "[page 1] scanned text")
    import random
    rnd = random.Random(1); sb = io.BytesIO(); sc = canvas.Canvas(sb)  # 8 pages of drawn shapes and no text layer, bigger in bytes than the report
    for _ in range(8):
        for _ in range(2500): sc.rect(rnd.random() * 500, rnd.random() * 700, rnd.random() * 40, rnd.random() * 40, fill=rnd.random() > 0.5)
        sc.showPage()
    sc.save(); assert len(sb.getvalue()) > len(b.getvalue())
    docs = [{"name": "report.pdf", "data_b64": base64.b64encode(b.getvalue()).decode()},
            {"name": "ExxonMobil/2Q26 Supplement Data.pdf", "data_b64": base64.b64encode(sb.getvalue()).decode()}]
    out, probs = U.extract_documents(docs)
    by = {d["name"]: d for d in out}
    assert not probs and by["report.pdf"]["pdf_b64"] and by["ExxonMobil/2Q26 Supplement Data.pdf"]["text"] == "[page 1] scanned text"
