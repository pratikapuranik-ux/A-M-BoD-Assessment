"""Which file is which: the document register.

A file name says little ('10-Q 0001138118-26-000005.pdf' is a 10-K, 'JLL_Annual-Report_2026_FINAL.pdf' is the 2025 report, '24241711-c95e-....pdf'
is a proxy). A&M keeps a register (an Excel file) that gives every supplied file its real identity: category, what it really is, period,
document date, the label to cite it by, whether to use it, and a flag when something is off. This module does the same job in two ways:

  * identify(): reads the cover page and works out the identity itself, for files nobody has registered;
  * the register (from_xlsx / apply): when a register is among the uploaded files, its rows win over file names and over identify().

apply() also drops what must not be read as evidence (a file filed under the wrong company, a duplicate copy), and gaps() lists what the
skill expects but the upload lacks. The identity travels with each document as d["ident"]; prompts show it and evidence cites the label.
"""
from __future__ import annotations

import io
import os
import re
from collections import Counter

from app.services import doclearn, subjects as subj

MAX_ASKS = 60  # model calls per run to identify files nothing else could place
CATEGORIES = ("Annual filing", "Annual filing exhibit", "Quarterly filing", "Proxy / circular", "Transcript", "Press release", "Presentation",
              "Excel supplement", "Annual / ESG report", "Other")
HEAD_TITLES = ("Company", "Folder (zip)", "File name as it is today", "Category", "What it really is", "Period", "Document / event date", "Cite as", "Pages", "Text readable?", "Use?", "Flag", "Note")
HEAD = ("company", "file name as it is today", "category", "what it really is", "period", "document / event date", "cite as", "pages",
        "text readable?", "use?", "flag", "note")
MONTH = {m: i for i, m in enumerate("january february march april may june july august september october november december".split(), 1)}
DATE_RE = re.compile(r"\b(January|February|March|April|May|June|July|August|September|October|November|December)\s+(\d{1,2}),?\s+(20\d\d)\b", re.I)
CODE_NAME = re.compile(r"^(?:[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}|[0-9a-f]{24,}|\d{10}-\d{2}-\d{6})$", re.I)
KINDS = {"slide": "slides", "presentation": "slides", "deck": "slides", "transcript": "call", "press release": "release", "earnings release": "release",
         "results": "release", "10-k": "10-K", "10k": "10-K", "10-q": "10-Q", "10q": "10-Q", "40-f": "40-F", "def14a": "proxy", "def 14a": "proxy",
         "proxy": "proxy", "supplement": "supplement", "annual report": "annual report", "annual-report": "annual report", "sustainab": "sustainability statement",
         "responsib": "CR report"}
KIND_CAT = {"10-K": "Annual filing", "40-F": "Annual filing", "10-Q": "Quarterly filing", "proxy": "Proxy / circular", "call": "Transcript", "release": "Press release",
            "slides": "Presentation", "supplement": "Excel supplement", "annual report": "Annual / ESG report", "sustainability statement": "Annual / ESG report", "CR report": "Annual / ESG report"}


# ---------------------------------------------------------------- the register file

def from_xlsx(raw: bytes) -> list[dict] | None:
    """The rows of a document register, or None when the workbook is not one. A register has a header row with 'File name as it is today' and 'Cite as'."""
    try:
        from openpyxl import load_workbook
        wb = load_workbook(io.BytesIO(raw), read_only=True, data_only=True)
    except Exception:  # noqa: BLE001
        return None
    for ws in wb.worksheets:
        cols = None; rows: list[dict] = []
        for k, r in enumerate(ws.iter_rows(values_only=True)):
            cells = ["" if v is None else str(v).strip() for v in r]
            if cols is None:
                low = [c.lower() for c in cells]
                if "cite as" in low and "file name as it is today" in low: cols = {h: low.index(h) for h in HEAD if h in low}
                elif k > 8: break
                continue
            row = {h: (cells[i] if i < len(cells) else "") for h, i in cols.items()}
            if row.get("file name as it is today") and row.get("company"): rows.append(row)
        if rows: return rows
    return None


# ---------------------------------------------------------------- reading a cover page

def _period_of_date(m: re.Match) -> tuple[str, int]:
    mon, year = MONTH[m.group(1).lower()], int(m.group(3))
    return f"Q{(mon - 1) // 3 + 1} {year}", year


