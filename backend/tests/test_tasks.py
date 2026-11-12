"""The task pipeline (cfg.PIPELINE "tasks"): retrieval as short independent tasks, the engine-written retrieval log, and scoring from a ledger.

Scripted fake client, no network. Run from backend/:  python -m pytest tests/test_tasks.py
"""
import re
from types import SimpleNamespace as NS

import pytest

from app.agents import graph as G, nodes as N, settings as cfg, tasks as TK, tools as T
from app.domain import retrieval as RT
from tests.test_research import (AS_OF, COMPANY, PEER_ARGS, FakeClient, first_text, last_text, msg, subject_submission, synthesis, tool_use, tools_of)
from app.agents import client as C


@pytest.fixture(autouse=True)
def task_pipeline(monkeypatch):
    monkeypatch.setattr(cfg, "PIPELINE", "tasks"); monkeypatch.setattr(cfg, "CONSISTENCY_RUNS", 1); monkeypatch.setattr(cfg, "REVIEW_ROUNDS", 0)
    monkeypatch.setattr(N, "today", lambda: AS_OF)


def web_turn(payload, n=3):
    return msg([NS(type="server_tool_use", id="s1", name="web_search", input={"query": "q"}),
                NS(type="web_search_tool_result", tool_use_id="s1", content=[NS(type="web_search_result")] * n),
                tool_use("submit_task_result", payload, "toolu_t1")])


def task_payload(text, prefix_url):
    """What a well-behaved model returns for the one task its prompt describes."""
    if m := re.search(r"Event sweep (ES\d\d)", text):
        return {"evidence": [], "retrieval_items": [], "registers": [], "event_sweep": [{"id": m.group(1), "hits": []}], "extra_registers": [],
                "extra_trade_press": [], "documents_unavailable": []}
    if "retrieval_items with one entry for R6" in text:
        regs = re.findall(r"^\s+(REG-\w+):", text, re.M)
        return {"evidence": [], "retrieval_items": [{"id": "R6", "status": "found", "documents": ["registers searched"], "queries": [], "years": [], "filings_reviewed": -1,
                                                        "feed": "", "reason": ""}],
                "registers": [{"id": r, "status": "searched", "hits": [], "reason": ""} for r in regs], "event_sweep": [], "extra_registers": [],
                "extra_trade_press": [], "documents_unavailable": []}
    rid = re.search(r"retrieval_items with one entry for (R\d)", text).group(1)
    ev = [] if rid == "R5" else [{"ref": "a1", "document": f"{rid} document", "doc_type": "filing", "date": "2026-03", "event_date": "2026-03-01", "url": f"https://www.sec.gov/{prefix_url}/{rid}",
                                  "excerpt": "Capex was 12 billion", "evidence_class": "direct", "search_log": "", "source_type": "company", "outlet": "", "underlying_source_type": ""}]
    item = {"id": rid, "status": "not_applicable" if rid == "R5" else "found", "documents": [] if rid == "R5" else [f"{rid} document"], "queries": [],
            "years": [2021, 2022, 2023, 2024, 2025] if rid in ("R1", "R2") else [], "filings_reviewed": 40 if rid == "R4" else -1, "feed": "SEC EDGAR" if rid == "R4" else "",
            "reason": "No pending transaction" if rid == "R5" else ""}
    return {"evidence": ev, "retrieval_items": [item], "registers": [], "event_sweep": [], "extra_registers": [], "extra_trade_press": [], "documents_unavailable": []}


def model(kw):
    names = tools_of(kw)
    if "submit_synthesis" in names:
        return msg([tool_use("submit_synthesis", synthesis(), "toolu_s1")])
    text = first_text(kw)
    if "submit_task_result" in names:
        if "not accepted" in last_text(kw): raise AssertionError(last_text(kw))
        who = re.search(r"Subject: ([^\n(]+)", text).group(1).strip().replace(" ", "")
        return web_turn(task_payload(text, who))
    prefix = re.search(r"Evidence code prefix: ([A-Z])", text).group(1)
    sub = subject_submission(prefix)
    if "grade.py reported" in last_text(kw) or "peer-relative" in last_text(kw):
        return msg([tool_use("submit_subject_assessment", {**{k: [] for k in sub}, "documents_unavailable": []}, "toolu_fix")])
    for k in ("retrieval_items", "registers", "event_sweep", "extra_registers", "extra_trade_press"): sub[k] = []
    return msg([tool_use("submit_subject_assessment", sub, "toolu_sc")])


