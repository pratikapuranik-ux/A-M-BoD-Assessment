"""Golden tests for the pure domain layer (engine, view, skill data). No web or DB imports.

Run from the backend directory:  python -m pytest tests/test_engine.py
"""
import copy
import json
import os
import re
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.domain import engine, skill, view  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
FIX = os.path.join(HERE, "fixtures")
DATA = os.path.join(os.path.dirname(HERE), "app", "data")
LINE = re.compile(r"^\[(.*?)\] (.*?): (.*)$")


def load(name, d=FIX):
    with open(os.path.join(d, name), encoding="utf-8") as f:
        return json.load(f)


@pytest.fixture()
def oi():
    return load("outside_in_run.json")


@pytest.fixture()
def io():
    return load("inside_out_run.json")


@pytest.fixture()
def prior():
    return load("prior_2026-Q3_simulated_run.json")


def strip_computed(run):
    r = copy.deepcopy(run)
    for s in r["subjects"]:
        s.pop("computed", None)
    return r


# ---------------------------------------------------------------- golden: grade reproduces `computed`

@pytest.mark.parametrize("name", ["outside_in_run.json", "inside_out_run.json", "prior_2026-Q3_simulated_run.json"])
def test_grade_reproduces_fixture_computed(name):
    run = load(name)
    g = strip_computed(run)
    res = engine.grade(g)
    assert res == {"ok": True, "problems": [], "warnings": []}
    for want, got in zip(run["subjects"], g["subjects"]):
        assert got["computed"] == want["computed"], want["name"]


def test_headline_grades(oi, io):
    def letters(run, lens):
        c = skill.company_of(run)["computed"]
        return "".join(c["dimensions"][d][lens]["grade"] for d in skill.DIMS), c["overall"][lens]["grade"]
    assert letters(oi, "board") == ("DBBCCB", "C")
    assert letters(io, "board_io") == ("BCBBDA", "B")
    assert letters(io, "board") == ("DBBCCB", "C")  # outside-in cell untouched in an inside-out run
    assert "".join(p["computed"]["overall"]["board"]["grade"] for p in skill.peers_of(oi)) == "CD"  # BP 2.5 rounds down
    assert skill.company_of(oi)["computed"]["coverage"]["board"]["assessed"] == 22


def test_check_does_not_write_computed(oi):
    g = strip_computed(oi)
    assert engine.grade(g, check=True)["ok"]
    assert all("computed" not in s for s in g["subjects"])
    engine.grade(g)
    assert all("computed" in s for s in g["subjects"])


# ---------------------------------------------------------------- scoring maths

def test_midpoint_rounds_down():
    sc = {i: (3 if skill.DIM_OF[i] <= "3" else 2) for i in skill.IND_IDS}
    assert engine.compute_scores(sc, 0.5)["overall"]["grade"] == "D"  # 2.5 -> D
    assert skill.round_midpoint_down(3.5) == 3 and skill.round_midpoint_down(2.6) == 3


def test_coverage_thresholds():
    c = lambda ids, thr: engine.compute_scores({i: 3 for i in ids}, thr)["dimensions"]  # noqa: E731
    assert c(["1.1", "1.2"], 0.5)["1"]["reported"] is True
    assert c(["1.1"], 0.5)["1"]["reported"] is False
    # two-thirds inside-out, including the framework's rounded 0.67
    thr = skill.FW["coverage_threshold"]["inside_out"]
    assert c(["4.1", "4.2"], thr)["4"]["reported"] is True
    assert c(["4.1", "4.2"], 0.67)["4"]["reported"] is True
    assert c(["4.1"], thr)["4"]["reported"] is False
    assert c(["1.1", "1.2"], thr)["1"]["reported"] is False
    assert c(["1.1", "1.2", "1.3"], thr)["1"]["reported"] is True


def test_overall_needs_three_dimensions():
    sc = {i: 5 for i in skill.IND_IDS if skill.DIM_OF[i] in "12"}
    assert engine.compute_scores(sc, 0.5)["overall"]["grade"] is None
    sc.update({i: 5 for i in skill.IND_IDS if skill.DIM_OF[i] == "3"})
    o = engine.compute_scores(sc, 0.5)["overall"]
    assert o["grade"] == "A" and o["provisional"] is True


# ---------------------------------------------------------------- rule checks

def probs(run):
    return "|".join(engine.grade(run, check=True)["problems"])


def test_problem_format(oi):
    oi["subjects"][0]["indicators"]["1.1"]["board"]["score"] = 5
    oi["subjects"][0]["indicators"]["1.1"]["board"]["evidence"] = [oi["subjects"][0]["indicators"]["1.1"]["board"]["evidence"][0]]
    res = engine.grade(oi, check=True)
    for p in res["problems"] + res["warnings"]:
        assert LINE.match(p), p


