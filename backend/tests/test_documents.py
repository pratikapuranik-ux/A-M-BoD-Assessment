"""Text extraction: docx, pdf, xlsx, text, limits and the PDF page budget."""
import base64
import io

import pytest
from docx import Document
from openpyxl import Workbook
from reportlab.pdfgen import canvas

from app.services import documents as X


def make_docx():
    d = Document(); d.add_paragraph("Board charter"); t = d.add_table(rows=1, cols=2); t.rows[0].cells[0].text = "Quorum"; t.rows[0].cells[1].text = "Five"
    b = io.BytesIO(); d.save(b); return b.getvalue()


def make_pdf(pages=2):
    b = io.BytesIO(); c = canvas.Canvas(b)
    for k in range(pages): c.drawString(72, 750, f"Minutes page {k + 1}"); c.showPage()
    c.save(); return b.getvalue()


def make_xlsx():
    wb = Workbook(); ws = wb.active; ws.title = "KPI"; ws.append(["metric", 4.5]); b = io.BytesIO(); wb.save(b); return b.getvalue()


def test_docx_keeps_table_order():
    r = X.extract("c.docx", make_docx(), slot=3)
    assert r["text"] == "Board charter\nQuorum | Five" and r["slot"] == 3 and r["pdf_b64"] is None


def test_pdf_pages_and_b64():
    data = make_pdf(2); r = X.extract("m.pdf", data)
    assert r["pages"] == 2 and "[page 1]\nMinutes page 1" in r["text"] and "[page 2]" in r["text"]
    assert base64.b64decode(r["pdf_b64"]) == data and r["size"] == len(data)


def test_xlsx_and_text_and_mime():
    assert X.extract("k.xlsx", make_xlsx())["text"] == "[sheet KPI]\nmetric | 4.5"
    assert X.extract("n.txt", "café".encode("cp1252"))["text"] == "café"
    assert X.ext_of("noext", "application/pdf; charset=x") == ".pdf" and X.ext_of("A.DOCX") == ".docx"
    assert X.extract("noext", b"hello", mime="text/plain")["text"] == "hello"


def test_errors():
    with pytest.raises(X.ExtractError, match="unsupported"): X.extract("a.exe", b"x")
    with pytest.raises(X.ExtractError, match="no readable text"): X.extract("e.txt", b"   ")
    with pytest.raises(X.ExtractError, match="could not be read"): X.extract("bad.pdf", b"not a pdf")
    with pytest.raises(X.ExtractError, match="100 MB"): X.extract("big.txt", b"x" * (X.MAX_FILE + 1))
    with pytest.raises(X.ExtractError, match="empty"): X.extract_b64({"name": "z.txt", "data_b64": ""})


def test_extract_b64():
    r = X.extract_b64({"name": "d.docx", "slot": "2", "data_b64": base64.b64encode(make_docx()).decode()})
    assert r["slot"] == 2 and "Board charter" in r["text"]


def test_fit_pdfs_budget():
    small = {"name": "s.pdf", "size": 10, "pages": 60, "pdf_b64": "x", "text": "[page 1]\nhello"}
    big = {"name": "b.pdf", "size": 20, "pages": 60, "pdf_b64": "x", "text": "[page 1]\nbody text"}
    X.fit_pdfs([small, big])
    assert small["pdf_b64"] == "x" and big["pdf_b64"] is None  # over 100 pages: sent as text
    scan = {"name": "scan.pdf", "size": 30, "pages": 60, "pdf_b64": "x", "text": "[page 1]\n\n\n[page 2]\n", "_raw": b"%PDF"}
    X.fit_pdfs([dict(small), scan])  # a scan that does not fit is not refused: it is marked for transcription
    assert scan["needs_ocr"] is True and scan["pdf_b64"] is None and scan["_raw"] == b"%PDF"
    fits = {"name": "scan2.pdf", "size": 30, "pages": 10, "pdf_b64": "x", "text": "", "_raw": b"%PDF"}
    X.fit_pdfs([fits]); assert "needs_ocr" not in fits and "_raw" not in fits and fits["pdf_b64"] == "x"  # a scan that fits goes as pages


