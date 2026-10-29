"""Pure validation, merge and assembly helpers for the outside-in and inside-out runs (no network, no SDK)."""
from __future__ import annotations

import copy
import datetime as dt
import json
import re
from pathlib import Path

from .settings import FW, IND_IDS, DIMS, PEER_RELATIVE, PERIOD_RE, DATE_RE, CODE_RE, AM_RE, STYLE_RE

# What stands in the run file where a director's answer would otherwise sit (anonymity: the answers are never persisted)
SA_NOTE = "Synthesised from director responses"

def _merge(old, new, keys):
    if old is None: return copy.deepcopy(new)
    out = copy.deepcopy(old)
    for field, v in new.items():
        if field in keys:
            if v:
                idx = {x.get(keys[field]): x for x in out.get(field, [])}
                idx.update({x.get(keys[field]): x for x in v})
                out[field] = list(idx.values())
        elif v not in ("", None, []):
            out[field] = copy.deepcopy(v)
    return out


def _drop(draft, field, key, bad):
    """Remove the draft's items whose key is invalid (wrong code prefix, unknown document or action id), so a
    resubmission that leaves them out can pass: a merge alone would keep them forever."""
    if bad: draft[field] = [x for x in draft.get(field, []) if x.get(key) not in bad]


def _cited(text):
    return [c for g in re.findall(r"\[([^\]]+)\]", text or "") for c in re.split(r"[\s,;]+", g) if CODE_RE.match(c)]


def _dups(xs):
    return sorted({x for x in xs if xs.count(x) > 1})


SEARCHED_RE = re.compile(r"search|quer|looked|checked|reviewed|fetch|retriev|read |10-k|proxy|proxies|8-k|transcript|register|filing|annual report|edgar|sweep", re.I)
STRONG_CLASSES = set(FW["strong_classes"])


def _check_cells(cells, known, ids=IND_IDS, items=None):
    """items (evidence code -> evidence dict) enables the Rule 3 minimum check for outside-in cells."""
    p = []; got = [c.get("id") for c in cells]
    if missing := [i for i in ids if i not in got]: p.append(f"indicators missing: {missing}")
    if d := _dups(got): p.append(f"indicators submitted more than once: {d}")
    for c in cells:
        w = f"indicator {c.get('id')}"
        if not (c.get("rationale") or "").strip(): p.append(f"{w}: rationale is empty")
        if bad := [x for x in (c.get("evidence") or []) + _cited(c.get("rationale")) if x not in known]:
            p.append(f"{w}: cites evidence codes that do not exist {sorted(set(bad))}")
        if c.get("carried_forward"): continue
        if c.get("score") == 0:
            if c.get("na_cause") == "none": p.append(f"{w}: not assessable (score 0) needs an na_cause")
            if c.get("na_cause") == "retrieval-limited":
                r = (c.get("rationale") or "").strip()
                if len(r.split()) < 6 or not SEARCHED_RE.search(r):
                    p.append(f"{w}: retrieval-limited needs a rationale that lists what was searched (Rule 15); search the Rule 15 set before marking it not assessable")
        else:
            if c.get("confidence") == "None": p.append(f"{w}: a score needs confidence High, Medium or Low")
            if not c.get("evidence"): p.append(f"{w}: a score needs at least one evidence item")
            elif items is not None and c.get("score") in (1, 5) and all(x in items for x in c["evidence"]):
                its = [items[x] for x in c["evidence"]]
                strong = any(i.get("evidence_class") in STRONG_CLASSES for i in its)
                docs = {(i.get("document") or "").strip() or x for i, x in zip(its, c["evidence"])}
                if not strong and (len(its) < 2 or len(docs) < 2):
                    p.append(f"{w}: score {c['score']} needs at least 2 evidence items from 2 documents or one strong item (Rule 3); "
                             f"has {len(its)} item(s) from {len(docs)} document(s)")
    return p