def test_plan_has_one_task_per_item_register_set_and_sweep_query():
    plan = RT.task_plan("Chevron", AS_OF, "energy")
    kinds = [t["kind"] for t in plan]
    assert kinds.count("item") == 7 and kinds.count("registers") == 1 and kinds.count("sweep") == len(RT.SPEC["event_sweep"])
    assert {i for t in plan for i in t["items"]} == {i["id"] for i in RT.SPEC["retrieval_items"]}
    es = next(t for t in plan if t["key"] == "ES01")
    assert es["query"].startswith("Chevron") and es["to"] == str(AS_OF) and es["frm"] == str(RT.months_before(AS_OF, 24))
    assert next(t for t in plan if t["key"] == "R4")["frm"] == str(RT.months_before(AS_OF, 36))


def test_assemble_numbers_evidence_dedupes_and_fills_the_log_itself():
    plan = {t["key"]: t for t in RT.task_plan("Chevron", AS_OF, "energy")}
    ev = lambda ref, url: {"ref": ref, "document": "d", "url": url, "date": "2026-03", "event_date": "2026-03-01"}
    results = [
        {"task": plan["R1"], "counts": {"web_search": 1, "web_fetch": 2, "results": 0}, "data": {"evidence": [ev("a1", "https://x/1")],
         "retrieval_items": [{"id": "R1", "status": "found", "documents": ["ar"], "queries": [], "years": [2025], "filings_reviewed": -1, "feed": "", "reason": ""}]}},
        {"task": plan["R4"], "counts": {"web_search": 1, "web_fetch": 0, "results": 0}, "data": {"evidence": [ev("b1", "https://x/1"), ev("b2", "https://x/2")],
         "retrieval_items": [{"id": "R4", "status": "found", "documents": ["feed"], "queries": [], "years": [], "filings_reviewed": 30, "feed": "EDGAR", "reason": ""}]}},
        {"task": plan["ES03"], "counts": {"web_search": 2, "web_fetch": 0, "results": 17}, "data": {"evidence": [ev("c1", "https://x/3")], "event_sweep": [{"id": "ES03", "hits": ["c1", "zz"]}]}}]
    seed = TK.assemble(results, "E", {})
    assert [e["code"] for e in seed["evidence"]] == ["E01", "E02", "E03"]  # the same URL and date read by two tasks keeps one number
    r4 = next(x for x in seed["retrieval_items"] if x["id"] == "R4")
    assert r4["from"] == str(RT.months_before(AS_OF, 36)) and r4["to"] == str(AS_OF) and r4["filings_reviewed"] == 30
    sw = seed["event_sweep"][0]
    assert sw["query"].startswith("Chevron") and sw["results_reviewed"] == 17 and sw["hits"] == ["E03"]  # counted by the engine; unknown refs dropped
    assert (sw["from"], sw["to"]) == (str(RT.months_before(AS_OF, 24)), str(AS_OF)) and seed["counts"] == {"web_search": 4, "web_fetch": 2, "results": 17}
    assert "E03 | 2026-03-01" in TK.ledger_text(seed)


def test_task_problems_catch_untyped_sources_missing_entries_and_unrun_searches():
    plan = {t["key"]: t for t in RT.task_plan("Chevron", AS_OF, "energy")}
    meta = {"as_of": str(AS_OF), "sector": "energy", "extra_trade_press": [], "extra_registers": []}
    bad = {"evidence": [{"ref": "a1", "document": "d", "url": "https://x", "date": "2026-03", "event_date": "2026-03-01", "excerpt": "e", "evidence_class": "direct",
                         "search_log": "", "source_type": "trade_press", "outlet": "MLex", "underlying_source_type": ""}], "event_sweep": []}
    p = TK._problems(plan["ES01"], bad, meta, {"web_search": 0, "web_fetch": 0, "results": 0})
    text = " | ".join(p)
    assert "MLex" in text and "event_sweep needs an entry with id ES01" in text and "web_search" in text
    ok = TK._problems(plan["ES01"], {"evidence": [], "event_sweep": [{"id": "ES01", "hits": []}]}, meta, {"web_search": 1, "web_fetch": 0, "results": 5})
    assert ok == []
    assert any("R5" in x for x in TK._problems(plan["R3"], {"evidence": [], "retrieval_items": [{"id": "R3", "status": "not_applicable", "reason": "x"}]}, meta, {"web_search": 1}))