def _quarter(s: str) -> str:
    s = s.replace("_", " ")
    for pat, order in ((r"\bq([1-4])[\s_-]*(20\d\d)\b", "qy"), (r"\b(20\d\d)[\s_-]*q([1-4])\b", "yq"), (r"\b([1-4])q[\s_-]*(20)?(\d\d)\b", "qyy"),
                       (r"\b(first|second|third|fourth)[\s-]+quarter[^0-9]{0,40}(20\d\d)", "word"), (r"\bq([1-4])[\s_-]*(\d\d)\b", "qy2")):
        m = re.search(pat, s, re.I)
        if not m: continue
        if order == "qy": return f"Q{m.group(1)} {m.group(2)}"
        if order == "yq": return f"Q{m.group(2)} {m.group(1)}"
        if order == "qyy": return f"Q{m.group(1)} 20{m.group(3)}"
        if order == "word": return f"Q{['first', 'second', 'third', 'fourth'].index(m.group(1).lower()) + 1} {m.group(2)}"
        return f"Q{m.group(1)} 20{m.group(2)}"
    return ""


def _years(s: str) -> list[str]:
    return re.findall(r"\b(20[12]\d)\b", s)


def kind_of_name(name: str) -> str:
    n = re.sub(r"[_]+", " ", name.lower())
    for k, v in KINDS.items():
        if k in n: return v
    return ""


def _proxy_year(head: str, base: str) -> tuple[str, str]:
    """(period, date) of a proxy: the meeting date after 'annual meeting', else the first full date on the cover, else a year in the file name."""
    m = re.search(r"annual\s+(?:and\s+special\s+)?meeting[^.]{0,300}?(January|February|March|April|May|June|July|August|September|October|November|December)\s+(\d{1,2}),?\s+(20\d\d)", head, re.I | re.S) or DATE_RE.search(head)
    if m: return f"{m.group(3)} annual meeting", f"Meeting {m.group(2)} {m.group(1).title()[:3]} {m.group(3)}"
    y = (_years(base) or _years(head) or [""])[0]
    return (f"{y} annual meeting" if y else ""), ""


