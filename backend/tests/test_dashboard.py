"""HTML dashboard: layout follows the reference; the page script is executed in jsdom when available."""
import copy
import json
import os
import shutil
import subprocess
import tempfile
from pathlib import Path

import pytest

from app.services import deliverables as D

EX = next(p for p in Path(__file__).resolve().parents if (p / "skill" / "example_runs").is_dir()) / "skill" / "example_runs"
CHECK_JS = Path(__file__).with_name("dashboard_dom_check.js")


def _load(name):
    return json.loads((EX / f"{name}_run.json").read_text(encoding="utf-8"))


def _recon(run):
    comp = next(s for s in run["subjects"] if s["role"] == "company")
    peer = next(s for s in run["subjects"] if s["role"] == "peer")
    eid = next(iter(run["evidence"]))
    return {"models": {"A": {"model": "claude-opus-5", "effort": "high"}, "B": {"model": "claude-sonnet-5-5", "effort": "high"}},
            "agreed": 20, "total": 22,
            "rows": [{"subject": comp["name"], "role": "company", "indicator": "1.4", "name": "Customer-linked accountability", "a": 3, "b": 4, "final": 3, "chosen": "A", "reason": f"Run A cites the plan [{eid}]."},
                     {"subject": peer["name"], "role": "peer", "indicator": "2.1", "name": "Pre-emptive reset", "a": None, "b": 2, "final": 2, "chosen": "B", "reason": "Run B found disclosure."}]}


def _build(run, tmp_path, name):
    out = tmp_path / f"{name}.html"
    D.build_dashboard(copy.deepcopy(run), str(out))
    return out.read_text(encoding="utf-8"), out


def _variant(name, recon=True):
    run = _load(name)
    for a in run["actions"]:
        a["improves"] = "Customer evidence reaching the board earlier"
    if recon:
        run["run"]["reconciliation"] = _recon(run)
    return run


@pytest.fixture(params=["outside_in", "inside_out"])
def built(request, tmp_path):
    html, path = _build(_variant(request.param), tmp_path, request.param)
    return request.param, html, path


def test_reference_strings(built):
    stage, html, _ = built
    for s in ["open to read", "Improves:", "Strongest:", "Weakest:", "Executive summary", ">Actions<", "Peer comparison",
              "Grades by dimension", "Dimension grades against the peer set", "What the board could do next",
              "Peers are assessed on public information with the same retrieval set and rubric. Select a row to see every company",
              "Coverage: ", "indicators assessed.", "non public board documents will help at a more accurate grade",
              "Where this grade is limited:", "Rounded average of dimension letters (midpoints round down).", "Coverage and limitations", "Documents available",
              "Where the two runs differed", "DRAFT ONLY"]:
        assert s in html, s
    assert html.index("Executive summary") < html.index("Peer comparison") < html.index(">Actions<")
    assert "__RUN__" not in html and "__FW__" not in html and "__TITLE__" not in html


def test_reconciliation_absent_without_key(tmp_path):
    html, _ = _build(_variant("outside_in", recon=False), tmp_path, "norecon")
    assert '"reconciliation"' not in html


def _jsdom_dir():
    cands = [os.environ.get("AM_JSDOM_DIR"), str(Path(tempfile.gettempdir()) / "am_jsdom")]
    return next((c for c in cands if c and (Path(c) / "node_modules" / "jsdom").is_dir()), None)


def _dom(path):
    node, jd = shutil.which("node"), _jsdom_dir()
    if not node or not jd:
        pytest.skip("node + jsdom not available (set AM_JSDOM_DIR to a folder containing node_modules/jsdom)")
    p = subprocess.run([node, str(CHECK_JS), jd, str(path)], capture_output=True, text=True, timeout=120, encoding="utf-8")
    assert p.returncode == 0, p.stderr
    return json.loads(p.stdout.strip().splitlines()[-1])