def _check_evidence(items, prefix=None):
    p = []; codes = [e.get("code", "") for e in items]
    if d := _dups(codes): p.append(f"evidence codes used more than once: {d}")
    for e in items:
        c = e.get("code", "")
        if prefix and not re.fullmatch(prefix + r"\d{2,3}", c): p.append(f"evidence code {c!r} must use the prefix {prefix} ({prefix}01, {prefix}02, ...)")
        if len((e.get("excerpt") or "").split()) >= 15: p.append(f"{c}: excerpt must be under 15 words verbatim")
        if not DATE_RE.match(e.get("date") or ""): p.append(f"{c}: date must be YYYY-MM-DD, YYYY-MM or YYYY")
        if "evidence_class" in e:
            if e["evidence_class"] == "searched_record":
                if not (e.get("search_log") or "").strip(): p.append(f"{c}: searched_record items need a search_log")
            elif not (e.get("url") or "").strip(): p.append(f"{c}: every item other than searched_record needs the URL (or platform reference) it came from")
            if not (e.get("document") or "").strip(): p.append(f"{c}: document title is empty")
    return p


def _check_actions(actions, period):
    p = []
    if not 1 <= len(actions) <= 5: p.append(f"actions: give one to five (got {len(actions)})")
    for a in actions:
        h = (a.get("heading") or "")[:40]
        if not (a.get("heading") or "").strip() or not (a.get("description") or "").strip(): p.append("each action needs a heading and description")
        if not a.get("measures"): p.append(f"action '{h}': needs measures")
        if not PERIOD_RE.match(a.get("target_by") or "") or a["target_by"] <= period: p.append(f"action '{h}': target_by must be a quarter (YYYY-Qn) after {period}")
        if AM_RE.search(json.dumps(a)): p.append(f"action '{h}': must not reference A&M or its services")
    return p


def _check_text(fields, known):
    bad = sorted({c for t in fields for c in _cited(t) if c not in known})
    p = [f"narrative cites evidence codes that do not exist: {bad}"] if bad else []
    if hits := sorted({m.group(0).lower() for t in fields for m in STYLE_RE.finditer(t or "")}):
        p.append(f"figurative language in the narrative: {hits}. Rewrite those sentences literally, as the Writing rules require: "
                 "no metaphor, idiom or personification. Keep every figure and the finding itself and state the mechanism plainly; "
                 "do not substitute another figure of speech, and paraphrase rather than quote a source's own idiom.")
    return p


def _recent(date, today):
    try:
        d = dt.date.fromisoformat(date if len(date) == 10 else (date + "-01" if len(date) == 7 else ""))
    except ValueError:
        return False
    return 0 <= (today - d).days <= 90


def _cell(c):
    if not c.get("score"):
        return {"score": None, "confidence": None, "evidence": list(c.get("evidence") or []),
                "na_cause": c.get("na_cause") if c.get("na_cause") not in ("none", None) else "retrieval-limited", "rationale": c.get("rationale") or ""}
    return {"score": c["score"], "confidence": c.get("confidence"), "evidence": list(c.get("evidence") or []), "rationale": c.get("rationale") or ""}


def _evidence_item(e, today):
    item = {"document": e.get("document", ""), "doc_type": e.get("doc_type") or "public", "date": e.get("date", ""), "url": e.get("url", ""),
            "excerpt": e.get("excerpt", ""), "evidence_class": e.get("evidence_class", "direct"),
            "source_origin": "provided" if (e.get("url") or "").startswith("provided:") else "public",
            "simulated": False, "recent": _recent(e.get("date") or "", today)}
    if e.get("search_log"): item["search_log"] = e["search_log"]
    return item



def _problem_text(problems):
    return "\n".join(f"- {where}: {msg}" for _, where, msg in problems)


