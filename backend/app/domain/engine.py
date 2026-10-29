"""Grading engine (rules v1.2, board-only): port of skill/scripts/grade.py and load_history.py plus the js/engine.js and
js/rules.js helpers (inside-out re-scoring, trend history, prior-action status, guardrail language scan).

Pure logic, no I/O. `grade()` returns problem strings formatted "[<code>] <subject>: <text>", the format the legacy
pipeline parsed from grade.py's BLOCK / WARN lines.
"""
from __future__ import annotations

import copy
import re
from typing import Any, Iterable

from .skill import (DIM_OF, DIMS, FW, IND_IDS, LV, VL, company_of, label_of, lenses_for, meets, period_label, peers_of,
                    round_midpoint_down, stage_of, to_grade)

STRONG = set(FW["strong_classes"])
WEAK = {"searched_record", "silence"}
CAPPED: dict[str, int] = dict(FW["silence_capped"])
CAPPED.update(FW["searched_record_capped"])

Issue = tuple[str, str, str]  # (code, subject, text)


def _fmt(items: Iterable[Issue]) -> list[str]:
    return [f"[{a}] {b}: {c}" for a, b, c in items]


# ------------------------------------------------------------------ validation

def validate_cell(name: str, iid: str, lens: str, cell: dict | None, evidence: dict, problems: list, warnings: list, stage: str = "outside_in") -> None:
    where = f"{iid}/{lens}"
    if cell is None or cell.get("score") is None:
        if (cell or {}).get("na_cause") not in FW["na_causes"]:
            problems.append((name, where, f"not assessable: na_cause must be one of {FW['na_causes']}"))
        if not ((cell or {}).get("rationale") or "").strip():
            problems.append((name, where, "not assessable: rationale must list what was searched (Rule 15)"))
        return
    s = cell["score"]
    if s not in (1, 2, 3, 4, 5):
        problems.append((name, where, f"score {s!r} is not an integer 1-5"))
        return
    ev = cell.get("evidence", []) or []
    missing = [e for e in ev if e not in evidence]
    if missing:
        problems.append((name, where, f"evidence ids not in evidence list: {missing}"))
        return
    items = [evidence[e] for e in ev]
    classes = [it.get("evidence_class", "direct") for it in items]
    bad = [c for c in classes if c not in FW["evidence_classes"]]
    if bad:
        problems.append((name, where, f"unknown evidence_class {bad}"))
    if lens == "board_io":
        io = [c for c in classes if c in ("inside_out", "self_assessment")]
        if not io and not cell.get("carried_forward"):
            problems.append((name, where, "post inside-out score must cite at least one inside_out or self_assessment item, or set carried_forward: true with the outside-in score unchanged"))
        if classes and all(c == "self_assessment" for c in classes) and cell.get("confidence") == "High":
            problems.append((name, where, "self-assessment-only cell cannot be High confidence (Part D)"))
    else:
        if any(c in ("inside_out", "self_assessment") for c in classes):
            problems.append((name, where, "outside-in cell may not cite inside_out or self_assessment evidence"))
    docs = {it.get("document", e) for it, e in zip(items, ev)}
    strong = any(c in STRONG or c == "inside_out" for c in classes)
    if s in (1, 5) and not strong and (len(ev) < 2 or len(docs) < 2):
        problems.append((name, where, f"score {s} needs >=2 items from >=2 documents or one strong item (has {len(ev)}/{len(docs)})"))
    if s in (2, 3, 4) and len(ev) < 1:
        problems.append((name, where, f"score {s} needs >=1 evidence item"))
    if s in (2, 4) and not (cell.get("rationale") or "").strip():
        problems.append((name, where, f"score {s} requires a rationale naming the parts of both anchors met"))
    if not (cell.get("rationale") or "").strip():
        warnings.append((name, where, "rationale is empty; outputs show rationale, not raw evidence"))
    only_weak = bool(classes) and all(c in WEAK for c in classes)
    if only_weak:
        if iid in CAPPED and s > CAPPED[iid]:
            problems.append((name, where, f"only silence/searched-record evidence: score capped at {CAPPED[iid]}"))
        elif iid not in CAPPED and iid not in FW["silence_full"]:
            problems.append((name, where, "silence/searched-record evidence is not scorable for this indicator"))
        if cell.get("confidence") != "Low":
            problems.append((name, where, "silence/searched-record-only cell must be Low confidence"))
    for it in items:
        if it.get("evidence_class") == "searched_record" and not it.get("search_log"):
            problems.append((name, where, "searched_record item needs search_log"))
    conf = cell.get("confidence")
    if conf not in ("High", "Medium", "Low"):
        problems.append((name, where, "confidence must be High, Medium or Low"))
    elif conf == "High":
        direct = sum(1 for c in classes if c in ("direct", "strong_direct", "board_act", "inside_out"))
        if not (direct >= 2 or strong):
            warnings.append((name, where, "High confidence needs >=2 direct items or one strong item"))