def test_page_script_runs_in_jsdom(built):
    stage, _, path = built
    r = _dom(path)
    assert r["errors"] == []
    k = r["kickers"]
    order = ["Executive summary", "Scorecard", "Peer comparison", "Reconciliation", "Actions"]
    idx = [next(i for i, x in enumerate(k) if x.startswith(o)) for o in order]
    assert idx == sorted(idx)
    assert r["execOpen"] is False
    assert r["dimRows"] == 6 and r["peerTable"] and r["peerRows"] == 6
    assert "(company)" in r["peerHeader"][1]
    assert r["reconRows"] == 2 and "agreed on 20 of 22" in r["reconText"] and "Run A's score stands" in r["reconText"]
    assert "open to read" in r["execText"] and "Improves:" in r["actionsText"]
    assert r["coverageLine"].startswith("Coverage: 22 of 22 indicators assessed.")
    assert r["bareCodes"] == [] and r["chips"] > 20
    assert r["panelOpen"] and r["panelRows"] == 4
    assert ("Strongest:" in r["panelText"] and "Weakest:" in r["panelText"]) or "indicators score" in r["panelText"]
    assert r["modalOpen"] and r["defModal"] and r["peerDetailOpen"]
    if stage == "inside_out":
        assert "inside-out update" in r["h1"]


def test_headings_and_removed_content(built):
    _, html, _ = built
    for h in ["Coverage and limitations", "Guardrails", "Additional information that would sharpen the assessment"]:
        assert h in html, h
    assert "Consistency run" not in html and "Metrics worth tracking" not in html and "POTENTIAL ACTIONS" not in html


def _sa_excerpts(run):
    return [e["excerpt"] for e in run["evidence"].values() if e.get("evidence_class") == "self_assessment" and e.get("excerpt")]


def test_sa_excerpts_not_in_view():
    from app.domain import view
    oi, io = _load("outside_in"), _load("inside_out")
    assert _sa_excerpts(io)
    dump = json.dumps(view.to_view(oi, io))
    assert not any(x in dump for x in _sa_excerpts(io))
    v = view.to_view(oi, io)
    assert v["io"]["sa"] == [] and v["metrics"] == [] and "consistency_result" not in dump
    g = v["guardrails"]; assert [x["group"] for x in g][0] == "Sources and evidence" and all(x["items"] for x in g)
    assert any("consistency test" in i and "not applied" in i for x in g for i in x["items"]) and v["self_assessment_responses"] is None
    cov = v["io"]["coverage"]
    assert cov["docs_available"] and not any("self-assessment" in d for d in cov["docs_available"]) and len(cov["docs_available"]) == len(set(cov["docs_available"]))
    assert v["coverage"]["docs_available"] and "docs_unavailable" in v["coverage"] and v["self_assessment_themes"] == []


def test_sa_excerpts_not_in_raw_html(tmp_path):
    html, _ = _build(_variant("inside_out"), tmp_path, "sa_raw")
    assert not any(x in html for x in _sa_excerpts(_load("inside_out")))


def test_dom_sections_anonymity_and_movement(built):
    stage, _, path = built
    r = _dom(path)
    run = _load(stage)
    assert r["errors"] == []
    assert not any(x in r["pageText"] or x in r.get("saModal", "") for x in _sa_excerpts(run))
    assert "Consistency run" not in r["pageText"] and "Outside-in score" not in r["scorecardText"] and "Post inside-out score" not in r["scorecardText"]
    assert "Documents available" in r["coverageText"] and "rule-limited" in r["coverageText"]
    assert "Coverage and limitations" in r["kickers"] and r["coverageText"]
    if stage == "inside_out":
        assert "Director responses are synthesised, not quoted." in r["saModal"]
        assert "Appendix" in r["kickers"] and "Director self-assessment: themes" in r["sectionTitles"]
        assert "Outside-in to post inside-out: indicators that moved".lower() not in " ".join(r["kickers"]).lower()


def test_dom_themes_rendered_when_present(tmp_path):
    run = _variant("inside_out")
    run["self_assessment_themes"] = [{"dimension": "1", "theme": "Early warning", "summary": "Directors converge on earlier escalation."}]
    _, path = _build(run, tmp_path, "themes")
    r = _dom(path)
    assert r["errors"] == [] and "Directors converge on earlier escalation." in r["appendixText"]


def test_no_reconciliation_dom(tmp_path):
    _, path = _build(_variant("outside_in", recon=False), tmp_path, "norecon2")
    r = _dom(path)
    assert r["errors"] == [] and not any(x.startswith("Reconciliation") for x in r["kickers"])