def _calibration(subjects):
    rows = [{"subject": s.name, "comparables": s.data.get("comparables", []),
             "peer_relative_scores": {c["id"]: c["score"] or "not assessable" for c in s.data["indicators"] if c["id"] in PEER_RELATIVE}}
            for s in subjects]
    return ("All subjects in the peer set are now scored. Their comparables and peer-relative scores (3.2, 5.1, 6.1, 6.2) are:\n"
            + json.dumps(rows, indent=1, ensure_ascii=False)
            + "\nCheck your peer-relative scores against this set ('in line with peers' is 3).")


def _synth_check(syn, peers, known, period):
    p = [f"{k} is empty" for k in ("headline", "overall_summary", "what_moved", "peer_position") if not (syn.get(k) or "").strip()]
    if len(syn.get("headline_findings", [])) != 3: p.append("headline_findings must have exactly three items")
    if not 3 <= len(syn.get("key_metrics", [])) <= 6: p.append("key_metrics needs three to six metrics")
    if len(syn.get("peer_summary_lines", [])) != len(peers): p.append(f"peer_summary_lines needs one line per peer ({len(peers)})")
    if missing := [k for k in DIMS + ["7"] if k not in {x.get("key") for x in syn.get("scorecard_headline", [])}]: p.append(f"scorecard_headline missing keys {missing}")
    if missing := [k for k in DIMS if k not in {x.get("dimension") for x in syn.get("peer_row_summary", [])}]: p.append(f"peer_row_summary missing dimensions {missing}")
    tickers = {(x.get("ticker") or "").upper() for x in syn.get("peer_summaries", [])}
    if missing := [s.ticker or s.name for s in peers if (s.ticker or s.name).upper() not in tickers]: p.append(f"peer_summaries missing for {missing}")
    p += _check_actions(syn.get("actions", []), period)
    texts = [syn.get(k) or "" for k in ("headline", "overall_summary", "what_moved", "peer_position")] + syn.get("headline_findings", []) \
        + syn.get("peer_summary_lines", []) + [x.get("text") or "" for x in syn.get("scorecard_headline", []) + syn.get("peer_row_summary", [])] \
        + [x.get("summary") or "" for x in syn.get("peer_summaries", [])] + [a.get("description") or "" for a in syn.get("actions", [])]
    return p + _check_text([t for t in texts if isinstance(t, str)], known)


def _retrieval_notes(subjects):
    """One line per subject: how many searches and fetches its research made (audit trail)."""
    return "; ".join(f"{'Company' if s.role == 'company' else 'Peer'} {s.short}: {getattr(s, 'counts', {}).get('web_search', 0)} searches, "
                     f"{getattr(s, 'counts', {}).get('web_fetch', 0)} fetches" for s in subjects)


def _assemble_oi(ctx, subjects, syn):
    today = ctx["today_date"]; company, peers = subjects[0], subjects[1:]
    evidence = {k: v for s in subjects for k, v in s.evidence(today).items()}
    subs = [s.to_run(today) for s in subjects]
    summaries = {x["ticker"].upper(): x["summary"] for x in syn.get("peer_summaries", [])}
    for s, out in zip(peers, subs[1:]):
        out["summary"] = summaries.get((s.ticker or s.name).upper(), "")
    unavailable = [f"{s.short}: {d}" for s in subjects for d in s.data.get("documents_unavailable", [])]
    period = ctx["period"]
    return {
        "run": copy.deepcopy(ctx["meta"]), "headline": syn.get("headline", ""), "subjects": subs, "evidence": evidence,
        "actions": [{"id": f"{period}-A{n}", **a} for n, a in enumerate(syn.get("actions", []), 1)],
        "coverage": {"documents_unavailable": unavailable, "consistency_result": ctx.get("consistency_result") or "Outside-in run 1",
                     "notes": ctx.get("notes") or _retrieval_notes(subjects)},
        **({"reconciliation": ctx["reconciliation"]} if ctx.get("reconciliation") else {}),
        "overall_summary": {"board": syn.get("overall_summary", "")}, "what_moved": syn.get("what_moved", ""),
        "headline_findings": syn.get("headline_findings", []), "key_metrics": syn.get("key_metrics", []),
        "peer_position": syn.get("peer_position", ""), "peer_summary_lines": syn.get("peer_summary_lines", []),
        "scorecard_headline": {x["key"]: x["text"] for x in sorted(syn.get("scorecard_headline", []), key=lambda x: x["key"])},
        "indicator_summary": {c["id"]: c["summary"] for c in sorted(company.data["indicators"], key=lambda c: IND_IDS.index(c["id"]))},
        "peer_row_summary": {x["dimension"]: x["text"] for x in sorted(syn.get("peer_row_summary", []), key=lambda x: x["dimension"])},
        "change_notes": {}, "prior_actions_status": [],
        "additional_information_needed": syn.get("additional_information_needed", []), "history": [],
    }