def identify(name: str, text: str, ext: str | None = None) -> dict:
    """What a file really is, from its cover page (and its name only where the cover is silent): category, what, period, date, kind (the
    short word used in the cite-as label), and flags. Heuristic: a register, when there is one, overrides it."""
    ext = (ext or os.path.splitext(name)[1]).lower(); base = os.path.splitext(os.path.basename(name))[0]
    head = (text or "")[:7000]; H = head.upper(); top = H[:900]
    flags: list[str] = []; cat = "Other"; what = ""; period = ""; date = ""; kind = ""
    first = DATE_RE.search(head); fdate = f"{first.group(2)} {first.group(1).title()[:3]} {first.group(3)}" if first else ""
    fy = re.search(r"fiscal\s+year\s+ended\s+([A-Za-z]+\s+\d{1,2},?\s+(20\d\d))", head, re.I)
    qe = re.search(r"(?:quarterly\s+period|quarter|three\s+months|six\s+months|nine\s+months)\s+ended\s+([A-Za-z]+)\s+(\d{1,2}),?\s+(20\d\d)", head, re.I)
    cover = "SECURITIES AND EXCHANGE COMMISSION" in H[:1500]
    pres = ext == ".pptx" or bool(re.search(r"slide|presentation|\bdeck\b", base, re.I)) and not re.search(r"transcript", base, re.I)
    if pres: cat, what, kind = "Presentation", "Earnings presentation", "slides"; period = _quarter(base) or _quarter(head)
    elif cover and re.search(r"\bFORM\s+10-K\b", H[:3000]) and "ANNUAL REPORT" in H[:3000]:
        cat, what, kind = "Annual filing", "Form 10-K (annual report)", "10-K"
        yr = fy.group(2) if fy else (_years(head) or [""])[0]; period = f"FY {yr} (year ended {fy.group(1).replace(',', '')})" if fy else f"FY {yr}"
    elif cover and re.search(r"\bFORM\s+10-Q\b", H[:3000]):
        cat, what, kind = "Quarterly filing", "Form 10-Q", "10-Q"
        if qe and qe.group(1).title() in {k.title() for k in MONTH}:
            q, _ = _period_of_date(re.search(r"(January|February|March|April|May|June|July|August|September|October|November|December)\s+(\d{1,2}),?\s+(20\d\d)", qe.group(0), re.I))
            period = f"{q} (quarter ended {qe.group(2)} {qe.group(1)[:3].title()} {qe.group(3)})"
    elif cover and re.search(r"\bFORM\s+40-F\b", H[:3000]): cat, what, kind = "Annual filing", "Form 40-F (main document)", "40-F"; period = f"FY {(_years(head) or [''])[0]}"
    elif re.search(r"\bSCHEDULE\s+14A\b|\bPROXY\s+STATEMENT\b|\bMANAGEMENT\s+INFORMATION\s+CIRCULAR\b|\bNOTICE\s+OF\s+(?:THE\s+)?ANNUAL\s+(?:AND\s+SPECIAL\s+)?MEETING\b", H[:5000]):
        cat, what, kind = "Proxy / circular", "Proxy statement", "proxy"
        period, date = _proxy_year((text or "")[:90000], base)  # the cover has no meeting date; the notice a few pages in does
    elif ext == ".pdf" and (re.search(r"MANAGEMENT.S DISCUSSION AND ANALYSIS", top) or re.search(r"CONSOLIDATED FINANCIAL STATEMENTS", top)) and ext == ".pdf":
        mdna = "DISCUSSION AND ANALYSIS" in top
        cat, kind = ("Annual filing exhibit", "MD&A" if mdna else "financial statements"); what = "Management's Discussion & Analysis" if mdna else "Consolidated financial statements"
        if "INTERIM" in top or "UNAUDITED" in top: cat = "Quarterly filing"; what = ("Interim " + what[0].lower() + what[1:]) + (" (unaudited)" if not mdna else "")
        period = _quarter(head) or (f"FY {(_years(head) or [''])[0]}" if _years(head) else "")
    elif re.search(r"\bCORRECTED\s+TRANSCRIPT\b|\bEARNINGS\s+(?:CALL|CONFERENCE\s+CALL)\b.{0,400}\b(?:OPERATOR|PRESENTATION)\b|\bQ[1-4]\s+20\d\d\s+EARNINGS\s+CALL\b", H[:4000], re.S) or "TRANSCRIPT" in base.upper():
        cat, what, kind = "Transcript", "Earnings call transcript", "call"; period = _quarter(head) or _quarter(base)
        if first: date = f"{first.group(2)} {first.group(1).title()[:3]} {first.group(3)}"
    elif ext == ".xlsx": cat, what, kind = "Excel supplement", "Financial supplement (Excel)", "supplement"; period = _quarter(base) or _quarter(head)
    elif re.search(r"EXHIBIT\s+99\.1|FOR\s+IMMEDIATE\s+RELEASE|(REPORTS|ANNOUNCES)[^.]{0,80}(QUARTER|RESULTS)", H[:2500]) or re.search(r"release|press", base, re.I):
        cat, what, kind = "Press release", "Earnings press release" + (" (Ex. 99.1)" if "EXHIBIT 99.1" in H[:2500] else ""), "release"; period = _quarter(base) or _quarter(head)
    elif kind_of_name(base) in ("annual report", "sustainability statement", "CR report") or re.search(r"CORPORATE\s+RESPONSIBILITY|SUSTAINABILITY|ESG\s+REPORT|ANNUAL\s+REPORT", H[:3000]):
        cat = "Annual / ESG report"; nk = kind_of_name(base)
        if nk == "sustainability statement" or not nk and re.search(r"SUSTAINABILITY", H[:3000]): what, kind = "Sustainability statement", "sustainability statement"
        elif nk == "CR report" or not nk and re.search(r"CORPORATE\s+RESPONSIBILITY|ESG", H[:3000]): what, kind = "Corporate responsibility report", "CR report"
        else: what, kind = "Annual report (shareholder edition)", "annual report"
        cover = Counter(_years(head[:2500])); period = f"FY {cover.most_common(1)[0][0]}" if cover else ""
    sure = bool(what)  # the cover page decided; otherwise what was learned from registers, or a model, may still
    if not what:  # the cover says nothing usable: fall back on the file name
        k = kind_of_name(base); cat = KIND_CAT.get(k, "Other"); kind = k; what = cat if k else "Not identified from its first page"
        period = _quarter(base) or (f"FY {_years(base)[0]}" if k in ("10-K", "40-F", "annual report") and _years(base) else "")
        if k == "proxy": period = _proxy_year("", base)[0]
        if not k or not (text or "").strip(): flags.append("Not identified from its cover" if not k else "No readable cover page")
    if not date and cat in ("Press release", "Transcript", "Presentation") and fdate: date = fdate
    if CODE_NAME.match(base) or re.fullmatch(r"[0-9a-f-]{20,}", base, re.I) or re.fullmatch(r"\d{10}-\d{2}-\d{6}", base): flags.append("Unnamed (code file name)")
    nk = kind_of_name(base)
    if nk in ("10-K", "10-Q", "40-F") and kind in ("10-K", "10-Q", "40-F", "MD&A", "financial statements") and nk != kind: flags.append("Misnamed")
    elif "md&a" in base.lower() and kind not in ("MD&A", "") : flags.append("Misnamed")
    nyear = _years(base); cyear = _years(period)
    if cat == "Annual / ESG report" and nyear and cyear and nyear[0] not in cyear: flags.append("Misnamed")
    return {"category": cat, "what": what, "period": period, "date": date, "kind": kind, "flag": flags, "cite_as": "", "use": "Use", "note": "", "source": "cover page", "sure": sure}