def validate_subject(subj: dict, evidence: dict, lenses: list[str], problems: list, warnings: list, stage: str = "outside_in") -> None:
    name = subj.get("name", "?")
    inds = subj.get("indicators", {}) or {}
    use = lenses if subj.get("role") == "company" else ["board"]
    for iid in IND_IDS:
        if iid not in inds:
            problems.append((name, iid, "missing indicator block"))
            continue
        for lens in use:
            validate_cell(name, iid, lens, inds[iid].get(lens), evidence, problems, warnings, stage)
    for a, b in FW["scoped_pairs"]:
        for lens in use:
            ea = set((inds.get(a, {}).get(lens) or {}).get("evidence", []) or [])
            eb = set((inds.get(b, {}).get(lens) or {}).get("evidence", []) or [])
            if ea & eb:
                problems.append((name, f"{a}/{b} ({lens})", f"evidence {sorted(ea & eb)} primary in both indicators of a scoped pair"))


def validate_run(run: dict, evidence_only: bool = False) -> tuple[list[Issue], list[Issue]]:
    """Run-level and subject-level rule checks (js validateRun + grade.py main). Does not compute."""
    problems: list[Issue] = []
    warnings: list[Issue] = []
    evidence = run.get("evidence", {}) or {}
    meta = run.get("run", {}) or {}
    stage = stage_of(run)
    if stage not in FW["stages"]:
        problems.append(("run", "run.stage", f"must be one of {list(FW['stages'])}"))
    if meta.get("mode") not in FW["run_modes"]:
        problems.append(("run", "run.mode", f"must be one of {list(FW['run_modes'])}"))
    if str(meta.get("rule_version")) != str(FW["rule_version"]):
        problems.append(("run", "run.rule_version", f"must be {FW['rule_version']}"))
    if not meta.get("period") or "-Q" not in str(meta.get("period")):
        problems.append(("run", "run.period", "must be set as YYYY-Qn"))
    lenses, _ = lenses_for({"run": {"stage": stage if stage in FW["stages"] else "outside_in"}})
    subs = run.get("subjects", []) or []
    if sum(1 for s in subs if s.get("role") == "company") != 1:
        problems.append(("run", "subjects", "exactly one subject must have role 'company'"))
    peers = [s for s in subs if s.get("role") == "peer"]
    if not (2 <= len(peers) <= FW["max_peers"]):
        problems.append(("run", "peers", f"peer set should be 2-{FW['max_peers']} listed peers (has {len(peers)})"))
    actions = run.get("actions", []) or []
    for a in actions:
        if not a.get("heading") or not a.get("description"):
            problems.append(("run", "actions", "each action needs heading and description"))
        if not a.get("target_by"):
            warnings.append(("run", f"action '{a.get('heading', '')[:30]}'", "no target_by; status cannot be tracked next quarter"))
        if re.search(r"\b(A&M|Alvarez|Marsal)\b", f"{a.get('heading', '')} {a.get('description', '')}", re.I):
            problems.append(("run", "actions", "actions must not reference A&M services"))
    if len(actions) > 5:
        problems.append(("run", "actions", "maximum five actions"))
    for pa in run.get("prior_actions_status", []) or []:
        if pa.get("status") not in FW["action_statuses"]:
            problems.append(("run", "prior_actions_status", f"status must be one of {FW['action_statuses']}"))
    for s in subs:
        if s.get("role") == "peer" and any("board_io" in (v or {}) for v in (s.get("indicators") or {}).values()):
            problems.append((s.get("name", "?"), "peer", "peers are never assessed with inside-out information"))
        validate_subject(s, evidence, lenses, problems, warnings, stage)
    for h in run.get("history", []) or []:
        if h.get("period") == meta.get("period"):
            problems.append(("run", "history", "history contains the current period"))
    return problems, warnings


