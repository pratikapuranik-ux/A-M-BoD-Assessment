"""One/two-page executive summary PDF (reportlab): scores, key findings, actions."""
from __future__ import annotations

import re
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import cm
from reportlab.platypus import KeepTogether, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from app.services.deliverables import (AMBER, BLUE, DIMS, DRAFT, FW, GRADE_FILL, GREY, NAVY, SCORE_FILL, company_of, first_sentence,
                                       grade_delta, lenses_for, peers_of, period_label, stage_of)

_CTRL = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f]")
_EID = re.compile(r"\s*\[(?:[EXBKLN]|SA|IO)\d{2,3}\]")
_SAFE = str.maketrans({"▲": "+", "▼": "-", "▸": ">", "→": "->", "≥": ">=", "≤": "<=", "→": "->", "•": "-", " ": " ", "‑": "-"})


def _t(s) -> str:
    """Plain text safe for reportlab Paragraph markup and the built-in Helvetica font (evidence markers dropped)."""
    s = _EID.sub("", _CTRL.sub("", "" if s is None else str(s))).translate(_SAFE)
    return escape(s.encode("cp1252", "replace").decode("cp1252"))


def _hex(h): return colors.HexColor("#" + h)


def build_pdf_summary(run: dict, out_path: str) -> str:
    """Render the executive summary of a graded run; returns out_path."""
    comp = company_of(run); C = comp.get("computed")
    if not C: raise ValueError("run has not been graded (company.computed is missing)")
    lenses, labels = lenses_for(run); io = stage_of(run) == "inside_out"; last = lenses[-1]
    hist = run.get("history") or []; period = period_label(run); peers = peers_of(run)
    mode = FW["run_modes"].get(run["run"].get("mode"), "")

    base = ParagraphStyle("b", fontName="Helvetica", fontSize=8.8, leading=11.6, textColor=_hex("1A1F2B"))
    small = ParagraphStyle("s", parent=base, fontSize=7.6, leading=9.6, textColor=_hex(GREY))
    kick = ParagraphStyle("k", parent=base, fontName="Helvetica-Bold", fontSize=7.5, textColor=_hex(BLUE), spaceBefore=9, spaceAfter=2)
    h1 = ParagraphStyle("h1", parent=base, fontName="Helvetica-Bold", fontSize=17, leading=21, textColor=_hex(NAVY), spaceAfter=2)
    h2 = ParagraphStyle("h2", parent=base, fontName="Helvetica-Bold", fontSize=10.5, leading=13, textColor=_hex(NAVY), spaceAfter=4)
    bold = ParagraphStyle("bd", parent=base, fontName="Helvetica-Bold", textColor=_hex(NAVY))
    cell = ParagraphStyle("c", parent=base, fontSize=7.8, leading=9.6)
    center = ParagraphStyle("ce", parent=cell, alignment=1)
    bullet = ParagraphStyle("bl", parent=base, leftIndent=10, firstLineIndent=-8, spaceAfter=2)

    def foot(canvas, doc):
        canvas.saveState(); canvas.setFont("Helvetica", 7); canvas.setFillColor(_hex(AMBER))
        canvas.drawString(1.6 * cm, 1.0 * cm, _t(DRAFT)); canvas.setFillColor(_hex(GREY)); canvas.drawRightString(A4[0] - 1.6 * cm, 1.0 * cm, f"Page {doc.page}")
        canvas.setFont("Helvetica-Bold", 7); canvas.drawString(1.6 * cm, A4[1] - 1.1 * cm, "ALVAREZ & MARSAL  |  Day 1 / Day 2 Board Assessment  |  Executive summary"); canvas.restoreState()

    def gcell(g, size=11):
        st = ParagraphStyle("g", parent=center, fontName="Helvetica-Bold", fontSize=size, leading=size + 2, textColor=colors.white)
        return Paragraph(_t(g or "n/a"), st)

    story = [Paragraph("ALVAREZ &amp; MARSAL", ParagraphStyle("br", parent=kick, spaceBefore=0)),
             Paragraph(_t(f"{comp['name']}: Day 1 / Day 2 Board Assessment" + (" (inside-out update)" if io else "")), h1),
             Paragraph(_t(f"{period}  |  run date {run['run'].get('run_date', '')}  |  {mode}" + ("  |  SIMULATED" if run["run"].get("simulated") else "")), small)]
    if run.get("headline"): story += [Spacer(1, 6), Paragraph(_t(run["headline"]), h2)]

    # overall grade tiles
    tiles = []
    for l in lenses:
        o = C["overall"][l]; prev = hist[-1] if hist else None
        pv = None
        if prev:
            po = prev["overall"]; pv = ((po.get("board_io") or po.get("board") or {}) if prev.get("stage") == "inside_out" else (po.get("board") or {})).get("grade")
        dl = grade_delta(o.get("grade"), pv)
        sub = f"{o['dimensions_reported']} of {len(DIMS)} dimensions" + (" - PROVISIONAL" if o.get("provisional") else "") + (f"; prior {pv} ({'+' if dl > 0 else ''}{dl})" if pv and dl is not None else "")
        inner = Table([[gcell(o.get("grade") or "-", 24), [Paragraph(f"<b>{_t(labels[l].upper())}</b>", small), Paragraph(f"<b>{_t(o.get('label', ''))}</b>", base), Paragraph(_t(sub), small)]]],
                      colWidths=[1.6 * cm, None])
        inner.setStyle(TableStyle([("BACKGROUND", (0, 0), (0, 0), _hex(GRADE_FILL.get(o.get("grade")))), ("VALIGN", (0, 0), (-1, -1), "MIDDLE"), ("LEFTPADDING", (1, 0), (1, 0), 8)]))
        tiles.append(inner)
    w = (A4[0] - 3.2 * cm) / len(tiles)
    tt = Table([tiles], colWidths=[w] * len(tiles)); tt.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), _hex("EEF7FD")), ("BOX", (0, 0), (-1, -1), 0.5, _hex("D9D9D9")),
                                                                         ("INNERGRID", (0, 0), (-1, -1), 0.5, _hex("D9D9D9")), ("TOPPADDING", (0, 0), (-1, -1), 6), ("BOTTOMPADDING", (0, 0), (-1, -1), 6)]))
    story += [Spacer(1, 6), tt]
    for l in lenses:
        s = (run.get("overall_summary") or {}).get(l)
        if s: story += [Spacer(1, 4), Paragraph(f"<b>{_t(labels[l])}:</b> {_t(s)}", cell)]

    # scorecard
    hdr = [Paragraph("<b>Dimension</b>", cell)] + [Paragraph(f"<b>{_t(labels[l] if io else period)}</b>", center) for l in lenses] + [Paragraph("<b>Headline</b>", cell)]
    rows = [hdr]; styles = [("BACKGROUND", (0, 0), (-1, 0), _hex("DCEBF7")), ("GRID", (0, 0), (-1, -1), 0.4, _hex("D9DEE5")), ("VALIGN", (0, 0), (-1, -1), "MIDDLE")]
    for r_, d in enumerate(DIMS, 1):
        row = [Paragraph(f"<b>{d}. {_t(FW['dimensions'][d])}</b>", cell)]
        for k, l in enumerate(lenses, 1):
            g = C["dimensions"][d][l].get("grade"); row.append(gcell(g, 9)); styles.append(("BACKGROUND", (k, r_), (k, r_), _hex(GRADE_FILL.get(g))))
        row.append(Paragraph(_t((run.get("scorecard_headline") or {}).get(d, "")), small)); rows.append(row)
    n = len(lenses); sc = Table(rows, colWidths=[4.6 * cm] + [1.7 * cm] * n + [A4[0] - 3.2 * cm - 4.6 * cm - 1.7 * cm * n], repeatRows=1)
    sc.setStyle(TableStyle(styles)); story += [Paragraph("SCORECARD", kick), sc]

    # key findings
    story.append(Paragraph("KEY FINDINGS", kick))
    wm = run.get("what_moved")
    if wm: story.append(Paragraph(_t(wm), base))
    findings = run.get("headline_findings") or []
    for f in findings[:6]: story.append(Paragraph("- " + _t(f), bullet))
    if io and run.get("inside_vs_outside"):
        ivo = run["inside_vs_outside"]
        for key, title in (("better", "Better than the public evidence suggested"), ("worse", "Worse than the public evidence suggested")):
            if ivo.get(key):
                story.append(Paragraph(f"<b>{title}</b>", ParagraphStyle("t", parent=bold, spaceBefore=4)))
                for x in ivo[key][:4]: story.append(Paragraph("- " + _t(x), bullet))
    if run.get("peer_position"):
        story += [Paragraph("POSITION RELATIVE TO PEERS" + (f" ({len(peers)} peers)" if peers else ""), kick), Paragraph(_t(run["peer_position"]), base)]

    # actions
    story.append(Paragraph("ACTIONS", kick))
    for k, a in enumerate((run.get("actions") or [])[:5], 1):
        story.append(KeepTogether([Paragraph(f"<b>{k:02d}  {_t(a.get('heading', ''))}.</b> {_t(first_sentence(a.get('description')))}", bullet)]
                                  + ([Paragraph(_t(("Measures: " + "; ".join(a.get("measures", [])) if a.get("measures") else "") + (f"  Target: {a['target_by']}" if a.get("target_by") else "")), ParagraphStyle("m", parent=small, leftIndent=10))]
                                     if a.get("measures") or a.get("target_by") else [])))
    story += [Spacer(1, 8), Paragraph(_t("Grades apply to the board as a body; no individual is assessed. " + DRAFT), ParagraphStyle("d", parent=small, textColor=_hex(AMBER)))]

    doc = SimpleDocTemplate(out_path, pagesize=A4, leftMargin=1.6 * cm, rightMargin=1.6 * cm, topMargin=1.7 * cm, bottomMargin=1.6 * cm,
                            title=_t(f"{comp['name']} - Executive summary"), author="Alvarez & Marsal")
    doc.build(story, onFirstPage=foot, onLaterPages=foot)
    return out_path