def test_scoring_prompt_replaces_the_research_steps_with_the_ledger():
    p = T.scoring_prompt(today="t", period="2026-Q4", name="Chevron", ticker="CVX", role="r", peerset="p", prefix="E", as_of="a", behaviour_from="b", trend_from="c",
                         ledger="E01 | ledger line", ledger_count=1, ledger_n="01", next_n="02", factlist="  1.1: x", search_budget=12, fetch_budget=8)
    assert "E01 | ledger line" in p and "1. Retrieve the Rule 14" not in p and "2. Score each indicator" in p and "ledger below holds E01 to E01" in p
    assert "Run every event-sweep query" not in p and "extra_registers lists any sector register" not in p


def test_outside_in_runs_the_tasks_then_scores_and_the_log_passes_the_rules(monkeypatch):
    client = FakeClient(model); monkeypatch.setattr(C, "get_client", lambda: client)
    run = G.run_outside_in(COMPANY["name"], "CVX", PEER_ARGS, "2026-Q4", "director_request", None)
    task_calls = [k for k in client.calls if "submit_task_result" in tools_of(k)]
    scoring = [k for k in client.calls if "submit_subject_assessment" in tools_of(k)]
    per_subject = len(RT.SPEC["retrieval_items"]) - 1 + 1 + len(RT.SPEC["event_sweep"])
    assert len(task_calls) == 3 * per_subject and len(scoring) >= 3
    assert all(k["tools"][0]["max_uses"] == cfg.TASK_SEARCHES and k["tools"][1]["max_uses"] == cfg.TASK_FETCHES for k in task_calls)
    assert all(k["tools"][0]["max_uses"] == cfg.SCORER_SEARCHES for k in scoring)
    log = run["subjects"][0]["retrieval_log"]
    assert log["event_sweep"]["ES01"]["query"].startswith(COMPANY["name"].split()[0]) and log["event_sweep"]["ES01"]["results_reviewed"] == 3
    assert log["items"]["R4"]["from"] == str(RT.months_before(AS_OF, 36)) and set(log["items"]) == {i["id"] for i in RT.SPEC["retrieval_items"]}
    assert {k[0] for k in run["evidence"]} == {"E", "X", "B"} and run["run"]["rule_version"] == "1.3"


def test_task_model_and_effort_apply_to_retrieval_tasks_only(monkeypatch):
    monkeypatch.setattr(cfg, "TASK_MODEL", "claude-sonnet-5"); monkeypatch.setattr(cfg, "TASK_EFFORT", "medium")
    client = FakeClient(model); monkeypatch.setattr(C, "get_client", lambda: client)
    G.run_outside_in(COMPANY["name"], "CVX", PEER_ARGS, "2026-Q4", "director_request", None)
    task_calls = [k for k in client.calls if "submit_task_result" in tools_of(k)]
    other = [k for k in client.calls if "submit_task_result" not in tools_of(k)]
    assert task_calls and all(k["model"] == "claude-sonnet-5" and k["output_config"] == {"effort": "medium"} for k in task_calls)
    assert all(k["model"] == "claude-opus-5" and k["output_config"] == {"effort": cfg.EFFORT} for k in other)


def test_stray_registers_from_a_non_register_task_are_ignored():
    t = {"key": "R1", "kind": "item", "items": ["R1"]}
    r = {"task": t, "data": {"registers": [{"id": "X", "status": "searched", "hits": []}]}, "counts": {"web_search": 1, "web_fetch": 0, "results": 0}}
    assert TK.assemble([r], "E", {})["registers"] == []