def _digest(graded, subjects):
    out = []
    for s, g in zip(subjects, graded["subjects"]):
        c = g["computed"]
        out.append({"name": s.name, "ticker": s.ticker, "role": s.role,
                    "overall": {k: c["overall"]["board"].get(k) for k in ("grade", "label", "numeric_average", "provisional")},
                    "coverage": c["coverage"]["board"],
                    "dimensions": {d: {k: c["dimensions"][d]["board"][k] for k in ("grade", "average", "assessed", "of")} for d in DIMS},
                    "indicators": {i: {k: g["indicators"][i]["board"].get(k) for k in ("score", "confidence", "rationale")} for i in IND_IDS},
                    "dimension_text": {d["dimension"]: d["assessment_text"] for d in s.data["dimensions"]},
                    "limitations": {d["dimension"]: d["limitations"] for d in s.data["dimensions"]},
                    "comparables": s.data.get("comparables", [])})
    ev = {k: f"{v['document']} ({v['date']}): {v['excerpt']}" for k, v in graded["evidence"].items() if k.startswith("E")}
    return json.dumps({"subjects": out, "company_evidence": ev}, indent=1, ensure_ascii=False)


def _route(problems, subjects):
    by = {s.name: [] for s in subjects}; rest = []
    for pr in problems:
        (by[pr[0]] if pr[0] in by else rest).append(pr)
    return by, rest


def _provided(name, documents):
    """Documents the A&M team supplied on the company: read alongside the public record, cited as 'provided: <file>'."""
    blocks = [{"type": "text", "text": f"The A&M team has also supplied {len(documents)} document(s) on {name}, below. Read them alongside the public record. "
               "Where one bears on an indicator, cite it as an evidence item like any other source, with doc_type 'provided document' and url "
               "'provided: <file name>'; the excerpt rule (under 15 words verbatim) applies. They do not replace the web research, and they are "
               "about the company only, not the peers."}]
    for d in documents:
        fname = d.get("name") or "document"
        if d.get("pdf_b64"):
            blocks += [{"type": "text", "text": f"Provided document: {fname}"},
                       {"type": "document", "source": {"type": "base64", "media_type": "application/pdf", "data": d["pdf_b64"]}, "title": fname}]
        elif d.get("text"):
            blocks.append({"type": "text", "text": f'<provided_document file="{fname}">\n{d["text"]}\n</provided_document>'})
    return blocks