def kind_of_row(row: dict) -> str:
    """The short kind word a register row implies (10-K, proxy, call, ...), from its cite-as label and its description."""
    s = f"{row.get('cite as', '')} {row.get('what it really is', '')}".lower()
    for k, v in (("10-k", "10-K"), ("10-q", "10-Q"), ("40-f", "40-F"), ("proxy", "proxy"), ("circular", "proxy"), ("call", "call"), ("transcript", "call"), ("release", "release"),
                 ("slides", "slides"), ("presentation", "slides"), ("supplement", "supplement"), ("md&a", "MD&A"), ("financial statements", "financial statements"),
                 ("sustainability", "sustainability statement"), ("cr report", "CR report"), ("corporate responsibility", "CR report"), ("annual report", "annual report")):
        if k in s: return v
    return ""


def cite_as(who: str, ident: dict) -> str:
    """The label a document is cited by: 'CBRE 10-Q Q1 2026', 'JLL 2026 proxy', 'CBRE Q3 2026 call'."""
    k, p = ident.get("kind") or "", ident.get("period") or ""
    q = re.search(r"Q[1-4] 20\d\d", p); fy = re.search(r"FY\s*(20\d\d)", p); yr = re.match(r"(20\d\d) annual meeting", p)
    if k == "10-K": tail = f"FY{fy.group(1)} 10-K" if fy else "10-K"
    elif k == "10-Q": tail = f"10-Q {q.group(0)}" if q else "10-Q"
    elif k == "proxy": tail = f"{yr.group(1)} proxy" if yr else "proxy"
    elif k in ("call", "release", "slides", "supplement"): tail = f"{q.group(0)} {k}" if q else k
    elif k in ("sustainability statement", "CR report", "annual report"): tail = f"{(fy.group(1) if fy else (_years(p) or [''])[0])} {k}".strip()
    elif q: tail = f"{q.group(0)} {ident.get('what') or k}".strip()
    else: tail = ident.get("what") or ident.get("name") or "document"
    return f"{who} {tail}".strip()


# ---------------------------------------------------------------- applying it to an upload

def _who(s: dict) -> str:
    t = (s.get("ticker") or "").strip()
    if t and len(t) <= 5 and t.isalpha(): return t.upper()
    n = re.sub(r"\b(Inc|Incorporated|Corporation|Corp|Group|Holdings|plc|Ltd|Limited|Company|Co|N\.?V|S\.?A|AG|SE)\b\.?", "", s.get("name", ""), flags=re.I)
    return re.sub(r"\s+", " ", n).strip(" ,.") or s.get("name", "")


def _subject_of(company: str, subs: list[dict]) -> int | None:
    for i, s in enumerate(subs):
        if subj._match(company, s.get("name", ""), s.get("ticker", "")): return i
    return None


def _taken_by(name: str, subs: list[dict], i: int) -> int | None:
    """The other subject a file's name points at ('Q1-2026-JLL-Supplemental...' in the CBRE folder), when it does not name its own."""
    n = subj.norm(name)
    def hit(s):
        for t in (subj.norm(s.get("ticker", "")), subj.norm(s.get("name", ""))):
            if len(t) >= 3 and t in n: return True
        return False
    if hit(subs[i]): return None
    return next((j for j, s in enumerate(subs) if j != i and hit(s)), None)