def test_rule_violations(oi):
    comp = lambda r: skill.company_of(r)["indicators"]  # noqa: E731
    r = copy.deepcopy(oi)
    comp(r)["1.1"]["board"].update(score=5, evidence=["E01"])
    assert re.search(r"score 5 needs|evidence ids not in", probs(r))
    r = copy.deepcopy(oi)
    r["actions"][0]["description"] += " Alvarez & Marsal can help"
    assert "must not reference A&M" in probs(r)
    r = copy.deepcopy(oi)
    skill.peers_of(r)[0]["indicators"]["1.1"]["board_io"] = {"score": 3, "evidence": [], "confidence": "Low", "rationale": "x"}
    assert "never assessed with inside-out" in probs(r)
    r = copy.deepcopy(oi)
    comp(r)["2.3"]["board"] = {"score": None}
    assert "na_cause" in probs(r)
    r = copy.deepcopy(oi)
    comp(r)["3.4"]["board"]["evidence"] = list(comp(r)["5.1"]["board"]["evidence"])
    assert "scoped pair" in probs(r)
    r = copy.deepcopy(oi)
    r["run"]["rule_version"] = "1.1"
    r["run"]["period"] = "2026"
    r["run"]["mode"] = "nope"
    p = probs(r)
    assert "run.rule_version" in p and "run.period" in p and "run.mode" in p
    r = copy.deepcopy(oi)
    r["history"] = [{"period": r["run"]["period"]}]
    assert "history contains the current period" in probs(r)
    r = copy.deepcopy(oi)
    r["actions"] = r["actions"] * 3
    assert "maximum five actions" in probs(r)


def test_inside_out_cell_rules(io):
    cell = skill.company_of(io)["indicators"]["1.1"]["board_io"]
    io2 = copy.deepcopy(io)
    c2 = skill.company_of(io2)["indicators"]["1.1"]["board_io"]
    c2["evidence"] = skill.company_of(io2)["indicators"]["1.1"]["board"]["evidence"]
    c2.pop("carried_forward", None)
    assert "post inside-out score must cite" in probs(io2)
    assert cell  # fixture cell exists


def test_malformed_run_does_not_raise():
    res = engine.grade({"subjects": None})
    assert res["ok"] is False and res["problems"]


# ---------------------------------------------------------------- history

def test_load_history_matches_legacy_shape(oi, prior):
    engine.load_history(oi, [prior])
    h = oi["history"]
    assert [x["period"] for x in h] == ["2026-Q3"]
    assert set(h[0]) >= {"period", "stage", "simulated", "run_date", "lenses", "dimensions", "overall", "indicators",
                         "indicator_rationale", "peers", "actions", "key_metrics"}
    assert h[0]["simulated"] is True and h[0]["lenses"] == ["board"]
    assert set(h[0]["indicators"]) == set(skill.IND_IDS)
    assert h[0]["overall"]["board"]["grade"] == skill.company_of(prior)["computed"]["overall"]["board"]["grade"]


def test_load_history_inside_out_supersedes_and_caps(oi, io, prior):
    p_oi, p_io = copy.deepcopy(io), copy.deepcopy(io)
    p_oi["run"]["stage"] = "outside_in"
    for s in p_oi["subjects"]:
        s.pop("computed", None)
        for ind in s["indicators"].values():
            ind.pop("board_io", None)
    engine.load_history(oi, [p_oi, p_io])
    assert len(oi["history"]) == 1 and oi["history"][0]["stage"] == "inside_out"
    many = []
    for q in range(1, 8):
        p = copy.deepcopy(prior)
        p["run"]["period"] = f"2024-Q{(q % 4) + 1}" if q < 5 else f"2025-Q{q - 4}"
        many.append(p)
    engine.load_history(oi, many)
    assert len(oi["history"]) <= skill.FW["max_history_quarters"]
    assert [h["period"] for h in oi["history"]] == sorted(h["period"] for h in oi["history"])


def test_history_from_run_strict(prior):
    p = copy.deepcopy(prior)
    p["run"].pop("simulated", None)
    e = engine.history_from_run(p)
    assert e["period"] == "2026-Q3" and e["overall"]["grade"] == "C"
    p["run"]["rule_version"] = "1.1"
    with pytest.raises(ValueError, match="rule version"):
        engine.history_from_run(p)
    p["run"]["rule_version"] = "1.2"
    p["run"]["simulated"] = True
    with pytest.raises(ValueError, match="simulated"):
        engine.history_from_run(p)
    with pytest.raises(ValueError, match="not a run file"):
        engine.history_from_run({})


# ---------------------------------------------------------------- view helpers (js engine port)

def test_model_matches_view_grades(oi, io, prior):
    v = view.to_view(oi, io, prior)
    m = engine.model(v)
    assert "".join(m["oi"]["dimensions"][d]["grade"] for d in skill.DIMS) == "DBBCCB" and m["oi"]["overall"]["grade"] == "C"
    assert "".join(m["io"]["dimensions"][d]["grade"] for d in skill.DIMS) == "BCBBDA" and m["io"]["overall"]["grade"] == "B"
    assert "".join(p["c"]["overall"]["grade"] for p in m["peers"]) == "CD"
    assert m["oi"]["assessed"] == 22 and m["io"]["assessed"] == 22


