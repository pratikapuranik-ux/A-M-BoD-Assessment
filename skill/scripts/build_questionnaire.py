#!/usr/bin/env python3
"""
build_questionnaire.py - produce the director self-assessment questionnaire as a Word file with
editable answer boxes (12 dimension-level questions, about 30 minutes to answer), plus an optional
1 / 3 / 5 self-rating per dimension.

Usage:
    python build_questionnaire.py "<Company>" out.docx

parse_questionnaire.py reads a returned file back into evidence items.
"""
import json, sys, random
from docx import Document
from docx.shared import Pt, RGBColor, Cm
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml.ns import qn
from docx.oxml import OxmlElement
from common import *


def rgb(h): return RGBColor(int(h[:2], 16), int(h[2:4], 16), int(h[4:], 16))

def shade(cell, fill):
    tcPr = cell._tc.get_or_add_tcPr(); shd = OxmlElement("w:shd"); shd.set(qn("w:val"), "clear"); shd.set(qn("w:color"), "auto"); shd.set(qn("w:fill"), fill); tcPr.append(shd)

def light_borders(table, color="BFC7D1"):
    b = OxmlElement("w:tblBorders")
    for side in ("top", "left", "bottom", "right", "insideH", "insideV"):
        e = OxmlElement(f"w:{side}"); e.set(qn("w:val"), "single"); e.set(qn("w:sz"), "4"); e.set(qn("w:color"), color); b.append(e)
    table._tbl.tblPr.append(b)

def p(doc, text, size=10, bold=False, color=None, italic=False, after=6):
    para = doc.add_paragraph(); r = para.add_run(text); r.font.size = Pt(size); r.font.bold = bold; r.font.italic = italic; r.font.name = "Arial"
    if color: r.font.color.rgb = rgb(color)
    para.paragraph_format.space_after = Pt(after); return para

def main():
    if len(sys.argv) < 3: print(__doc__); sys.exit(2)
    company, out = sys.argv[1], sys.argv[2]
    doc = Document(); st = doc.styles["Normal"]; st.font.name = "Arial"; st.font.size = Pt(10)
    sec = doc.sections[0]; sec.left_margin = sec.right_margin = Cm(2)
    p(doc, "ALVAREZ & MARSAL  |  DAY 1 / DAY 2 BOARD ASSESSMENT", 8, True, BLUE)
    p(doc, f"Director self-assessment: {company}", 18, True, NAVY, after=2)
    p(doc, "Twelve questions, two per dimension, about 30 minutes. Answer in the shaded boxes in your own words; specific examples matter more than complete sentences. Your answers are read alongside the outside-in evidence and treated as self-reported. Nothing you write is attributed to you by name in the output.", 9, color=GREY, after=10)
    meta = doc.add_table(rows=2, cols=2); light_borders(meta)
    for r_, (k, v) in enumerate((("Your role on the board (optional)", ""), ("Date completed", ""))):
        meta.rows[r_].cells[0].text = k; meta.rows[r_].cells[1].text = v
        shade(meta.rows[r_].cells[0], TINT)
    doc.add_paragraph()
    n = 0; cur = None
    for d, dname, q in FW["questionnaire"]:
        if d != cur:
            cur = d; p(doc, f"Dimension {d}: {dname}", 12, True, NAVY, after=2)
        n += 1
        p(doc, f"Q{n}. {q}", 10, True, after=3)
        t = doc.add_table(rows=1, cols=1); light_borders(t); cell = t.rows[0].cells[0]; shade(cell, "F7F9FB")
        cell.text = ""
        rr = cell.paragraphs[0].add_run("Your answer:"); rr.font.size = Pt(9); rr.font.italic = True; rr.font.name = "Arial"
        rr.font.color.rgb = rgb("9AA3B2")
        for _ in range(4): cell.add_paragraph()
        doc.add_paragraph().paragraph_format.space_after = Pt(2)
        if n % 2 == 0:
            rt = doc.add_table(rows=1, cols=4); light_borders(rt)
            rt.rows[0].cells[0].text = f"Your own rating for Dimension {d} (optional): mark one"
            shade(rt.rows[0].cells[0], TINT)
            for k, lab in enumerate(("1  Day 2", "3  Mixed", "5  Day 1"), 1):
                rt.rows[0].cells[k].text = "☐ " + lab
            doc.add_paragraph()
    p(doc, "Thank you. Return this file to the A&M team. " + DRAFT, 8, italic=True, color=GREY)
    doc.save(out); print(f"Questionnaire written to {out}")


if __name__ == "__main__":
    main()