# ------------------------------------------------------------------ computation

def compute_scores(sc: dict[str, int | None], thr: float, ids: list[str] | None = None) -> dict:
    """Dimension and overall grades from a {indicator id: score|None} map (js compute()). `thr` is the coverage threshold."""
    ids = ids or IND_IDS
    dims: dict[str, dict] = {}
    for d in DIMS:
        dids = [i for i in ids if DIM_OF.get(i) == d]
        v = [sc[i] for i in dids if sc.get(i) is not None]
        n, m = len(v), len(dids)
        rec: dict[str, Any] = {"assessed": n, "of": m}
        if n > 0 and meets(n, m, thr):
            avg = sum(v) / n
            g, label = to_grade(avg)
            rec.update({"average": round(avg, 2), "grade": g, "label": label, "reported": True})
        else:
            rec.update({"average": None, "grade": None, "label": "Insufficient evidence", "reported": False})
        dims[d] = rec
    return {"dimensions": dims, "overall": _overall_of(dims), "assessed": sum(1 for i in ids if sc.get(i) is not None)}


def _overall_of(dims: dict[str, dict]) -> dict:
    letters = [dims[d]["grade"] for d in DIMS if dims[d]["reported"]]
    o: dict[str, Any] = {"dimensions_reported": len(letters), "provisional": False}
    if len(letters) >= 3:
        avg = sum(LV[x] for x in letters) / len(letters)
        r = round_midpoint_down(avg)
        o.update({"grade": VL[r], "numeric_average": round(avg, 2), "provisional": len(letters) == 3, "label": label_of(VL[r])})
    else:
        o.update({"grade": None, "numeric_average": None, "label": "No overall grade (fewer than 3 dimensions reported)"})
    return o


def compute_subject(subj: dict, lenses: list[str], stage: str = "outside_in") -> dict:
    inds = subj.get("indicators", {}) or {}
    out: dict[str, Any] = {"dimensions": {}, "overall": {}, "coverage": {}}
    use = lenses if subj.get("role") == "company" else ["board"]
    for lens in use:
        thr = FW["coverage_threshold"]["inside_out" if lens == "board_io" else "outside_in"]
        for d in DIMS:
            ids = [i for i in IND_IDS if DIM_OF[i] == d]
            scores = [((inds.get(i) or {}).get(lens) or {}).get("score") for i in ids]
            scores = [s for s in scores if s is not None]
            n, m = len(scores), len(ids)
            rec: dict[str, Any] = {"assessed": n, "of": m}
            if n > 0 and meets(n, m, thr):
                avg = sum(scores) / n
                g, label = to_grade(avg)
                rec.update({"average": round(avg, 2), "grade": g, "label": label, "reported": True})
            else:
                rec.update({"average": None, "grade": None, "label": "Insufficient evidence", "reported": False})
            out["dimensions"].setdefault(d, {})[lens] = rec
        letters = [out["dimensions"][d][lens]["grade"] for d in DIMS if out["dimensions"][d][lens]["reported"]]
        o: dict[str, Any] = {"dimensions_reported": len(letters), "provisional": False}
        if len(letters) >= 3:
            avg = sum(LV[x] for x in letters) / len(letters)
            r = round_midpoint_down(avg)
            o.update({"grade": VL[r], "numeric_average": round(avg, 2), "provisional": len(letters) == 3,
                      "label": next(b["label"] for b in FW["grade_scale"] if b["grade"] == VL[r])})
        else:
            o.update({"grade": None, "numeric_average": None, "label": "No overall grade (fewer than 3 dimensions reported)"})
        out["overall"][lens] = o
        cells = [((inds.get(i) or {}).get(lens) or {}) for i in IND_IDS]
        split = {k: 0 for k in FW["na_causes"]}
        split["unspecified"] = 0
        for c in cells:
            if c.get("score") is None:
                split[c.get("na_cause") if c.get("na_cause") in split else "unspecified"] += 1
        out["coverage"][lens] = {"assessed": sum(1 for c in cells if c.get("score") is not None), "of": len(IND_IDS), "not_assessable": split}
    return out