def apply(docs: list[dict], company: dict, peers: list[dict], rows: list[dict] | None = None, ask=None, learn: bool = True) -> tuple[list[dict], list[dict], list[str]]:
    """Gives every document its identity (d['ident']). Returns (kept, ignored, notes): documents to read, documents set aside (each with an
    'ident' carrying use='Ignore (reason)'), and plain-language notes for the run log.
    Order of authority: the register, then the cover page, then what earlier registers taught (doclearn), then a model shown the closest lessons (`ask`).
    Every file a register describes is learned from (`learn`)."""
    subs = [company] + list(peers); kept: list[dict] = []; ignored: list[dict] = []; notes: list[str] = []; asked = 0; lessons = 0
    by_base: dict[str, list[tuple[int | None, dict]]] = {}
    for r in rows or []: by_base.setdefault(os.path.basename(r["file name as it is today"]).lower(), []).append((_subject_of(r["company"], subs), r))
    for d in docs:
        i = int(d.get("subject") or 0); base = os.path.basename(d.get("name") or "")
        ident = identify(d.get("name") or "", d.get("text") or "")
        fp = doclearn.fingerprint(d.get("name") or "", d.get("text") or "")
        if not ident.pop("sure") and (d.get("text") or "").strip():  # the cover rules could not place it: use what was learned, then ask
            got, conf = doclearn.classify(fp); how = "learned from earlier registers"
            if not got and ask and asked < MAX_ASKS: asked += 1; got = doclearn.ask_model(d.get("name") or "", d.get("text") or "", fp, CATEGORIES, ask); how = "read by a model, with earlier registers as examples"
            if got:
                ident.update(category=got["category"], what=got["what"] or ident["what"], kind=got["kind"] or ident["kind"], source=how)
                ident["flag"] = [f for f in ident["flag"] if not f.startswith("Not identified")]
                if not ident["period"]: ident["period"] = _quarter(os.path.basename(d.get("name") or "")) or _quarter(d["text"][:7000]) or (_proxy_year(d["text"][:90000], os.path.basename(d["name"]))[0] if got["kind"] == "proxy" else "")
        if d.get("transcribed") or (d.get("needs_ocr") and not d.get("text")): ident["flag"].append("No text layer (read by OCR)")
        match = by_base.get((base or "").lower()) or []
        mine = next((r for s, r in match if s == i), None) or (match[0][1] if len(match) == 1 and match[0][0] is None else None)
        if mine:
            for k, h in (("category", "category"), ("what", "what it really is"), ("period", "period"), ("date", "document / event date"), ("cite_as", "cite as"), ("note", "note")):
                if mine.get(h): ident[k] = mine[h]
            ident["use"] = mine.get("use?") or "Use"; ident["source"] = "register"
            ident["flag"] = [f.strip() for f in (mine.get("flag") or "").split(";") if f.strip()]
            ident["kind"] = kind_of_row(mine) or ident["kind"]
            if learn and ident["use"].lower().startswith("use") and (d.get("text") or "").strip() and doclearn.learn(fp, ident): lessons += 1
        elif match:  # registered, but under another company: it sits in the wrong folder
            ident["use"] = "Ignore (misfiled)"; ident["source"] = "register"; ident["note"] = f"The register lists this file under {match[0][1]['company']}, not under {_who(subs[i])}."
        elif rows:
            ident["note"] = "Not in the register: identified from its first page."
        if not ident["cite_as"]:
            ident["cite_as"] = cite_as(_who(subs[i]), ident) if ident["category"] != "Other" else f"{_who(subs[i])} {os.path.splitext(base)[0]}"  # unplaced: cited by its own name
        other = _taken_by(base, subs, i)
        if other is not None and ident["use"] == "Use" and not mine:
            ident["use"] = "Ignore (misfiled)"; ident["note"] = f"The file name points at {_who(subs[other])}; it sits in {_who(subs[i])}'s folder."
        d["ident"] = ident
    # the same bytes twice, or the same document under two names: keep one, the one with more pages
    seen: dict[tuple, dict] = {}
    for d in docs:
        ident = d["ident"]
        if not ident["use"].lower().startswith("use"): continue
        by_label = ("cite", int(d.get("subject") or 0), ident["cite_as"].lower()) if ident["category"] != "Other" and ident["period"] else None  # one label = one document, only when it names a period
        key = ("sha", d["sha"]) if d.get("sha") else by_label
        if key is None: continue
        for k in (key, by_label):
            if k is None: continue
            if k in seen:
                a, b = seen[k], d
                lose = b if (a.get("pages") or 0) >= (b.get("pages") or 0) else a
                lose["ident"]["use"] = "Ignore (duplicate)"; lose["ident"]["flag"] = list(dict.fromkeys(lose["ident"]["flag"] + ["Two copies"]))
                lose["ident"]["note"] = lose["ident"]["note"] or f"Same document as {(a if lose is b else b)['name']}; the longer copy is used."
                if lose is a: seen[k] = b
                break
        else:
            seen[key] = d
            if by_label: seen[by_label] = d
    if lessons: notes.append(f"Learned from the register: {lessons} new example(s) of how a document type looks; they are used to identify unlabelled files in future runs")
    labels: Counter = Counter()
    for d in docs:
        ident = d["ident"]
        if ident["use"].lower().startswith("use"):
            labels[(int(d.get("subject") or 0), ident["cite_as"])] += 1
            if labels[(int(d.get("subject") or 0), ident["cite_as"])] > 1: ident["cite_as"] += f" ({labels[(int(d.get('subject') or 0), ident['cite_as'])]})"
            kept.append(d)
        else:
            ignored.append(d); notes.append(f"{d['name']}: set aside ({ident['use']}). {ident['note']}".strip())
    for d in kept:
        f = [x for x in d["ident"]["flag"] if x != "Two copies"]
        if f and d["ident"]["source"] != "register": notes.append(f"{d['name']}: read as {d['ident']['cite_as']} ({'; '.join(f)})")
        elif d["ident"]["source"] == "register" and any(x.startswith(("Misnamed", "Unnamed")) for x in f): notes.append(f"{d['name']}: the register says this is {d['ident']['cite_as']} ({d['ident']['what']}); read as that, not by its file name")
    return kept, ignored, notes


