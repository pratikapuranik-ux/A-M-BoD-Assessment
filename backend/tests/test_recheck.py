"""The anchor recheck: scores of 4 and 5 are read again against the anchors; where the second reading differs it replaces the first, and the
change is listed in the run for the report. Scripted fake client, no network. Run from backend/:  python -m pytest tests/test_recheck.py
"""
import json
import re
from types import SimpleNamespace as NS

import pytest

from app.agents import client as C, graph as G, nodes as N, settings as cfg
from app.services import audit
from tests.test_research import (AS_OF, COMPANY, PEER_ARGS, FakeClient, make_model, usage)


@pytest.fixture(autouse=True)
def recheck_on(monkeypatch):
    monkeypatch.setattr(cfg, "RECHECK", True); monkeypatch.setattr(cfg, "PIPELINE", "single"); monkeypatch.setattr(cfg, "CONSISTENCY_RUNS", 1)
    monkeypatch.setattr(cfg, "REVIEW_ROUNDS", 0); monkeypatch.setattr(N, "today", lambda: AS_OF)


def second_reader(lower=("0:",)):
    """A fake reader: for each indicator it is given it keeps the score, except the first high score of each key prefix in `lower`, which it lowers by one."""
    seen = {"prompts": 0, "moved": []}

    def create(**kw):
        seen["prompts"] += 1
        prompt = kw["messages"][0]["content"]
        rows = []; done = set()
        for key, score in re.findall(r'<indicator key="([^"]+)" id="[^"]+" name="[^"]*">.*?<first_pass_score>(\d)</first_pass_score>', prompt, re.S):
            score = int(score); pre = key.split(":")[0] + ":"
            if pre in lower and pre not in done and score >= 4:
                done.add(pre); seen["moved"].append((key, score))
                rows.append({"key": key, "strict_score": score - 1, "reason": "The facts match the 3 anchor as written, not the 5 anchor.",
                             "rationale": "Directors reviewed the matter and the filing records one meeting in the year. This matches the Mixed anchor, not the strong anchor.",
                             "summary": "Mixed practice; one meeting recorded."})
            else: rows.append({"key": key, "strict_score": score, "reason": "Anchors met as scored.", "rationale": "", "summary": ""})
        return NS(content=[NS(type="text", text=json.dumps(rows))], usage=usage())
    return create, seen


def install(monkeypatch, reader):
    client = FakeClient(make_model()); client.messages = NS(create=reader)
    monkeypatch.setattr(C, "get_client", lambda: client)
    return client


def test_a_changed_score_replaces_the_first_one_and_is_listed(monkeypatch):
    create, seen = second_reader(lower=("0:", "1:"))
    client = install(monkeypatch, create)
    run = G.run_outside_in(COMPANY["name"], "CVX", PEER_ARGS, "2026-Q4", "director_request", None)
    block = run["anchor_recheck"]
    assert block["status"] == "done" and block["scores"] == [2, 4, 5] and block["reviewed"] >= 2 and seen["prompts"] == 3  # one reading per subject
    assert len(block["rows"]) == 2 and {r["role"] for r in block["rows"]} == {"company", "peer"}
    for r in block["rows"]:
        assert r["final"] == r["first"] - 1 and r["reason"].startswith("The facts match") and r["name"]
        subj = next(s for s in run["subjects"] if s["name"] == r["subject"])
        assert subj["indicators"][r["indicator"]]["board"]["score"] == r["final"]  # the report shows the final score only
    co = next(r for r in block["rows"] if r["role"] == "company")
    assert co["first"] == dict(seen["moved"])["0:" + co["indicator"]]
    # the company's narrative was sent back for revision, and its revision (a full resubmission at the old scores) could not move the locked score
    texts = [str(k["messages"][-1]["content"]) for k in client.calls if "submit_subject_assessment" in [t["name"] for t in k["tools"]]]
    assert any("An anchor recheck has set these final indicator scores" in t for t in texts)
    assert next(s for s in run["subjects"] if s["role"] == "company")["indicators"][co["indicator"]]["board"]["score"] == co["final"]


def test_an_unchanged_reading_adds_a_table_with_no_rows_and_no_narrative_revision(monkeypatch):
    create, seen = second_reader(lower=())
    client = install(monkeypatch, create)
    run = G.run_outside_in(COMPANY["name"], "CVX", PEER_ARGS, "2026-Q4", "director_request", None)
    assert run["anchor_recheck"]["rows"] == [] and run["anchor_recheck"]["reviewed"] >= 1
    assert not any("An anchor recheck" in str(k["messages"][-1]["content"]) for k in client.calls)


def test_a_failed_recheck_does_not_discard_the_research(monkeypatch):
    def broken(**kw): raise RuntimeError("service down")
    install(monkeypatch, broken)
    run = G.run_outside_in(COMPANY["name"], "CVX", PEER_ARGS, "2026-Q4", "director_request", None)
    assert run["anchor_recheck"]["rows"] == [] and "could not be completed" in run["anchor_recheck"]["status"] and len(run["subjects"]) == 3


def test_recheck_prompt_carries_anchors_scores_and_summary_only_where_given():
    items = [{"key": "0:1.1", "id": "1.1", "score": 5, "rationale": "R one.", "summary": "S one."}, {"key": "1:1.2", "id": "1.2", "score": 4, "rationale": "R two.", "summary": ""}]
    p = audit.build_recheck_prompt(items)
    assert 'key="0:1.1"' in p and "<first_pass_summary>S one.</first_pass_summary>" in p and p.count("<first_pass_summary>") == 1
    assert "<anchor_3>" in p and "A score may move up as well as down" in p


def test_off_switch_skips_the_recheck(monkeypatch):
    monkeypatch.setattr(cfg, "RECHECK", False)
    create, seen = second_reader(lower=("0:",))
    install(monkeypatch, create)
    run = G.run_outside_in(COMPANY["name"], "CVX", PEER_ARGS, "2026-Q4", "director_request", None)
    assert "anchor_recheck" not in run and seen["prompts"] == 0


def test_only_scores_2_4_and_5_are_read_again(monkeypatch):
    sent = []
    def create(**kw):
        prompt = kw["messages"][0]["content"]; sent.extend(int(x) for x in re.findall(r"<first_pass_score>(\d)</first_pass_score>", prompt))
        rows = [{"key": k, "strict_score": int(s), "reason": "ok", "rationale": "", "summary": ""} for k, s in re.findall(r'<indicator key="([^"]+)".*?<first_pass_score>(\d)</first_pass_score>', prompt, re.S)]
        return NS(content=[NS(type="text", text=json.dumps(rows))], usage=usage())
    install(monkeypatch, create)
    G.run_outside_in(COMPANY["name"], "CVX", PEER_ARGS, "2026-Q4", "director_request", None)
    assert sent and set(sent) <= {2, 4, 5} and 2 in sent
    monkeypatch.setattr(cfg, "RECHECK_SCORES", (5,)); sent.clear()
    G.run_outside_in(COMPANY["name"], "CVX", PEER_ARGS, "2026-Q4", "director_request", None)
    assert sent and set(sent) == {5}