def grade(run: dict, check: bool = False) -> dict:
    """Validate the scoring rules and (unless `check`) write `computed` into every subject of `run`.

    Returns {"ok", "problems", "warnings"}; each string is "[<code>] <subject>: <text>".
    """
    try:
        problems, warnings = validate_run(run)
        if not check:
            lenses, _ = lenses_for({"run": {"stage": stage_of(run) if stage_of(run) in FW["stages"] else "outside_in"}})
            for s in run.get("subjects", []) or []:
                s["computed"] = compute_subject(s, lenses, stage_of(run))
    except (AttributeError, TypeError, KeyError) as e:  # malformed run: report instead of raising
        return {"ok": False, "problems": [f"[run] run: could not read the run ({type(e).__name__}: {e})"], "warnings": []}
    return {"ok": not problems, "problems": _fmt(problems), "warnings": _fmt(warnings)}


def grade_summary(run: dict) -> str:
    """Text report like grade.py's console output (for logs)."""
    lenses, labels = lenses_for(run)
    lines = []
    for s in run.get("subjects", []):
        c = s.get("computed") or {}
        use = lenses if s.get("role") == "company" else ["board"]
        lines.append(f"{s['name']} ({s['role']})  " + "  ".join(f"{labels[l]}: {c['coverage'][l]['assessed']}/{c['coverage'][l]['of']}" for l in use))
        lines.append("  Overall: " + " | ".join(f"{labels[l]} {c['overall'][l].get('grade') or '-'}" for l in use))
    return "\n".join(lines)


# ------------------------------------------------------------------ history (load_history.py)

def summarise(prior: dict) -> dict:
    """One compact history entry from a prior run file (load_history.summarise). A prior that was never graded is graded on a copy."""
    if not (company_of(prior).get("computed")):
        prior = copy.deepcopy(prior)
        grade(prior)
    comp = company_of(prior)
    c = comp.get("computed") or {}
    lenses = [l for l in ("board", "board_io") if l in (c.get("overall") or {})]
    return {
        "period": period_label(prior), "stage": stage_of(prior), "simulated": bool((prior.get("run") or {}).get("simulated")),
        "run_date": (prior.get("run") or {}).get("run_date"), "lenses": lenses,
        "dimensions": {d: {l: {"grade": c["dimensions"][d][l]["grade"], "average": c["dimensions"][d][l]["average"]} for l in lenses} for d in DIMS},
        "overall": {l: {"grade": c["overall"][l].get("grade"), "provisional": c["overall"][l].get("provisional")} for l in lenses},
        "indicators": {i: {l: ((comp["indicators"].get(i) or {}).get(l) or {}).get("score") for l in lenses} for i in IND_IDS},
        "indicator_rationale": {i: {l: ((comp["indicators"].get(i) or {}).get(l) or {}).get("rationale") for l in lenses} for i in IND_IDS},
        "peers": {p["name"]: {d: p["computed"]["dimensions"][d]["board"]["grade"] for d in DIMS} | {"overall": p["computed"]["overall"]["board"].get("grade")}
                  for p in peers_of(prior) if p.get("computed")},
        "actions": prior.get("actions", []),
        "key_metrics": prior.get("key_metrics", []),
    }