# ---------------------------------------------------------------- what is missing

def gaps(kept: list[dict], names: list[str]) -> list[dict]:
    """What the skill looks for and the upload lacks, per subject: annual filing, three proxies, four earnings call transcripts, a recent quarter."""
    out: list[dict] = []
    for i, name in enumerate(names):
        mine = [d for d in kept if int(d.get("subject") or 0) == i]
        if not mine: continue
        n = Counter(d["ident"]["category"] for d in mine)
        if not n["Annual filing"]: out.append({"subject": name, "gap": "No annual filing (10-K or 40-F)", "why": "Five years of cash flows (R1) and the strategy and risk sections need one; the web search will be used instead."})
        if n["Proxy / circular"] < 3: out.append({"subject": name, "gap": f"{n['Proxy / circular'] or 'No'} proxy statement{'s' if n['Proxy / circular'] != 1 else ''} (three expected)", "why": "Board composition, tenure, pay and governance (R2) read best from the last three; earlier years will be searched on the web."})
        if n["Transcript"] < 4: out.append({"subject": name, "gap": f"{n['Transcript'] or 'No'} earnings call transcript{'s' if n['Transcript'] != 1 else ''} (four expected)", "why": "Management's stated priorities and decisions are read from the calls; this subject will be thinner than peers that have them."})
    return out


def label(d: dict) -> str:
    """How a document is named to the model: the label to cite it by, what it really is, and the file it sits in."""
    i = d.get("ident")
    if not i: return d.get("name") or "document"
    bits = [x for x in (i.get("what"), i.get("period"), i.get("date")) if x]
    return f"{i['cite_as']} ({'; '.join(bits)}; file {d.get('name')})" if bits else f"{i['cite_as']} (file {d.get('name')})"


def sheet_tag(d: dict) -> str:
    """The opening tag of a document's fact sheet, with the label to cite it by."""
    i = d.get("ident")
    return f'<fact_sheet file="{d.get("name")}"' + (f' cite_as="{i["cite_as"]}" what="{i.get("what", "")}" period="{i.get("period", "")}"' if i else "") + ">"
