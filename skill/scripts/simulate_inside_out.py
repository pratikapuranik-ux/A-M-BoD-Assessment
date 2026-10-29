#!/usr/bin/env python3
"""
simulate_inside_out.py - generate a full set of SIMULATED inside-out documents for prototype testing,
zip them, and write a manifest listing the facts planted in each document.

Usage:
    python simulate_inside_out.py run.json out_dir [--seed 7]

Produces, under out_dir/inside_out_simulated/: thirteen Word documents (one per inside-out document type),
one Excel action tracker, the filled self-assessment questionnaire, and manifest.json. Then zips the folder
to out_dir/<Company>_inside_out_SIMULATED.zip. Every document is headed SIMULATED and references the
company's prior actions (if any) so the action-status logic can be exercised. The planted facts are
designed to move a handful of indicators both up and down relative to the outside-in scores.
"""
import json, sys, os, random, zipfile, subprocess
from docx import Document
from docx.shared import Pt, RGBColor, Cm
from openpyxl import Workbook
from common import *

HERE = os.path.dirname(os.path.abspath(__file__))


def mk(title, company, period, blocks):
    """blocks: list of ("h", text) | ("p", text) | ("b", [bullets]) | ("t", rows) | ("n", note)"""
    doc = Document(); st = doc.styles["Normal"]; st.font.name = "Arial"; st.font.size = Pt(10)
    sec = doc.sections[0]; sec.left_margin = sec.right_margin = Cm(2.2)
    h = doc.add_paragraph(); r = h.add_run("SIMULATED DOCUMENT FOR PROTOTYPE TESTING"); r.font.size = Pt(8); r.font.bold = True; r.font.color.rgb = RGBColor(0xCF, 0x7F, 0x00)
    t = doc.add_paragraph(); r = t.add_run(f"{company} — {title}"); r.font.size = Pt(16); r.font.bold = True; r.font.color.rgb = RGBColor(0, 0x2B, 0x49)
    d = doc.add_paragraph(); r = d.add_run(f"Period: {period}   ·   Classification: Board confidential (simulated)   ·   Names of individuals replaced by roles / letters"); r.font.size = Pt(8); r.font.italic = True
    for kind, body in blocks:
        if kind == "h":
            hh = doc.add_paragraph(); rr = hh.add_run(body); rr.font.bold = True; rr.font.size = Pt(11.5); rr.font.color.rgb = RGBColor(0, 0x85, 0xCA); hh.paragraph_format.space_before = Pt(10)
        elif kind == "h2":
            hh = doc.add_paragraph(); rr = hh.add_run(body); rr.font.bold = True; rr.font.size = Pt(10); rr.font.color.rgb = RGBColor(0, 0x2B, 0x49)
        elif kind == "p": doc.add_paragraph(body)
        elif kind == "n":
            pp = doc.add_paragraph(); rr = pp.add_run(body); rr.font.italic = True; rr.font.size = Pt(9); rr.font.color.rgb = RGBColor(0x64, 0x64, 0x64)
        elif kind == "b":
            for item in body: doc.add_paragraph(item, style="List Bullet")
        elif kind == "t":
            tb = doc.add_table(rows=1, cols=len(body[0])); tb.style = "Table Grid"
            for i, c in enumerate(body[0]):
                cell = tb.rows[0].cells[i]; cell.text = ""; rr = cell.paragraphs[0].add_run(str(c)); rr.font.bold = True; rr.font.size = Pt(8.5)
            for row in body[1:]:
                cells = tb.add_row().cells
                for i, c in enumerate(row):
                    cells[i].text = ""; rr = cells[i].paragraphs[0].add_run(str(c)); rr.font.size = Pt(8.5)
            doc.add_paragraph()
    return doc