def load_history(run: dict, priors: list[dict]) -> None:
    """Replace run["history"] with compact entries from `priors` (newest per period; inside-out supersedes outside-in;
    newest max_history_quarters kept, oldest first)."""
    by: dict[str, dict] = {}
    for h in (summarise(p) for p in priors):
        if h["period"] not in by or h["stage"] == "inside_out":
            by[h["period"]] = h
    run["history"] = sorted(by.values(), key=lambda h: h["period"])[-FW["max_history_quarters"]:]


def history_from_run(run: dict) -> dict:
    """Strict variant used when a user supplies a prior run file (js historyFromRun): rejects non-run, simulated or
    wrong-rule-version files. Returns {period, stage, ind, dims, overall, oiOverall, actions}."""
    if not isinstance(run, dict) or not isinstance(run.get("run"), dict) or not isinstance(run.get("subjects"), list):
        raise ValueError("not a run file")
    if run["run"].get("simulated"):
        raise ValueError("simulated assessments cannot be used for trend")
    if str(run["run"].get("rule_version")) != str(FW["rule_version"]):
        raise ValueError(f"rule version {run['run'].get('rule_version')} differs from {FW['rule_version']}; re-run before comparing")
    subj = next((s for s in run["subjects"] if s.get("role") == "company"), None)
    if not subj:
        raise ValueError("no company subject")
    oi: dict[str, Any] = {}
    io: dict[str, Any] = {}
    has_io = False
    for i in IND_IDS:
        c = (subj.get("indicators") or {}).get(i) or {}
        oi[i] = (c.get("board") or {}).get("score")
        if c.get("board_io"):
            has_io = True
            io[i] = c["board_io"].get("score")
    a = compute_scores(oi, FW["coverage_threshold"]["outside_in"])
    b = compute_scores(io, FW["coverage_threshold"]["inside_out"]) if has_io else None
    c = b or a
    return {"period": run["run"].get("period"), "stage": run["run"].get("stage"), "ind": io if has_io else oi,
            "dims": c["dimensions"], "overall": c["overall"], "oiOverall": a["overall"], "actions": run.get("actions", [])}


def build_history(priors: list[dict], selected: list[str], current_period: str | None = None, keep: int = 2) -> list[dict]:
    """Trend entries from the view's `priors` the user picked (js buildHistory), oldest first, at most `keep`."""
    out = []
    for p in priors or []:
        if p["period"] not in selected or p["period"] == current_period:
            continue
        thr = FW["coverage_threshold"]["inside_out" if p.get("stage") == "inside_out" else "outside_in"]
        c = compute_scores(p["scores"], thr)
        out.append({"period": p["period"], "stage": p.get("stage"), "ind": p["scores"], "dims": c["dimensions"], "overall": c["overall"], "actions": p.get("actions", [])})
    return sorted(out, key=lambda h: h["period"])[-keep:]


# ------------------------------------------------------------------ inside-out re-scoring (js ioCell / M)

def io_cell(view: dict, iid: str) -> dict:
    """The post inside-out cell for an indicator: re-scored from board documents, else the outside-in score carried forward."""
    o = view["ind"][iid]
    c = ((view.get("io") or {}).get("cells") or {}).get(iid)
    if c:
        carried = bool(c.get("carried"))
        return {"score": c["score"], "conf": c.get("conf"), "rat": c.get("rationale"), "ev": c.get("ev") or [], "carried": carried,
                "src": "carried forward" if carried else "board documents"}
    return {"score": o.get("score"), "conf": o.get("conf"), "rat": "Carried forward: nothing supplied settles this indicator, so the outside-in score stands.",
            "ev": o.get("ev", []), "carried": True, "src": "carried forward"}