def test_scores_must_cite_supplied_documents():
    from app.agents.nodes import Subject
    s = Subject("Acme", "", "company", "E"); s.docs = [{"label": f"Acme {x}", "file": f"{x}.pdf"} for x in "abcd"]
    ev = [{"code": "E01", "url": "provided: a.pdf"}]
    p = [m for m in s.accept({"evidence": ev}) if m.startswith("documents:")]
    assert p and "only 1 of the 4" in p[0] and "Acme b" in p[0]
    ev += [{"code": "E02", "url": "provided: b.pdf"}, {"code": "E03", "url": "provided: c.pdf"}]
    assert not [m for m in s.accept({"evidence": ev}) if m.startswith("documents:")]


class _Band:
    def note(self, *a): pass
    def set(self, *a): pass
    def tick(self, *a, **k): pass


def _subject(name="Acme"):
    return NS(name=name, ticker="ACM", role="company", short=name, model="m", prefix="E")


def _ctx(tmp_path=None):
    return {"meta": {"as_of": str(AS_OF), "sector": "general"}, "stop": None, "doc_names": {}}


def test_a_task_that_cannot_be_made_valid_is_recorded_as_not_covered_and_does_not_end_the_run(monkeypatch):
    from app.agents.client import ResearchInvalid
    plan = {t["key"]: t for t in RT.task_plan("Acme", AS_OF, "general")}
    def boom(*a, **k): raise ResearchInvalid("breaks the rules", ["x"])
    monkeypatch.setattr(TK, "_run_task_live", boom); monkeypatch.setattr(cfg, "TASK_CACHE", False)
    r = TK._run_task(_subject(), _ctx(), plan["ES05"], [], _Band(), 0)
    assert r["failed"] and r["data"] == {}
    seed = TK.assemble([r, TK._run_task(_subject(), _ctx(), plan["R1"], [], _Band(), 0), TK._run_task(_subject(), _ctx(), plan["REG"], [], _Band(), 0)], "E", {})
    assert [x["id"] for x in seed["event_sweep"]] == ["ES05"] and seed["event_sweep"][0]["hits"] == []  # the log is still complete
    assert any(x["id"] == "R1" and x["status"] == "unavailable" and x["queries"] for x in seed["retrieval_items"])
    assert len(seed["registers"]) == len(plan["REG"]["registers"]) and any("ES05" in d or "Event sweep" in d for d in seed["documents_unavailable"])  # and the coverage says so


def test_our_own_bug_in_one_task_is_isolated_but_a_rejected_key_still_stops_the_run(monkeypatch):
    from app.agents.client import ResearchError
    plan = {t["key"]: t for t in RT.task_plan("Acme", AS_OF, "general")}
    monkeypatch.setattr(cfg, "TASK_CACHE", False)
    monkeypatch.setattr(TK, "_run_task_live", lambda *a, **k: {}["date"])  # a KeyError, like the one that cost a run
    assert TK._run_task(_subject(), _ctx(), plan["ES01"], [], _Band(), 0)["failed"].startswith("KeyError")
    def rejected(*a, **k): raise ResearchError("The server's Microsoft Foundry API key was rejected.")
    monkeypatch.setattr(TK, "_run_task_live", rejected)
    with pytest.raises(ResearchError, match="rejected"): TK._run_task(_subject(), _ctx(), plan["ES01"], [], _Band(), 0)


def test_a_finished_task_is_read_back_instead_of_paid_for_again(monkeypatch):
    plan = {t["key"]: t for t in RT.task_plan("Acme", AS_OF, "general")}; calls = []
    def live(subject, ctx, t, names, band, i):
        calls.append(t["key"]); return {"task": t, "data": {"evidence": [], "event_sweep": [{"id": t["sweep"], "hits": []}]}, "counts": {"web_search": 2, "web_fetch": 0, "results": 9}}
    monkeypatch.setattr(TK, "_run_task_live", live); monkeypatch.setattr(cfg, "TASK_CACHE", True)
    a = TK._run_task(_subject("Cached Co"), _ctx(), plan["ES02"], [], _Band(), 0)
    b = TK._run_task(_subject("Cached Co"), _ctx(), plan["ES02"], [], _Band(), 0)
    assert calls == ["ES02"] and b["cached"] and b["counts"]["results"] == 9 and b["data"] == a["data"]
    TK._run_task(_subject("Other Co"), _ctx(), plan["ES02"], [], _Band(), 0)  # another subject is not served from it
    assert calls == ["ES02", "ES02"]


