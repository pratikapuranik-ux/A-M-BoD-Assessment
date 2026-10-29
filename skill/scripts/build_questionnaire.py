#!/usr/bin/env python3
"""
build_questionnaire.py - produce the director self-assessment questionnaire as a Word file with
editable answer boxes (12 dimension-level questions, about 30 minutes to answer), plus an optional
1 / 3 / 5 self-rating per dimension.

Usage:
    python build_questionnaire.py "<Company>" out.docx [--simulate-answers run.json]

With --simulate-answers the answer boxes are pre-filled with plausible synthetic answers derived from
the current outside-in run (marked SIMULATED), for prototype testing.
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

SIM = {
 "1": ["Yes, a lost-contract debrief in Q2 changed our pricing posture; it reached us through the CEO's summary rather than directly. Most customer input arrives via management.", "Customer satisfaction sits in the annual bonus at about 10%; it has never reduced a payout to my knowledge."],
 "2": ["We revised our volume assumptions after a guidance miss last year; outside pressure prompted it, although the board had asked questions earlier.", "I trust the pipeline conversion number least. We have not retired a report in two years; the pack has grown."],
 "3": ["Electrification and channel shift. We hold a position on the first with capex targets; the second is discussed but without targets. Two external speakers in the past year.", "On tariffs we moved with peers; on the channel shift, after them. Management initiated both."],
 "4": ["Informally yes. A pricing pilot took one meeting; the divestiture took four. We deferred one acquisition for a further independent view.", "Minority views are not formally recorded. Decisions generally stay settled; one was revisited twice."],
 "5": ["Cost first, then buybacks to support EPS. Reinvestment was raised by two directors but not developed as an alternative.", "The last evaluation added a technology skills matrix; the last appointment brought digital experience. Owners would say we are slow to refresh."],
 "6": ["More time on earnings. No formal trigger; we would act on a rating warning. We refinanced early in 2025 before stress.", "Leverage policy is 2.0-2.5x net debt/EBITDA, reviewed annually, stress-tested at budget. Working capital is owned by the audit committee chair."]}


def main():
    if len(sys.argv) < 3: print(__doc__); sys.exit(2)
    company, out = sys.argv[1], sys.argv[2]
    sim = "--simulate-answers" in sys.argv
    doc = Document(); st = doc.styles["Normal"]; st.font.name = "Arial"; st.font.size = Pt(10)
    sec = doc.sections[0]; sec.left_margin = sec.right_margin = Cm(2)
    p(doc, "ALVAREZ & MARSAL  |  DAY 1 / DAY 2 BOARD ASSESSMENT", 8, True, BLUE)
    p(doc, f"Director self-assessment: {company}", 18, True, NAVY, after=2)
    p(doc, "Twelve questions, two per dimension, about 30 minutes. Answer in the shaded boxes in your own words; specific examples matter more than complete sentences. Your answers are read alongside the outside-in evidence and treated as self-reported. Nothing you write is attributed to you by name in the output." + ("  THIS COPY CONTAINS SIMULATED ANSWERS FOR PROTOTYPE TESTING." if sim else ""), 9, color=GREY, after=10)
    meta = doc.add_table(rows=2, cols=2); light_borders(meta)
    for r_, (k, v) in enumerate((("Your role on the board (optional)", ""), ("Date completed", ""))):
        meta.rows[r_].cells[0].text = k; meta.rows[r_].cells[1].text = v if not sim else ("Independent director (SIMULATED)" if r_ == 0 else "2026-10-23 (SIMULATED)")
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
        ans = SIM[d][(n - 1) % 2] if sim else ""
        rr = cell.paragraphs[0].add_run(f"[SIMULATED] {ans}" if sim else "Your answer:"); rr.font.size = Pt(9); rr.font.italic = not sim; rr.font.name = "Arial"
        if not sim: rr.font.color.rgb = rgb("9AA3B2")
        for _ in range(4 if not sim else 0): cell.add_paragraph()
        doc.add_paragraph().paragraph_format.space_after = Pt(2)
        if n % 2 == 0:
            rt = doc.add_table(rows=1, cols=4); light_borders(rt)
            rt.rows[0].cells[0].text = f"Your own rating for Dimension {d} (optional): mark one"
            shade(rt.rows[0].cells[0], TINT)
            for k, lab in enumerate(("1  Day 2", "3  Mixed", "5  Day 1"), 1):
                rt.rows[0].cells[k].text = ("☒ " if sim and k == random.choice([1, 2, 2, 3]) else "☐ ") + lab
            doc.add_paragraph()
    p(doc, "Thank you. Return this file to the A&M team. " + DRAFT, 8, italic=True, color=GREY)
    doc.save(out); print(f"Questionnaire written to {out}" + (" (simulated answers)" if sim else ""))


if __name__ == "__main__":
    main()