def model(view: dict) -> dict:
    """Grades for the view (js M()): outside-in, post inside-out and each peer."""
    ids = sorted((i for i in view["ind"] if re.fullmatch(r"\d+\.\d+", i)), key=lambda x: tuple(int(p) for p in x.split(".")))
    oi_sc = {i: view["ind"][i].get("score") for i in ids}
    io_sc = {i: io_cell(view, i)["score"] for i in ids}
    thr = FW["coverage_threshold"]
    m: dict[str, Any] = {"oiSc": oi_sc, "ioSc": io_sc, "oi": compute_scores(oi_sc, thr["outside_in"], ids), "io": compute_scores(io_sc, thr["inside_out"], ids), "peers": []}
    for p, name in enumerate(view["meta"].get("peer_short", [])):
        sc = {i: view["peers"][p]["ind"][i].get("score") for i in ids}
        m["peers"].append({"name": name, "full": view["meta"]["peers"][p], "sc": sc, "c": compute_scores(sc, thr["outside_in"], ids)})
    return m


def prior_actions_list(view: dict, history: list[dict] | None = None) -> list[dict]:
    """Status of last quarter's actions (js priorActionsList): the inside-out result's own list, else last history entry's actions as untracked."""
    pa = (view.get("io") or {}).get("prior_actions")
    if pa:
        return [{"id": a.get("id"), "heading": a.get("heading"), "status": a.get("status"), "note": a.get("note"), "metrics": a.get("metrics")} for a in pa]
    last = history[-1] if history else None
    if last and last.get("actions"):
        return [{"id": a.get("id"), "heading": a.get("heading"), "status": "no_public_evidence",
                 "note": "Status needs the action tracker or minutes; none supplied in this run.", "metrics": "; ".join(a.get("measures") or [])} for a in last["actions"]]
    return []


def cause_split(view: dict, sc: dict[str, int | None]) -> dict[str, int]:
    """Not-assessable indicators by cause (js causeSplit)."""
    sp = {k: 0 for k in FW["na_causes"]}
    for i, s in sc.items():
        if s is None:
            c = (view["ind"].get(i) or {}).get("na")
            sp[c if c in sp else FW["na_causes"][0]] += 1
    return sp


# ------------------------------------------------------------------ guardrails (references/guardrails.md)

_G_TITLE = re.compile(r"\b(Mr|Mrs|Ms|Mx|Dr|Prof)\.?\s+[A-Z][a-z]+")
_G_ROLE = re.compile(r"\b(director|chair|chairman|CEO|CFO)\s+[A-Z][a-z]+\s+[A-Z][a-z]+")
_G_CHAR = re.compile(r"\b(incompetent|corrupt|lazy|dishonest|lying|liar)\b", re.I)
_G_LEGAL = re.compile(r"breach(ed|es)?\s+(of\s+|its\s+|their\s+|the\s+)?(fiduciary\s+)?dut|\bfraud|\billegal|\bunlawful|negligen|\bliable\b|violat(ed|ion) of (the )?(law|securities)", re.I)
_G_ADVICE = re.compile(r"\b(buy|sell|short)\s+(the\s+)?(stock|shares)|price target|will (rise|fall|outperform|underperform)|undervalued|overvalued", re.I)


def guardrail_scan(text: str | None) -> list[str]:
    """Language warnings: individuals named, people characterised, legal conclusions, investment advice."""
    t = text or ""
    w = []
    if _G_TITLE.search(t) or _G_ROLE.search(t):
        w.append("Names an individual. Grades apply to the board as a body; refer to roles or the board.")
    if _G_CHAR.search(t):
        w.append("Characterises people. Keep language evidence-based and non-accusatory.")
    if _G_LEGAL.search(t):
        w.append("Reads as a legal conclusion. Describe what the record shows instead.")
    if _G_ADVICE.search(t):
        w.append("Reads as investment advice or a share-price view.")
    return w


def language_warnings(answers: dict | list | None) -> list[dict]:
    """Guardrail warnings for self-assessment answers keyed (or listed) by question number (js languageWarnings)."""
    items = answers.items() if isinstance(answers, dict) else enumerate(answers or [], 1)
    out = []
    for n, a in items:
        if a and str(a).strip():
            out += [{"q": int(n), "msg": m} for m in guardrail_scan(str(a))]
    return out