def main():
    if len(sys.argv) < 3: print(__doc__); sys.exit(2)
    seed = int(sys.argv[sys.argv.index("--seed") + 1]) if "--seed" in sys.argv else 7
    random.seed(seed)
    run = json.load(open(sys.argv[1])); out = sys.argv[2]
    comp = company_of(run); name = comp["name"]; period = period_label(run); pp = prev_quarter(period)
    folder = os.path.join(out, "inside_out_simulated"); os.makedirs(folder, exist_ok=True)
    prior_actions = []
    for h in run.get("history", []): prior_actions = h.get("actions", []) or prior_actions
    status_plan = {}
    for k, a in enumerate(prior_actions):
        status_plan[a.get("id", f"A{k+1}")] = ["completed", "behind", "not_started", "on_track"][k % 4]
    manifest = {"company": name, "period": period, "simulated": True, "planted_facts": [], "prior_action_status_planted": status_plan}
    def fact(doc, inds, text, direction): manifest["planted_facts"].append({"document": doc, "indicators": inds, "fact": text, "expected_direction": direction})

    docs = {}
    M = ["Meeting 1 (first month of quarter Q-3)", "Meeting 2 (strategy offsite, quarter Q-2)", "Meeting 3 (quarter Q-1)", "Meeting 4 (quarter Q, actions review)"]
    att = "Present: Chair (independent), CEO, seven independent directors (Directors A-G), Company Secretary. In attendance for items as noted: CFO, General Counsel, Head of Sales, Head of Operations, Chief Customer Officer. Quorum confirmed."
    act_rows = [["Action id", "Heading", "Owner", "Target", "Status reported at Meeting 4", "Discussion"]]
    for a in prior_actions:
        stt = status_plan[a["id"]]; m = (a.get("measures") or ["measure"])[0]
        disc = {"completed": f"Chair confirmed completion; {m} is now reported at every meeting. Board thanked management.",
                "behind": "Management reported the work has slipped two quarters owing to competing priorities in the operations team and a vacancy in the analytics role. Director C asked for a recovery plan with named owner and dates by the next meeting; agreed.",
                "not_started": "No update provided; the item was not on the agenda. Director E noted this was the second meeting without an update. Chair agreed to carry it forward and to discuss ownership with the CEO.",
                "on_track": "On track; the framework draft was circulated for comment two weeks before the meeting; approval scheduled for the next meeting."}[stt]
        act_rows.append([a["id"], a["heading"], "CEO" if stt != "completed" else "CFO", a.get("target_by", ""), stt.replace("_", " "), disc])
    docs["01_Board_Minutes.docx"] = mk("Board minutes, last four meetings", name, period, [
        ("n", "Minutes are recorded in summary form in line with the company's minute-taking policy; decisions, dissent and actions are recorded verbatim where directors request it."),
        ("h", M[0]), ("p", att),
        ("h2", "1. Chair's opening remarks and conflicts"), ("p", "No conflicts declared. The Chair noted the forthcoming strategy offsite and asked directors to submit the two or three structural shifts they believe matter most for the company by the end of the month."),
        ("h2", "2. CEO report"), ("p", "The CEO presented the quarterly update (pack section 2): revenue in line with guidance, margin 40bp below plan on input costs, and the integration of the 2023 acquisition at 60% of planned synergies. Discussion focused on the margin shortfall; the CEO committed to a pricing update at Meeting 3."),
        ("h2", "3. Financial results and liquidity"), ("p", "The CFO presented results and the liquidity report. Headroom $560m against the $400m floor; net leverage 2.4x. The Finance Committee Chair reported that the committee had asked management in the prior quarter to examine early refinancing of the 2027 notes given the maturity concentration, before any rating-agency commentary. The board APPROVED the refinancing of the 2027 notes on the terms set out in the paper (RESOLVED, unanimous)."),
        ("h2", "4. Customer complaints trend"), ("p", "The Audit Committee Chair raised the complaints trend following a regulator enquiry received the previous month. Complaint volumes were not in the standing pack; the Chief Customer Officer joined by invitation and reported a 12% year-on-year increase concentrated in two product lines. Director B asked why the board had learned of the trend through the regulator rather than management. Management UNDERTOOK to add a customer outcomes section, including a watch list of accounts actively escalating, to the standing pack from Meeting 2 (ACTION: CEO)."),
        ("h2", "5. Committee reports"), ("p", "Audit: clean half-year review; one internal audit finding open (KPI definitions). Compensation: scorecard design for the coming year, with free cash flow weighting proposed to rise from 10% to 20%; the board endorsed the direction. Nominating & Governance: one director search in progress (technology)."),
        ("h2", "6. Executive session"), ("p", "Held without management; see Chair's notes (separate record)."),
        ("h", M[1]), ("p", att + " Head of Sales presented item 2 at the board's request."),
        ("h2", "1. Structural shifts"), ("p", "Directors' submissions were consolidated into four candidate shifts: electrification of the installed base, channel shift to digital procurement, input-cost volatility, and consolidation among distributors. The board agreed to hold an explicit position on electrification and channel shift, with the other two tracked as risks."),
        ("h2", "2. Plan assumptions: volume"), ("p", "At the board's request from the previous offsite, the Head of Sales presented order-book and win-rate data below the C-suite summary level. The data showed volume growth running at 1-2% against the plan assumption of 4%. After discussion, the board REQUESTED a revision of the volume assumption in the strategic plan (v2026) and a capex envelope for the electrification position. Directors D and F recorded a MINORITY VIEW that the revision did not go far enough and that the plan should assume flat volume; the minority view is minuted at their request and will be revisited at Meeting 4."),
        ("h2", "3. Proposed bolt-on acquisition"), ("p", "Management presented a $95m bolt-on acquisition in distribution. Directors questioned the synergy case given the 2023 acquisition's record and the absence of an independent commercial view. The board DECLINED to approve the transaction at this meeting and DEFERRED the decision pending an independent commercial review (ACTION: CFO to commission; report to Meeting 3)."),
        ("h2", "4. Channel shift"), ("p", "Discussed without an explicit target; management to return with options (ACTION: CEO, no date set)."),
        ("h2", "5. External perspective"), ("p", "An industry analyst addressed the board on electrification adoption curves. Directors found the session useful; the Chair asked the Company Secretary to schedule at least one external session per half-year."),
        ("h", M[2]), ("p", att),
        ("h2", "1. Pilot portfolio review"), ("p", "At the board's request, the CEO presented a review of the eleven pilots launched in the prior eighteen months: four scaled, five stopped, two still open beyond eighteen months without a decision. Director A asked why the two open pilots had not been decided; management cited competing priorities. The board ASKED for a scale-or-stop decision on both within one quarter (ACTION: CEO, Meeting 4)."),
        ("h2", "2. Capital allocation: buyback"), ("p", "Management proposed an increase in the buyback authorisation of $300m to support earnings per share following the margin shortfall. Director F asked for a reinvestment alternative to be presented alongside, consistent with the electrification position agreed at the offsite. The CFO stated that a reinvestment case was not available for this meeting. After discussion the board APPROVED the buyback increase (RESOLVED, seven in favour, two abstentions recorded: Directors D and F)."),
        ("h2", "3. Independent commercial review of the bolt-on"), ("p", "The review found the synergy case overstated by roughly a third. Management withdrew the proposal. The Chair noted the value of the deferral."),
        ("h2", "4. Pricing update"), ("p", "Pricing actions recovered 25bp of the 40bp margin gap; the remainder is expected in the next two quarters."),
        ("h2", "5. KPI restatement"), ("p", "The Audit Committee Chair noted that the pipeline conversion KPI in the pack had been restated in the quarter without explanation. Management explained a definition change; the Chair asked that definition changes be documented in the pack in future (ACTION: CFO)."),
        ("h", M[3]), ("p", att),
        ("h2", "1. Review of actions from the previous assessment"), ("p", "The board reviewed the status of each action arising from the previous assessment. Status as reported and discussed:"), ("t", act_rows),
        ("h2", "2. Open pilots"), ("p", "Both open pilots decided: one scaled with a $12m budget, one stopped with no restructuring charge. The board noted the decision was taken within the quarter requested."),
        ("h2", "3. Minority view on volume assumption"), ("p", "Revisited as agreed. Volume in the two quarters since the offsite ran at 1.4%; Directors D and F maintained their view; the board agreed to review again at the next offsite. No relitigation of the plan approval itself."),
        ("h2", "4. Customer outcomes (standing item)"), ("p", "Third quarterly report: NPS 31 (prior 34), complaints up 12%, watch list of three accounts, one at risk of churn ($40m revenue). The board asked the Chief Customer Officer to present a retention plan for the at-risk account at the next meeting."),
        ("h2", "5. Liquidity"), ("p", "Headroom $620m; stress test presented; early refinancing complete. Finance Committee Chair proposed liquidity early-warning triggers be added to the risk dashboard; AGREED."),
        ("h2", "6. Board pack"), ("p", "The Chair observed the pack had grown to 212 pages from 168 the prior year despite the evaluation action to reduce it. The Governance Committee was asked to propose which standing reports could be retired (ACTION: Governance Committee Chair, next meeting)."),
    ])
    fact("01_Board_Minutes.docx", ["2.1", "2.3", "4.3"], "Board-initiated assumption revision with sub-C-suite evidence and minuted minority view", "up")
    fact("01_Board_Minutes.docx", ["4.2"], "Acquisition declined pending independent review; review found synergies overstated", "up")
    fact("01_Board_Minutes.docx", ["5.1", "5.4"], "Buyback approved without a reinvestment alternative being presented; two abstentions", "down")
    fact("01_Board_Minutes.docx", ["4.1"], "Two pilots open beyond 18 months; decided within the quarter the board set", "mixed")
    fact("01_Board_Minutes.docx", ["1.3", "1.1"], "Complaints trend reached the board via a regulator enquiry; customer outcomes then made a standing item", "mixed")

    docs["02_Board_Agendas_and_Calendar.docx"] = mk("Board agendas and annual calendar", name, period, [
        ("h", "Standing agenda structure"), ("p", "Every scheduled meeting follows the same skeleton: Chair's remarks and conflicts; CEO report; financial results and liquidity (Finance Committee); operations; committee reports; risk and compliance; executive session. From Meeting 2 a customer outcomes item was added as standing item 4, following the complaints discussion at Meeting 1. Strategy is covered in depth once a year at the offsite and otherwise appears as sub-items under the CEO report."),
        ("h", "Agenda, " + M[0]), ("t", [["Time", "Item", "Lead", "Type"], ["08:30", "Chair's remarks; conflicts", "Chair", "Governance"], ["08:45", "CEO report", "CEO", "Reporting"], ["09:45", "Financial results and liquidity", "CFO", "Reporting"], ["10:45", "Customer complaints trend (added at Audit Chair's request)", "Audit Chair / CCO", "Risk"], ["11:30", "Committee reports", "Committee Chairs", "Governance"], ["12:30", "Lunch", "", ""], ["13:15", "2027 notes refinancing: approval", "CFO", "Decision"], ["14:00", "Risk and compliance update", "GC", "Reporting"], ["15:00", "Executive session", "Chair", "Governance"]]),
        ("h", "Agenda, " + M[1]), ("t", [["Time", "Item", "Lead", "Type"], ["08:30", "Structural shifts: directors' submissions", "Chair", "Strategy"], ["09:30", "Volume assumption: order-book evidence", "Head of Sales", "Strategy"], ["11:00", "Plan v2026: revision request", "Board", "Decision"], ["12:00", "Proposed bolt-on acquisition", "CEO / CFO", "Decision"], ["13:30", "Channel shift options", "CEO", "Strategy"], ["14:30", "External speaker: electrification adoption", "Industry analyst", "External"], ["15:30", "Executive session", "Chair", "Governance"]]),
        ("h", "Agenda, " + M[2]), ("t", [["Time", "Item", "Lead", "Type"], ["08:30", "Chair's remarks", "Chair", "Governance"], ["08:40", "CEO report incl. pilot portfolio review", "CEO", "Reporting"], ["09:45", "Financial results and liquidity", "CFO", "Reporting"], ["10:30", "Customer outcomes (standing)", "CCO", "Customer"], ["11:00", "Buyback authorisation increase", "CFO", "Decision"], ["11:45", "Independent commercial review: bolt-on", "Adviser", "Decision"], ["12:30", "Pricing update", "CEO", "Reporting"], ["13:30", "Committee reports; KPI restatement", "Committee Chairs", "Governance"], ["14:30", "Risk and compliance", "GC", "Reporting"]]),
        ("h", "Agenda, " + M[3]), ("t", [["Time", "Item", "Lead", "Type"], ["08:30", "Actions from previous assessment: status review", "Chair", "Governance"], ["09:30", "Open pilots: scale-or-stop decisions", "CEO", "Decision"], ["10:00", "Minority view on volume: revisit", "Chair", "Strategy"], ["10:30", "Customer outcomes (standing)", "CCO", "Customer"], ["11:15", "Liquidity and early-warning triggers", "CFO", "Decision"], ["12:00", "Board pack: standing reports review", "Chair", "Governance"], ["13:30", "Committee reports", "Committee Chairs", "Governance"], ["14:30", "Executive session", "Chair", "Governance"]]),
        ("h", "Time allocation (Company Secretary's analysis)"), ("t", [["Meeting", "Reporting and compliance", "Strategy, customer, talent, capital decisions", "External voices"], ["M1", "70%", "30%", "0"], ["M2 (offsite)", "15%", "85%", "1 (industry analyst)"], ["M3", "60%", "40%", "1 (independent adviser)"], ["M4", "55%", "45%", "0"], ["Year average", "50%", "50%", "2"]]),
        ("h", "Annual calendar"), ("t", [["Month", "Event", "Notes"], ["1", "Board meeting 1; Audit Committee", "Results"], ["2", "Site visit: plant (East)", "Completed; management present throughout"], ["3", "Strategy offsite (Meeting 2)", "External speaker"], ["4", "Compensation Committee", "Scorecard"], ["5", "AGM", ""], ["6", "Board meeting 3; Finance Committee stress test", ""], ["7", "Site visit: distribution centre", "Scheduled; not yet held"], ["9", "Board meeting 4; Nominating & Governance", "Actions review"], ["11", "Board evaluation (internal questionnaire)", "Externally facilitated review planned for next cycle"]]),
        ("p", "No customer advisory board exists. Director contact with customers outside site visits is not scheduled."),
    ])
    fact("02_Board_Agendas_and_Calendar.docx", ["1.1"], "Customer outcomes became a standing item from Meeting 2", "up")
    fact("02_Board_Agendas_and_Calendar.docx", ["1.2", "3.3"], "Site visits with management present; two external voices in the year; no customer advisory board", "flat")

    kpis = [["KPI", "Definition (per pack glossary)", "Q-4", "Q-3", "Q-2", "Q-1", "Q", "Definition last changed"],
            ["Revenue growth (organic)", "Constant currency, ex M&A", "3.1%", "2.4%", "1.9%", "1.6%", "1.4%", "2021"],
            ["Adjusted EBIT margin", "Ex restructuring and amortisation", "14.2%", "13.9%", "13.6%", "13.8%", "14.0%", "2021"],
            ["Free cash flow conversion", "FCF / net income", "78%", "80%", "82%", "85%", "88%", "2021"],
            ["Net leverage", "Net debt / adj. EBITDA", "2.5x", "2.4x", "2.4x", "2.3x", "2.3x", "2021"],
            ["Pipeline conversion", "Orders won / qualified pipeline", "31%", "30%", "36%*", "35%", "34%", "Q-2 (restated; not documented in pack)"],
            ["On-time delivery", "Lines delivered on promised date", "93%", "92%", "92%", "91%", "91%", "2019"],
            ["Safety TRIR", "Recordable incidents per 200k hours", "0.9", "0.8", "0.9", "0.7", "0.7", "2019"],
            ["Employee engagement", "Annual survey index", "71", "71", "-", "-", "69", "2022"],
            ["NPS (new from M2)", "Relationship NPS, top-50 accounts", "-", "-", "34", "32", "31", "Q-2"],
            ["Complaints volume (new from M2)", "Logged complaints per quarter", "-", "-", "1,180", "1,240", "1,320", "Q-2"],
            ["Synergy capture, 2023 acquisition", "Run-rate vs plan", "48%", "52%", "55%", "58%", "60%", "2023"],
            ["Capex / depreciation", "", "0.9x", "0.9x", "1.0x", "1.1x", "1.1x", "2021"],
            ["Working capital days", "Cash conversion cycle", "52", "51", "50", "49", "48", "2021"],
            ["Return on invested capital", "Adj. NOPAT / invested capital", "11.2%", "11.0%", "10.9%", "11.1%", "11.3%", "2021"]]
    docs["03_Board_Pack_Extracts.docx"] = mk("Board pack extracts: KPI dashboard, customer section, pack statistics", name, period, [
        ("h", "KPI dashboard (section 3 of the pack)"), ("p", "Fourteen headline KPIs are reported each meeting against plan and prior year. Definitions are held in a glossary last reviewed in 2021. The pipeline conversion KPI was restated in Q-2 (marked *) when the definition of 'qualified pipeline' was narrowed; the change was not noted in the pack and was raised by the Audit Committee Chair at Meeting 3."), ("t", kpis),
        ("h", "Customer outcomes section (section 4, introduced at Meeting 2)"), ("p", "Prepared by the Chief Customer Officer's team. Sources are management-curated (CRM and complaints system); no unfiltered customer voice is included, though verbatim complaint extracts were added from Q-1 at Director B's request."),
        ("t", [["Segment", "Relationship NPS Q", "Change vs Q-2", "Complaints Q", "Top-10 account health"], ["Distributors", "28", "-4", "610", "7 green, 2 amber, 1 red"], ["OEMs", "36", "-2", "390", "8 green, 1 amber, 1 red"], ["Direct / fleet", "33", "-3", "320", "9 green, 1 amber"]]),
        ("h2", "Watch list: accounts actively escalating"), ("t", [["Account (coded)", "Segment", "Annual revenue", "Issue", "Status", "Owner"], ["D-07", "Distributor", "$40m", "Repeated late deliveries; threatening to dual-source", "Red: executive sponsor assigned; retention plan due Meeting 5", "CCO"], ["O-03", "OEM", "$22m", "Quality escape on one product line", "Amber: containment complete; audit scheduled", "COO"], ["D-12", "Distributor", "$9m", "Pricing dispute after Q-1 increase", "Amber: negotiation in progress", "Head of Sales"]]),
        ("h", "Pack statistics"), ("t", [["Measure", "Prior year", "This year"], ["Pack length (pages, average)", "168", "212"], ["Standing reports", "19", "22"], ["Reports retired in the year", "0", "0"], ["Papers circulated less than 5 days before meeting", "3", "6"]]),
        ("n", "Observation from the Company Secretary: the pack has grown by 26% in a year despite the board evaluation action to reduce it; no standing report has been retired in three years."),
    ])
    fact("03_Board_Pack_Extracts.docx", ["1.1", "1.3"], "Customer section with NPS, complaints, account health and watch list now in pack; verbatim complaints added", "up")
    fact("03_Board_Pack_Extracts.docx", ["2.2", "2.4"], "KPI restated without documentation; pack growing; no reports retired in three years", "down")

    docs["04_Governance_Framework.docx"] = mk("Governance framework: matters reserved, delegation of authority, committee terms of reference, capital and treasury policies, incentive scorecard", name, period, [
        ("h", "Matters reserved for the board"), ("b", ["Strategy and the annual plan; material changes to either.", "Capital commitments above $50m; M&A and disposals above $25m enterprise value.", "Leverage outside the treasury policy range; dividends; buyback authorisations.", "Appointment and removal of the CEO and CFO; CEO succession plan.", "Board and committee composition; charters; the board evaluation.", "Material litigation and regulatory settlements.", "Risk appetite statement."]),
        ("n", "The schedule classifies matters by value and category. It does not distinguish reversible from irreversible decisions, and operating decisions below the thresholds are delegated without a stated expectation on decision speed."),
        ("h", "Delegation of authority (summary)"), ("t", [["Decision", "Board", "CEO", "Executive Committee", "Business unit head"], ["Capital commitment", "> $50m", "$10-50m", "$2-10m", "< $2m"], ["M&A / disposal", "> $25m EV", "$5-25m EV", "-", "-"], ["Pricing changes", "-", "Portfolio-wide > 5%", "Segment-level", "Account-level"], ["New product / pilot launch", "-", "> $5m", "$1-5m", "< $1m"], ["Pilot stop decision", "-", "Any", "Any", "Any within own budget"], ["Headcount plan", "Annual plan", "Within plan", "Within BU plan", "-"]]),
        ("h", "Committees"), ("t", [["Committee", "Established", "Members", "Meetings / year", "Last terms-of-reference change", "Independent advisers retained"], ["Audit", "Legacy", "4", "6", "2021", "External auditor; internal audit co-source"], ["Compensation", "Legacy", "3", "5", "2024 (FCF measure added)", "Compensation consultant"], ["Nominating & Governance", "Legacy", "3", "4", "2020", "Search firm (ad hoc)"], ["Finance", "2024", "4", "4", "2024 (new)", "None"], ["Technology", "Proposed", "-", "-", "-", "-"]]),
        ("h", "Capital allocation policy (approved 2024)"), ("b", ["Priority 1: maintenance and safety capex (c. 0.7x depreciation).", "Priority 2: growth capex and R&D consistent with the strategic plan, up to 1.3x depreciation in aggregate.", "Priority 3: dividend growth in line with earnings.", "Priority 4: bolt-on M&A within the leverage range.", "Priority 5: buybacks from surplus cash; proposals to state the alternative uses considered (policy wording; not applied at Meeting 3)."]),
        ("h", "Treasury policy"), ("t", [["Parameter", "Policy", "Position at Q"], ["Net leverage", "2.0x - 2.5x through the cycle", "2.3x"], ["Minimum liquidity headroom", "$400m (cash plus undrawn committed facilities)", "$620m"], ["Maturity concentration", "No more than 25% of gross debt in any twelve months", "Compliant after 2027 refinancing (was 38%)"], ["Stress testing", "Twice a year to the Finance Committee; scenario of revenue -15% and margin -200bp", "Presented M1 and M4"], ["Counterparty limits", "Investment grade; single-name cap 20%", "Compliant"]]),
        ("h", "Executive incentive scorecard (current year)"), ("t", [["Component", "Measure", "Weight", "Threshold / target / max", "Prior year weight"], ["Annual bonus", "Adjusted EBIT", "40%", "95% / 100% / 110% of plan", "50%"], ["Annual bonus", "Free cash flow", "20%", "$ plan", "10%"], ["Annual bonus", "Revenue", "10%", "Plan", "10%"], ["Annual bonus", "Customer satisfaction (NPS and complaints composite)", "20%", "Composite index", "20%"], ["Annual bonus", "Safety (TRIR)", "10%", "Gate plus scale", "10%"], ["LTI", "Relative TSR", "50%", "Median / 60th / 80th percentile", "50%"], ["LTI", "ROIC", "50%", "10.5% / 11.5% / 12.5%", "50%"]]),
        ("n", "Compensation Committee note: the customer composite paid at 92% of target last year; no year on record has paid below threshold on that measure."),
    ])
    fact("04_Governance_Framework.docx", ["6.1", "6.2", "1.4"], "FCF at 20% of bonus; customer satisfaction 20% (but never paid below threshold); liquidity policy with headroom floor and stress tests", "up")
    fact("04_Governance_Framework.docx", ["4.1"], "Delegation disclosed by value, not reversibility; pilot stop delegated at any level", "flat")

    docs["05_Strategy_Papers_and_Plan_Versions.docx"] = mk("Strategy papers and plan versions (three cycles)", name, period, [
        ("h", "Plan assumptions by version"), ("t", [["Assumption", "Plan v2024", "Plan v2025", "Plan v2026 (board-requested revision)", "Source of change"], ["Market volume growth", "4%", "2%", "1% (minority view: flat)", "Order-book and win-rate evidence presented by Head of Sales at board request"], ["Price / mix", "+2%", "+2%", "+2.5%", "Pricing programme"], ["Electrification share of installed base", "Not addressed", "Risk factor only", "12% by year 5; explicit position; capex envelope $300m over three years", "Board offsite decision"], ["Channel shift to digital procurement", "Not addressed", "Risk factor only", "Risk factor; options requested; no target", "Open action"], ["Input-cost volatility", "Hedging policy", "Hedging policy", "Hedging policy; pass-through target 80%", "Pricing programme"], ["Distributor consolidation", "Not addressed", "Watch", "Watch", "-"], ["Synergy capture (2023 acquisition)", "100% by year 2", "80% by year 3", "70% by year 3", "Post-investment review"]]),
        ("h", "Offsite paper: structural shifts (Meeting 2)"), ("p", "Management's paper presented electrification as the central shift and proposed a three-year capex envelope of $300m, phased $60m / $110m / $130m, with stage gates at the end of years one and two. Channel shift was presented as a risk to distributor relationships rather than as an opportunity; the board asked for an options paper, which has not yet been scheduled."),
        ("h", "Board's revision request (extract from the resolution)"), ("p", "RESOLVED that management revise the strategic plan to reflect a 1% market volume assumption, incorporate the electrification position and capex envelope, and return with a channel-shift options paper. The Chair recorded that the revision was initiated by the board on the basis of evidence it had itself requested, and preceded the subsequent guidance reset announced to the market."),
        ("h", "Previous cycles"), ("p", "Plan v2024 and v2025 were approved as presented by management with amendments limited to phasing. The v2025 volume reduction from 4% to 2% followed two quarters of misses rather than a change in evidence requested by the board."),
    ])
    fact("05_Strategy_Papers_and_Plan_Versions.docx", ["2.1", "3.1"], "Board-requested plan revision ahead of the guidance reset; explicit position on one of two shifts", "up")

    docs["06_Capital_and_Investment_Papers.docx"] = mk("Capital and investment papers with post-investment reviews", name, period, [
        ("h", "Investment paper: plant automation programme, $180m (approved Meeting 1 of the prior year)"), ("t", [["Alternative", "Capex", "Payback", "NPV at 9%", "Key risk"], ["Do nothing", "$0", "-", "$0 (base)", "Cost position erodes; two lines become uncompetitive by year 4"], ["Partial automation (two lines)", "$95m", "5.1 years", "$38m", "Leaves highest-cost line unaddressed"], ["Full automation (recommended)", "$180m", "4.6 years", "$71m", "Execution across three sites in parallel"]]),
        ("h2", "Pre-mortem (board request)"), ("b", ["Programme overruns by 20% because the three sites are run in parallel: mitigant, sequence sites with a six-month gap; adopted.", "Volume falls short and the payback extends to seven years: mitigant, stage gate after site one; adopted.", "Skills shortage in controls engineering: mitigant, retain integrator for two years; adopted."]),
        ("n", "Board decision: approved full automation with the sequencing and stage-gate mitigants. The paper is the first to include a pre-mortem; it was requested by Director A."),
        ("h", "Post-investment review: 2023 acquisition (presented Meeting 3)"), ("t", [["Metric", "Investment case", "Actual at 24 months", "Variance"], ["Revenue synergies", "$30m run-rate", "$12m", "-60%"], ["Cost synergies", "$45m run-rate", "$33m", "-27%"], ["Integration cost", "$20m", "$29m", "+45%"], ["Customer retention", "95%", "88%", "-7pts"], ["ROIC year 2", "10%", "6.4%", "-3.6pts"]]),
        ("p", "Lessons recorded: revenue synergies assumed cross-selling into distributor accounts that had exclusive arrangements with competitors; diligence did not test this. The board asked that future acquisition cases include an independent commercial view, which was applied to the bolt-on proposal at Meeting 2."),
        ("h", "Post-investment review: 2022 acquisition"), ("p", "No review exists. The Audit Committee asked for one in the prior year; it was deferred twice and is not scheduled."),
        ("h", "Buyback authorisation increase, $300m (Meeting 3)"), ("p", "Paper presented by the CFO: rationale is earnings-per-share support following the margin shortfall; surplus cash after the refinancing; leverage remains within policy. Alternative uses considered: the paper lists 'accelerate electrification capex' as an alternative but provides no case, timing or return estimate. Director F's request for a reinvestment alternative was recorded; the paper was not revised before approval."),
    ])
    fact("06_Capital_and_Investment_Papers.docx", ["4.2", "3.4"], "Alternatives and pre-mortem on major capex; one post-investment review completed with lessons applied, one missing", "mixed")
    fact("06_Capital_and_Investment_Papers.docx", ["5.1"], "Buyback paper names a reinvestment alternative without any case behind it", "down")

    docs["07_Treasury_and_Liquidity_Report.docx"] = mk("Treasury and liquidity report to the Finance Committee and board", name, period, [
        ("h", "Liquidity position"), ("t", [["Component", "Q-1", "Q"], ["Cash and equivalents", "$210m", "$240m"], ["Undrawn committed revolving facility", "$350m", "$380m"], ["Total headroom", "$560m", "$620m"], ["Policy floor", "$400m", "$400m"], ["Headroom above floor", "$160m", "$220m"]]),
        ("h", "Maturity ladder (gross debt $1.9bn)"), ("t", [["Year", "Before refinancing", "After refinancing", "Instrument"], ["Year 1", "$120m", "$120m", "Term loan amortisation"], ["Year 2 (2027)", "$720m", "$220m", "2027 notes: $500m refinanced early"], ["Year 3", "$300m", "$300m", "Notes"], ["Year 4", "$260m", "$260m", "Notes"], ["Year 5+", "$500m", "$1,000m", "New 2031 notes $500m"]]),
        ("p", "The 2027 notes were refinanced eleven months ahead of maturity. The Finance Committee requested the analysis in Q-3 on the basis of the maturity concentration (38% in one year against a 25% policy limit), before any rating-agency commentary. The new notes priced 15bp inside the secondary curve."),
        ("h", "Covenants and ratings"), ("t", [["Item", "Requirement", "Position", "Headroom"], ["Net leverage covenant", "< 3.5x", "2.3x", "1.2x"], ["Interest cover covenant", "> 3.0x", "6.8x", "3.8x"], ["Rating (agency 1)", "-", "BBB, stable", "-"], ["Rating (agency 2)", "-", "Baa2, stable", "-"]]),
        ("h", "Stress test (presented Meeting 4)"), ("t", [["Scenario", "Assumption", "Minimum headroom", "Quarter of minimum", "Covenant breach?"], ["Base", "Plan", "$590m", "-", "No"], ["Downside", "Revenue -15%, margin -200bp", "$430m", "Q+6", "No"], ["Severe", "Revenue -25%, margin -300bp, working capital +10 days", "$310m", "Q+5", "No (leverage 3.2x)"], ["Severe plus rating downgrade", "As severe, plus facility margin step-up", "$290m", "Q+5", "No"]]),
        ("n", "Under the severe scenario headroom falls below the $400m floor in quarter five; management's response plan (capex deferral $80m, working capital programme $50m, dividend hold) restores the floor within two quarters. The Finance Committee asked for the response plan to be pre-approved as a contingency; agreed."),
        ("h", "Working capital"), ("t", [["Measure", "Q-4", "Q-2", "Q", "Peer median"], ["Receivable days", "58", "56", "55", "60"], ["Inventory days", "71", "69", "67", "75"], ["Payable days", "77", "75", "74", "80"], ["Cash conversion cycle", "52", "50", "48", "55"]]),
        ("h", "Early-warning triggers (adopted Meeting 4)"), ("b", ["Headroom below $480m for two consecutive months.", "Net leverage above 2.4x at any quarter end.", "Any rating outlook change to negative.", "Receivable days above 60 or inventory days above 75.", "Any single maturity year above 20% of gross debt."]),
    ])
    fact("07_Treasury_and_Liquidity_Report.docx", ["6.2", "6.3"], "Headroom above floor under downside stress; proactive refinancing initiated by the committee; early-warning triggers adopted; contingency plan pre-approved", "up")

    docs["08_Board_Evaluation_Report_and_Action_Log.docx"] = mk("Board evaluation report and action log", name, period, [
        ("h", "Method"), ("p", "Internal questionnaire administered by the Company Secretary (38 questions, 1-5 scale, free text); individual director reviews conducted by the Chair for the first time this cycle; committee self-reviews. The last externally facilitated evaluation was four years ago; the next cycle is planned to be externally facilitated."),
        ("h", "Results by theme"), ("t", [["Theme", "Average score (1-5)", "Change vs prior", "Representative comment (anonymised)"], ["Strategy time and quality", "3.1", "+0.2", "Offsite was the best in years; too little strategy between offsites"], ["Information and board pack", "2.6", "-0.3", "Pack is too long and arrives late; definitions change without warning"], ["Board composition and skills", "3.4", "+0.4", "Digital appointment helped; still light on electrification and software"], ["Dynamics and challenge", "3.8", "+0.1", "Challenge is real and well received; minority views are recorded"], ["Committee effectiveness", "3.6", "0.0", "Finance Committee has sharpened liquidity oversight"], ["Customer and external focus", "2.9", "+0.5", "Customer item is a real improvement; directors still rarely meet customers"], ["Succession and renewal", "3.0", "-0.1", "Tenure is long; retirement-age waiver sets a precedent"], ["Chair and executive session", "3.9", "+0.1", "Sessions are substantive"]]),
        ("h", "Action log"), ("t", [["#", "Action from evaluation", "Owner", "Due", "Status", "Note"], ["1", "Reduce pack length to 150 pages", "Company Secretary / CFO", "Last year", "Open (behind)", "Pack grew to 212 pages; Governance Committee now reviewing standing reports"], ["2", "Add technology expertise to the board", "N&G Chair", "Last year", "Closed", "Digital director appointed"], ["3", "Increase strategy time between offsites", "Chair", "This year", "Open", "One additional strategy item per meeting from M3"], ["4", "Externally facilitated evaluation", "N&G Chair", "Next cycle", "Planned", "Provider shortlist prepared"], ["5", "Individual director reviews", "Chair", "This cycle", "Closed", "Completed for all directors"], ["6", "Director customer engagement programme", "CCO / Chair", "This year", "Not started", "No owner assigned until Meeting 4"]]),
        ("h", "Owner engagement"), ("p", "The Chair and the Compensation Committee Chair met the ten largest shareholders after the AGM; say-on-pay support was 87% (prior 91%); two holders raised buyback versus reinvestment. The board discussed the feedback at Meeting 3; no change was made to the buyback proposal."),
    ])
    fact("08_Board_Evaluation_Report_and_Action_Log.docx", ["5.3"], "Internal evaluation with individual reviews; actions partly closed; pack action behind; owner feedback heard but not acted on", "flat")

    docs["09_Skills_Matrix_and_Succession_Plans.docx"] = mk("Skills matrix and board and CEO succession plans", name, period, [
        ("h", "Board composition (directors coded)"), ("t", [["Director", "Role", "Tenure (years)", "Age band", "Primary skills", "Committees"], ["Chair", "Independent Chair", "11", "65-70", "Industrial CEO; capital markets", "N&G (Chair), Finance"], ["A", "Independent", "14", "70-75", "Engineering; operations", "Audit, Finance"], ["B", "Independent", "12", "65-70", "Audit; risk", "Audit (Chair)"], ["C", "Independent", "9", "60-65", "Consumer; marketing", "Compensation"], ["D", "Independent", "8", "60-65", "Finance; M&A", "Finance (Chair), Audit"], ["E", "Independent", "7", "55-60", "Legal; regulatory", "N&G, Compensation (Chair)"], ["F", "Independent", "6", "55-60", "Sustainability; energy", "Finance"], ["G", "Independent", "2", "45-50", "Digital; software", "Technology (proposed)"], ["CEO", "Executive", "5", "55-60", "Operations; sales", "-"]]),
        ("p", "Average independent director tenure 9.1 years. One appointment in the last three years (Director G, digital). No term limit. Retirement age 75; waived once (Director A, current year) by board resolution."),
        ("h", "Skills matrix against the named structural shifts"), ("t", [["Skill", "Directors with deep experience", "Assessment"], ["Electrification / power electronics", "F (partial)", "Gap; search brief being drafted"], ["Digital channels / software", "G", "Covered by one director"], ["Distribution / channel economics", "C, CEO", "Covered"], ["Capital allocation / M&A", "Chair, D", "Covered"], ["Restructuring / liquidity", "D", "Thin"], ["Customer-side executive experience (end markets)", "None", "Gap"]]),
        ("h", "CEO succession"), ("p", "Two internal candidates (COO and CFO) with development plans reviewed annually by the N&G Committee with the Chair; an emergency successor (COO) is named and reviewed each year. External benchmarking of the internal candidates was last done three years ago; the committee has asked for a refresh next year."),
        ("h", "Board succession"), ("p", "Plan to appoint one director with electrification experience within eighteen months; Director A's retirement waiver expires next year and is not expected to be renewed. No plan addresses the tenure profile beyond that."),
        ("h", "Leadership pipeline below CEO"), ("p", "Talent review covers the top 40 roles; 60% have a ready-now or ready-in-one-year successor; the Chief Customer Officer role has none."),
    ])
    fact("09_Skills_Matrix_and_Succession_Plans.docx", ["5.2", "3.3"], "Long tenure and waived retirement age; CEO succession planned; electrification and customer-side gaps acknowledged", "mixed")

    ceo_reports = [("Report 1", "48%", "24%", "8%", "12%", "8%", "Margin shortfall; integration; refinancing"), ("Report 2 (offsite)", "20%", "15%", "15%", "40%", "10%", "Volume evidence; electrification; channel options"), ("Report 3", "46%", "26%", "16%", "8%", "4%", "Pricing recovery; pilot review; buyback"), ("Report 4", "40%", "22%", "20%", "12%", "6%", "Actions review; customer retention; triggers")]
    docs["10_CEO_Reports_to_the_Board.docx"] = mk("CEO reports to the board (last four): extracts and content analysis", name, period, [
        ("h", "Content analysis (Company Secretary)"), ("t", [["Report", "Financial results", "Operations", "Customers", "Structural shifts / strategy", "Cash and liquidity", "Headline topics"]] + [list(r) for r in ceo_reports] + [["Average", "38%", "22%", "15%", "18%", "7%", ""]]),
        ("p", "Customer content rose from 8% to 20% across the year after the Audit Committee Chair's request at Meeting 1. Cash and liquidity content remains low in the CEO's report because it is covered by the CFO's liquidity report; directors have not objected."),
        ("h", "Extract, Report 1"), ("p", "Margin finished 40bp below plan on input costs, partly offset by pricing. Integration of the 2023 acquisition is at 60% of planned synergies; the revenue synergy case was over-optimistic and we will present the post-investment review at Meeting 3. The refinancing of the 2027 notes is recommended now, while markets are open; the Finance Committee asked us to bring this forward and we agree."),
        ("h", "Extract, Report 2"), ("p", "The order book supports 1-2% volume growth, not 4%. We recommend the board consider electrification as the central structural shift and approve a capex envelope. On channel shift, we see risk to distributor relationships and would prefer to study options before committing."),
        ("h", "Extract, Report 3"), ("p", "Pricing has recovered 25bp. Of eleven pilots, four scaled and five stopped; two remain open and we will decide within the quarter as requested. We recommend a $300m buyback increase to support EPS following the margin shortfall; leverage remains within policy. We have not prepared a reinvestment alternative for this meeting."),
        ("h", "Extract, Report 4"), ("p", "Both open pilots are decided. Customer: NPS 31, complaints up 12%, one $40m account at risk; the retention plan comes next meeting. Liquidity: refinancing complete, headroom $620m. Actions from the previous assessment: status attached; two are behind plan and I take responsibility for the ownership gap."),
    ])
    fact("10_CEO_Reports_to_the_Board.docx", ["1.1", "6.1"], "Customer share of CEO report rising to 20%; cash share low (covered elsewhere)", "mixed")

    docs["11_Customer_Insight_and_Key_Account_Reports.docx"] = mk("Customer insight and key-account reports (quarterly, from Meeting 2)", name, period, [
        ("h", "Relationship NPS, top-50 accounts"), ("t", [["Quarter", "NPS", "Response rate", "Promoters", "Detractors", "Top detractor theme"], ["Q-2", "34", "62%", "48%", "14%", "Delivery reliability"], ["Q-1", "32", "58%", "46%", "14%", "Delivery reliability"], ["Q", "31", "60%", "45%", "14%", "Delivery reliability; pricing"]]),
        ("h", "Complaints"), ("t", [["Category", "Q-2", "Q-1", "Q", "Trend"], ["Late delivery", "520", "560", "610", "Rising"], ["Quality / returns", "310", "330", "350", "Rising"], ["Billing / pricing", "190", "200", "230", "Rising after Q-1 price increase"], ["Service response", "160", "150", "130", "Falling"], ["Total", "1,180", "1,240", "1,320", "+12% year on year"]]),
        ("h", "Key-account health and watch list"), ("t", [["Account", "Segment", "Revenue", "Health", "Escalation history", "Action"], ["D-07", "Distributor", "$40m", "Red", "Three escalations to CEO level in two quarters; threatening to dual-source", "Executive sponsor assigned (COO); retention plan to board Meeting 5"], ["O-03", "OEM", "$22m", "Amber", "Quality escape; containment complete", "Customer audit scheduled"], ["D-12", "Distributor", "$9m", "Amber", "Pricing dispute", "Negotiation in progress"], ["O-01", "OEM", "$55m", "Green", "None", "Annual business review complete"], ["D-02", "Distributor", "$38m", "Green", "None", "-"]]),
        ("h", "Verbatim complaint extracts (added at Director B's request)"), ("b", ["Distributor, Q: 'Third late shipment this quarter; we are quoting your competitor for the next tender.'", "OEM, Q-1: 'The quality escape cost us a line stop; your response was fast but the root cause took six weeks.'", "Fleet customer, Q: 'The price increase letter arrived after the invoice.'"]),
        ("h", "Customer advisory board"), ("p", "Not established. The Chief Customer Officer's paper recommends a distributor advisory council reporting to the board twice a year; no decision has been taken."),
        ("h", "Lost deals"), ("p", "Four tenders above $5m lost in the quarter; three cited delivery reliability. Lost-deal reviews are held within the sales function and have not been presented to the board."),
    ])
    fact("11_Customer_Insight_and_Key_Account_Reports.docx", ["1.3", "1.1"], "Watch list and verbatim complaints reach the board quarterly; one account at risk; lost-deal reviews still not presented", "up")

    risks = [["#", "Risk", "Owner", "Likelihood", "Impact", "Trend", "Early-warning indicator in dashboard"], ["1", "Liquidity shortfall under severe downside", "CFO", "Low", "High", "Stable", "Headroom < $480m two months (new)"], ["2", "Loss of a top-10 account", "CCO", "Medium", "High", "Rising", "Escalations open > 60 days (new)"], ["3", "Input-cost volatility", "COO", "High", "Medium", "Stable", "Pass-through < 70%"], ["4", "Electrification transition slower / faster than plan", "CEO", "Medium", "High", "Rising", "Installed-base mix quarterly"], ["5", "Distributor consolidation", "Head of Sales", "Medium", "Medium", "Rising", "Top-5 distributor share"], ["6", "Quality escape", "COO", "Medium", "High", "Stable", "Returns rate"], ["7", "Cyber incident", "CIO", "Medium", "High", "Stable", "Patch latency"], ["8", "Integration shortfall, 2023 acquisition", "CFO", "High", "Medium", "Stable", "Synergy run-rate"], ["9", "Key-person loss (CCO role has no successor)", "CHRO", "Medium", "Medium", "New", "Succession coverage"], ["10", "KPI integrity (undocumented definition changes)", "CFO", "Medium", "Medium", "New", "Definition change log"]]
    docs["12_Internal_Audit_and_Risk_Reports.docx"] = mk("Internal audit and risk reports", name, period, [
        ("h", "Risk register (top 10 of 18)"), ("t", risks),
        ("h", "Early-warning dashboard"), ("p", "Introduced in Q-1 with nine indicators; liquidity triggers and customer escalation indicators were added at Meeting 4. The dashboard is reviewed by the Audit Committee quarterly and by the full board twice a year."),
        ("h", "Internal audit findings (year to date)"), ("t", [["Audit", "Rating", "Finding", "Management response", "Status"], ["KPI governance", "Significant", "Pipeline conversion definition changed in Q-2 without documentation or disclosure to the board", "Definition change log introduced; changes to be footnoted in the pack", "Open; due next quarter"], ["Customer complaints handling", "Moderate", "Root-cause analysis not performed for 40% of quality complaints", "Process redesigned; staffed from Q+1", "Open"], ["Treasury controls", "Satisfactory", "No findings", "-", "Closed"], ["Capital project governance", "Moderate", "No post-investment review for the 2022 acquisition despite committee request", "Review scheduled for next year", "Open; overdue"], ["Delegation of authority compliance", "Satisfactory", "Two instances of pilot spend above BU threshold approved retrospectively", "Reminder issued", "Closed"]]),
    ])
    fact("12_Internal_Audit_and_Risk_Reports.docx", ["6.3", "2.2", "1.3"], "Liquidity and customer triggers in dashboard; undocumented KPI change rated significant; missing PIR flagged overdue", "mixed")

    docs["13_Chair_Notes_Executive_Sessions.docx"] = mk("Chair's notes from executive sessions (summary record)", name, period, [
        ("n", "Informal notes kept by the Chair; circulated to independent directors only. Not minutes."),
        ("h", "Session following Meeting 2"), ("b", ["Directors broadly welcomed the volume-assumption revision and the decision to defer the bolt-on. Two directors said the board should have pressed for a flat-volume case; the minority view is recorded in the minutes at their request and the Chair confirmed it will be revisited at Meeting 4.", "Several directors asked why the reinvestment case for electrification never seems to be developed to the same standard as returns-of-capital proposals. The Chair undertook to raise this with the CEO and CFO.", "Directors agreed the external speaker added value; ask for one per half-year."]),
        ("h", "Session following Meeting 3"), ("b", ["The buyback decision was discussed candidly. Directors D and F explained their abstentions: not opposition to the buyback as such, but to approving it without the alternative the board had asked for. Other directors accepted the point. The Chair committed that no future buyback or dividend increase would come to the board without a costed reinvestment alternative alongside, and will put this to management as a standing requirement.", "Directors noted that the pilot review had been useful and asked that it become an annual item.", "No director sought to reopen the plan approval; the volume debate is channelled into the agreed revisit.", "Concern raised about the Chief Customer Officer role having no successor given its growing importance; Chair to raise with the CEO."]),
        ("h", "Chair's observations"), ("p", "Challenge in the room is direct and is well received by the CEO. Dissent is recorded and does not resurface outside the agreed process. The recurring weakness is that management's proposals arrive without the alternatives the board has asked for, which the Chair intends to address through the standing requirement above."),
    ])
    fact("13_Chair_Notes_Executive_Sessions.docx", ["4.3", "5.1"], "Candid dissent with abstentions explained; no relitigation; Chair commits to a standing reinvestment-alternative requirement", "up")
    for fn, d in docs.items(): d.save(os.path.join(folder, fn))
    # action tracker xlsx
    wb = Workbook(); ws = wb.active; ws.title = "Prior actions"
    ws.append(["Action id", "Heading", "Target by", "Measures", "Status (simulated)", "Evidence in documents"])
    for a in prior_actions:
        ws.append([a.get("id"), a.get("heading"), a.get("target_by"), "; ".join(a.get("measures", [])), status_plan[a["id"]], "See 01_Board_Minutes.docx, Meeting 4"])
    ws2 = wb.create_sheet("Metrics tracked"); ws2.append(["Metric", "Q-1", "Q", "Target", "Source"])
    for row in (["Key-customer escalations open > 60 days", 7, 4, 2, "11_Customer_Insight"], ["Free cash flow conversion", "82%", "88%", "90%", "07_Treasury"], ["Liquidity headroom vs floor", "$560m", "$620m", "$400m", "07_Treasury"], ["Board pack pages", 198, 212, 150, "03_Board_Pack"]): ws2.append(row)
    wb.save(os.path.join(folder, "14_Action_Tracker_and_Metrics.xlsx"))
    # questionnaire with simulated answers
    subprocess.run([sys.executable, os.path.join(HERE, "build_questionnaire.py"), name, os.path.join(folder, "15_Self_Assessment_Questionnaire_FILLED.docx"), "--simulate-answers", sys.argv[1]], check=True)
    json.dump(manifest, open(os.path.join(folder, "manifest.json"), "w"), indent=1)
    zpath = os.path.join(out, f"{name.replace(' ', '_')}_inside_out_SIMULATED.zip")
    with zipfile.ZipFile(zpath, "w", zipfile.ZIP_DEFLATED) as z:
        for fn in sorted(os.listdir(folder)): z.write(os.path.join(folder, fn), arcname=fn)
    print(f"{len(os.listdir(folder))} simulated files in {folder}; zip at {zpath}. Read manifest.json for the planted facts and prior-action statuses.")


if __name__ == "__main__":
    main()