def test_io_cell_carries_forward_and_missing_io_is_safe(oi, io):
    v = view.to_view(oi, io)
    v2 = copy.deepcopy(v)
    v2["io"].pop("cells"), v2["io"].pop("ev")
    assert engine.io_cell(v2, "1.1")["carried"] is True
    assert engine.io_cell(view.to_view(oi), "1.1")["score"] == v["ind"]["1.1"]["score"]


def test_prior_actions_and_history_build(oi, io, prior):
    v = view.to_view(oi, io, prior)
    assert engine.prior_actions_list(v)  # io.prior_actions present
    v_oi = view.to_view(oi, None, prior)
    pa = engine.prior_actions_list(v_oi, v_oi["priors"])
    assert pa and all(a["status"] == "no_public_evidence" for a in pa)
    h = engine.build_history(v["priors"], ["2026-Q3"], "2026-Q4")
    assert h and h[0]["period"] == "2026-Q3" and h[0]["overall"]["grade"] == "C"
    assert engine.build_history(v["priors"], ["2026-Q3"], "2026-Q3") == []


def test_cause_split(oi):
    v = view.to_view(oi)
    sc = {i: v["ind"][i]["score"] for i in v["ind"]}
    sp = engine.cause_split(v, sc)
    assert sum(sp.values()) == sum(1 for s in sc.values() if s is None)


def test_guardrails():
    assert len(engine.guardrail_scan("Mr Smith was incompetent")) >= 2
    assert engine.guardrail_scan("The board breached its fiduciary duty")
    assert engine.guardrail_scan("Analysts see the shares as undervalued")
    assert engine.guardrail_scan("The board asked for unfiltered customer evidence") == []
    assert engine.language_warnings({"2": "the CEO John Smith is a liar", "3": ""})[0]["q"] == 2


# ---------------------------------------------------------------- view

def test_name_helpers():
    assert view.short_name("Exxon Mobil (ExxonMobil Holdings Corporation)") == "ExxonMobil"
    assert view.short_name("BP p.l.c.") == "BP"
    assert view.short_name("Chevron Corporation") == "Chevron"
    assert view.slug("Chevron", "CVX") == "chevron"
    assert view.slug("", "CVX") == "cvx"
    assert view.slug("!!!", "").startswith("co-")
    assert len(view.slug("a" * 100)) <= 56


def test_company_peers_ids(oi):
    assert view.company_of(oi)["name"] == "Chevron Corporation"
    assert [view.subj_short(p) for p in view.peers_of(oi)] == ["ExxonMobil", "BP"]
    assert view.company_id(view.company_of(oi)) == "chevron"


def test_framework_keys():
    fw = view.framework()
    assert set(fw) == set(skill.FW_KEYS) and fw["rule_version"] == "1.2"


def test_base_view_shape():
    b = view.base_view()
    assert set(b) >= {"meta", "ind", "peers", "read", "method", "defs", "io", "prior", "priors", "docs", "q", "modes", "scale", "files"}
    assert len(b["ind"]) == 22 and all(v["score"] is None for v in b["ind"].values())
    assert b["io"] is None and b["docs"] and b["q"]


def _missing_or_diff(want, got, path=""):
    out = []
    if isinstance(want, dict) and isinstance(got, dict):
        for k in want:
            out += [f"missing {path}/{k}"] if k not in got else _missing_or_diff(want[k], got[k], f"{path}/{k}")
    elif want != got:
        out.append(f"differs {path}")
    return out


def test_to_view_matches_example_view_fixture(oi, io, prior):
    """tests/fixtures/example_view.js (converted to app/data/example_view.json) is the front end's golden view. The fixture
    predates `id`, `prefixes`, `priors`, `files`, `overall`, evidence `simulated` flags and carries full self-assessment
    answers where the example run keeps truncated excerpts, so those are excluded."""
    want = load("example_view.json", DATA)
    got = view.to_view(oi, io, prior)
    diffs = [d for d in _missing_or_diff(want, got) if not d.endswith("/simulated") and d != "differs /io/sa"]
    assert diffs == []
    assert len(got["io"]["sa"]) == len(want["io"]["sa"]) == len(skill.FW["questionnaire"])


def test_to_view_outside_in_only(oi, prior):
    v = view.to_view(oi, None, prior, {"id": "chevron", "source": "research", "files": {"a": "b"}})
    assert v["io"] is None and v["meta"]["id"] == "chevron" and v["meta"]["source"] == "research" and v["files"] == {"a": "b"}
    assert v["priors"] and v["priors"][-1]["period"] == "2026-Q3" and v["prior"]["period"] == "2026-Q3"
    assert v["scorecard"][-1]["dim"] == "Overall"
    assert json.dumps(v)  # JSON-serialisable


def test_to_view_history_fallback(oi, prior):
    engine.load_history(oi, [prior])
    v = view.to_view(oi)
    assert [p["period"] for p in v["priors"]] == ["2026-Q3"] and v["prior"]["period"] == "2026-Q3"