def _io_inputs(run, documents, answers, today):
    names = [d[0] for d in FW["inside_out_priority_docs"]]
    items, blocks, extra = {}, [], 14
    for d in documents:
        slot = int(d.get("slot") or 0); fname = d.get("name") or "document"
        if not (d.get("text") or d.get("pdf_b64")):
            continue
        if 1 <= slot <= len(names) and f"IO{slot:02d}" not in items:
            code, label = f"IO{slot:02d}", names[slot - 1]
        else:  # a second file for the same document type, or an unslotted one
            code, label = f"IO{extra:02d}", (f"{names[slot - 1]}: {Path(fname).stem}" if 1 <= slot <= len(names) else Path(fname).stem); extra += 1
        items[code] = {"document": f"{label} (board document)", "doc_type": "board document", "date": today.isoformat(),
                       "url": "", "excerpt": "", "evidence_class": "inside_out", "source_origin": "inside_out",
                       "simulated": False, "recent": True, "file_name": fname}
        if d.get("pdf_b64"):
            blocks += [{"type": "text", "text": f"Document {code}: {label} (file {fname})"},
                       {"type": "document", "source": {"type": "base64", "media_type": "application/pdf", "data": d["pdf_b64"]}, "title": f"{code} {label}"}]
        else:
            blocks.append({"type": "text", "text": f'<document code="{code}" title="{label}" file="{fname}">\n{d["text"]}\n</document>'})
    qs = FW["questionnaire"]; sa = {}
    for k, a in (answers or {}).items():
        n = int(re.sub(r"\D", "", str(k)) or 0)
        if 1 <= n <= len(qs) and (a or "").strip():
            dim, dname, q = qs[n - 1]
            # `excerpt` carries the answers to the model (the digest reads it) and is replaced by SA_NOTE in _assemble_io,
            # so no verbatim answer is written to the run file or reaches a renderer.
            sa[f"SA{n:02d}"] = {"document": f"Director self-assessment, Q{n} ({dname})", "doc_type": "self-assessment",
                                "date": today.isoformat(), "url": "", "excerpt": a.strip(), "evidence_class": "self_assessment",
                                "source_origin": "self_assessment", "simulated": False, "recent": True, "question": q}
    return items, blocks, dict(sorted(sa.items()))


def _io_check(io, oi_cells, known, io_items, sa, prior, period):
    p = _check_cells(io.get("cells", []), known)
    for c in io.get("cells", []):
        if c.get("carried_forward") or not c.get("score"): continue
        w = f"indicator {c.get('id')}"; ev = c.get("evidence") or []
        if not any(x.startswith(("IO", "SA")) for x in ev):
            p.append(f"{w}: a post inside-out score must cite an IO or SA item, or set carried_forward true")
        if ev and all(x.startswith("SA") for x in ev):
            oi = (oi_cells.get(c.get("id")) or {}).get("score")
            if c["score"] > 3 and (oi is None or c["score"] > oi): p.append(f"{w}: self-assessment alone cannot lift a score above 3 (Rule 19)")
            if c.get("confidence") == "High": p.append(f"{w}: a self-assessment-only cell cannot be High confidence (Rule 19)")
    docs = {d.get("code"): d for d in io.get("documents", [])}
    if bad := [c for c in docs if c not in io_items]: p.append(f"documents lists unknown codes {bad}")
    if missing := [c for c in io_items if c not in docs]: p.append(f"documents needs a date and excerpt for {missing}")
    p += _check_evidence(list(docs.values()))
    p += [f"{k} is empty" for k in ("headline", "overall_summary", "what_moved") if not (io.get(k) or "").strip()]
    if len(io.get("headline_findings", [])) != 3: p.append("headline_findings must have exactly three items")
    p += _check_actions(io.get("actions", []), period)
    pids = [a["id"] for a in prior]; got = {x.get("id"): x for x in io.get("prior_actions_status", [])}
    if missing := [i for i in pids if i not in got]: p.append(f"prior_actions_status needs an entry for {missing}")
    if bad := [i for i in got if i not in pids]: p.append(f"prior_actions_status has unknown action ids {bad}")
    behind = [i for i, x in got.items() if x.get("status") in ("behind", "not_started")]
    if missing := [i for i in behind if i not in {b.get("id") for b in io.get("back_on_track", [])}]: p.append(f"back_on_track needs an entry for {missing}")
    texts = [io.get(k) or "" for k in ("headline", "overall_summary", "what_moved")] + io.get("better", []) + io.get("worse", []) \
        + io.get("headline_findings", []) + [x.get("note") or "" for x in io.get("io_change_notes", [])] \
        + [x.get("evidence_note") or "" for x in io.get("prior_actions_status", [])] + [a.get("description") or "" for a in io.get("actions", [])]
    return p + _check_text([t for t in texts if isinstance(t, str)], known)