def test_malformed_entries_from_a_task_are_skipped_not_fatal():
    plan = {t["key"]: t for t in RT.task_plan("Acme", AS_OF, "general")}
    junk = {"task": plan["ES03"], "counts": {"web_search": 1, "web_fetch": 0, "results": 3}, "data": {"evidence": [None, "x", {"document": "no ref"}, {"ref": "a1", "document": "d", "url": "https://x", "date": "2026-01"}],
            "event_sweep": ["bad", {"id": "ES03", "hits": ["a1"]}], "registers": ["bad"], "retrieval_items": [None]}}
    seed = TK.assemble([junk], "E", {})
    assert [e["code"] for e in seed["evidence"]] == ["E01"] and seed["event_sweep"][0]["hits"] == ["E01"]


def test_a_rejected_key_is_reported_before_anything_is_read(monkeypatch):
    from app.agents import client as C
    class Auth(Exception): pass
    sdk = C.anthropic
    class Boom:
        class messages:
            @staticmethod
            def create(**k): raise sdk.AuthenticationError("bad", response=NS(status_code=401, headers={}, request=None), body={})
    monkeypatch.setattr(C, "get_client", lambda: Boom)
    with pytest.raises(C.ResearchError, match="key was rejected"): C.ping()
    class Fine:
        class messages:
            @staticmethod
            def create(**k): return NS()
    monkeypatch.setattr(C, "get_client", lambda: Fine); C.ping()


def _doc(name, text, subject=0):
    return {"name": name, "text": text, "pdf_b64": None, "subject": subject, "pages": 3, "sha": name,
            "ident": {"cite_as": "Chevron FY2025 10-K", "category": "Annual filing", "what": "Form 10-K", "period": "FY 2025", "date": "", "kind": "10-K", "flag": [], "use": "Use", "note": "", "source": "cover page"}}


def test_documents_prepared_in_the_background_reach_the_scoring_step(monkeypatch):
    """The documents are still being prepared while the retrieval tasks run; the scoring step waits for them and then sees them."""
    import threading
    from concurrent.futures import ThreadPoolExecutor
    monkeypatch.setattr(cfg, "MIN_DOC_CITES", 0)
    gate = threading.Event(); calls_before_ready = []
    client = FakeClient(model); monkeypatch.setattr(C, "get_client", lambda: client)
    def prepare():
        gate.wait(10); calls_before_ready.append(sum(1 for k in client.calls if "submit_task_result" in tools_of(k)))
        return [_doc("filing.pdf", "[page 1]\nFORM 10-K annual report fiscal year ended December 31, 2025\n" + "board " * 50)], {}
    pool = ThreadPoolExecutor(1); fut = pool.submit(prepare)
    threading.Timer(0.5, gate.set).start()
    run = G.run_outside_in(COMPANY["name"], "CVX", PEER_ARGS, "2026-Q4", "director_request", None, documents=fut)
    scoring = [k for k in client.calls if "submit_subject_assessment" in tools_of(k)]
    assert run["subjects"] and any("Chevron FY2025 10-K" in str(k["messages"][0]) for k in scoring)  # the label reached the scorer
    pool.shutdown()


def test_documents_that_cannot_be_prepared_stop_the_run_at_scoring_with_the_reason(monkeypatch):
    from concurrent.futures import ThreadPoolExecutor
    client = FakeClient(model); monkeypatch.setattr(C, "get_client", lambda: client)
    def prepare(): raise RuntimeError("some documents could not be read")
    pool = ThreadPoolExecutor(1); fut = pool.submit(prepare)
    with pytest.raises(C.ResearchError, match="could not be prepared: some documents could not be read"):
        G.run_outside_in(COMPANY["name"], "CVX", PEER_ARGS, "2026-Q4", "director_request", None, documents=fut)
    assert [k for k in client.calls if "submit_task_result" in tools_of(k)]  # the retrieval ran (and is saved) before the failure was reported
    pool.shutdown()