def test_more_file_types():
    import zipfile
    from PIL import Image
    ns = 'xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main"'
    slide = lambda *lines: f"<p:sld {ns}><p:cSld><p:spTree><p:sp><p:txBody>" + "".join(f"<a:p><a:r><a:t>{t}</a:t></a:r></a:p>" for t in lines) + "</p:txBody></p:sp></p:spTree></p:cSld></p:sld>"
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("ppt/slides/slide2.xml", slide("Liquidity")); z.writestr("ppt/slides/slide1.xml", slide("Capital allocation", "Buybacks paused"))
        z.writestr("ppt/notesSlides/notesSlide1.xml", f"<p:notes {ns}><p:cSld><p:spTree><p:sp><p:txBody><a:p><a:r><a:t>Lead with cash</a:t></a:r></a:p></p:txBody></p:sp></p:spTree></p:cSld></p:notes>")
    r = X.extract("deck.pptx", buf.getvalue())
    assert r["text"] == "[slide 1]\nCapital allocation\nBuybacks paused\n[speaker notes] Lead with cash\n\n[slide 2]\nLiquidity"
    r = X.extract("page.html", b"<html><head><style>p{}</style><script>x=1</script></head><body><h1>Results</h1><p>Cash &amp; liquidity<br>up</p></body></html>")
    assert r["text"] == "Results\nCash & liquidity\nup"
    png = io.BytesIO(); Image.new("RGBA", (60, 40), (255, 255, 255, 0)).save(png, "PNG")
    r = X.extract("scan.png", png.getvalue())  # an image is not read here: it is marked for transcription as a JPEG
    assert r["needs_ocr"] is True and r["text"] == "" and r["pages"] == 1 and r["_image"][:2] == b"\xff\xd8" and r["pdf_b64"] is None
    for n in ("deck.pptx", "scan.png", "scan.TIF", "page.htm"): assert X.ext_of(n) in X.SUPPORTED


def test_a_pdf_pypdf_cannot_open_is_read_with_pdfium(monkeypatch):
    import pypdf
    from reportlab.pdfgen import canvas
    b = io.BytesIO(); c = canvas.Canvas(b); c.drawString(72, 750, "Board met eight times"); c.showPage(); c.drawString(72, 750, "Capex 16 billion"); c.showPage(); c.save()
    def broken(*a, **k): raise pypdf.errors.LimitReachedError("Reached maximum array element count.")
    monkeypatch.setattr(pypdf, "PdfReader", broken)
    r = X.extract("10K.pdf", b.getvalue())
    assert r["pages"] == 2 and "Board met eight times" in r["text"] and "[page 2]" in r["text"] and "Capex 16 billion" in r["text"]


def test_a_workbook_openpyxl_cannot_open_is_read_from_its_xml(monkeypatch):
    import openpyxl
    wb = openpyxl.Workbook(); ws = wb.active; ws.title = "Data"; ws.append(["Metric", "2025"]); ws.append(["Revenue", 12.5]); ws.append(["Note", None])
    ws2 = wb.create_sheet("Second"); ws2.append(["Directors", 11])
    b = io.BytesIO(); wb.save(b)
    def broken(*a, **k): raise TypeError("expected <class 'int'>")
    monkeypatch.setattr(openpyxl, "load_workbook", broken)
    r = X.extract("IAC.xlsx", b.getvalue())
    assert "[sheet Data]" in r["text"] and "Metric | 2025" in r["text"] and "Revenue | 12.5" in r["text"] and "[sheet Second]" in r["text"] and "Directors | 11" in r["text"]


def test_folder_of_a_company_not_in_the_assessment_is_not_used():
    from app.services import subjects as S
    co, peers = {"name": "Chevron", "ticker": "CVX"}, [{"name": "BP", "ticker": "BP"}, {"name": "ExxonMobil", "ticker": "XOM"}]
    paths = ["OutsideIn/Chevron/10K.pdf", "OutsideIn/Chevron/proxy/p.pdf", "OutsideIn/Bp/ar.pdf", "OutsideIn/ExxxonMobil/10k.pdf", "OutsideIn/Shell/ar.pdf", "OutsideIn/loose.pdf"]
    assert S.assign_many(paths, co, peers) == [0, 0, 1, 2, -1, 0]
    assert S.assign_many(["a.pdf", "b.pdf"], co, peers) == [0, 0]  # no folders: all the company's