def _assemble_io(base, io, io_items, sa, prior, ratings, period):
    run = copy.deepcopy(base)
    comp = next(s for s in run["subjects"] if s["role"] == "company")
    for c in io.get("cells", []):
        if c.get("id") not in comp["indicators"]: continue
        oi = comp["indicators"][c["id"]]["board"]
        if c.get("carried_forward"):
            cell = {k: copy.deepcopy(oi.get(k)) for k in ("score", "confidence", "evidence") if k in oi}
            if oi.get("score") is None: cell["na_cause"] = oi.get("na_cause")
            cell.update(rationale=c.get("rationale") or "Carried forward: the board documents add nothing on this indicator.", carried_forward=True)
        else:
            cell = {**_cell(c), "carried_forward": False}
        comp["indicators"][c["id"]]["board_io"] = cell
    docs = {d.get("code"): d for d in io.get("documents", [])}
    for code, item in io_items.items():
        d = docs.get(code) or {}
        run["evidence"][code] = {**item, "date": d.get("date") or item["date"], "excerpt": d.get("excerpt", "")}
    # Anonymity: the run keeps the question and the SA code (so [SA01] citations resolve) but never the answer itself;
    # what a reader sees of the self-assessment is the synthesised themes below.
    for code, item in sa.items():
        run["evidence"][code] = {**copy.deepcopy(item), "excerpt": SA_NOTE}
    heads = {a["id"]: a.get("heading", "") for a in prior}
    notes = [x for x in io.get("io_change_notes", []) if x.get("id") in IND_IDS]
    run.update(headline=io.get("headline", ""), what_moved=io.get("what_moved", ""), headline_findings=io.get("headline_findings", []),
               inside_vs_outside={"better": io.get("better", []), "worse": io.get("worse", [])},
               io_change_notes={x["id"]: x.get("note", "") for x in sorted(notes, key=lambda x: IND_IDS.index(x["id"]))},
               actions=[{"id": f"{period}-A{n}", **a} for n, a in enumerate(io.get("actions", []), 1)],
               prior_actions_status=[{"id": x.get("id"), "heading": heads.get(x.get("id"), ""), "status": x.get("status"), "evidence_note": x.get("evidence_note", ""),
                                      "metrics_note": x.get("metrics_note", "")} for x in io.get("prior_actions_status", [])],
               back_on_track=[{"id": b.get("id"), "heading": heads.get(b.get("id"), ""), **{k: v for k, v in b.items() if k != "id"}} for b in io.get("back_on_track", [])],
               additional_information_needed=io.get("additional_information_needed", []), self_ratings=ratings,
               self_assessment_themes=[{"dimension": str(t.get("dimension")), "theme": t.get("theme", ""), "summary": t.get("summary", "")}
                                       for t in io.get("self_assessment_themes", []) if str(t.get("dimension")) in DIMS],
               self_assessment_responses=run.get("self_assessment_responses", 0))
    run.setdefault("overall_summary", {})["board_io"] = io.get("overall_summary", "")
    # Peers are never re-scored or re-written inside-out (Rule 17): their cells, page summary and the peer narrative are the
    # outside-in ones verbatim, whatever the model returns. Restoring them here keeps the two stages identical by construction.
    for i, src in enumerate(base.get("subjects", [])):
        if src.get("role") == "peer": run["subjects"][i] = copy.deepcopy(src)
    for k in ("peer_position", "peer_summary_lines", "peer_row_summary"):
        if k in base: run[k] = copy.deepcopy(base[k])
    return run

