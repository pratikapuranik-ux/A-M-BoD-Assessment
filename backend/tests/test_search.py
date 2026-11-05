"""Supplied documents: assigned to a subject by folder, kept per assessment, summarised, searched and read back (models stubbed)."""
import base64
import io
import types

import pytest

from app.agents import checks, conversation, settings as cfg
from app.agents.tools import SEARCH_TOOL
from app.api import uploads as U
from app.services import factsheet, library, search, storage, subjects

CO = {"name": "Chevron Corporation", "ticker": "CVX"}
PEERS = [{"name": "Exxon Mobil Corporation", "ticker": "XOM"}, {"name": "Shell plc", "ticker": "SHEL"}]


def test_files_are_assigned_by_folder_name():
    a = lambda p: subjects.assign(p, CO, PEERS)
    assert a("Energy Cluster test run/ExxxonMobil/10Q2q26.pdf") == 1  # a spelling slip is tolerated
    assert a("Energy/Shell/shell-annual-report.pdf") == 2
    assert a("Energy/Chevron/2025-supplement.pdf") == 0
    assert a("Energy/XOM/10-K.pdf") == 1  # a ticker works too
    assert a("loose-file.pdf") == 0 and a("Energy/Other/file.pdf") == 0  # unmatched files belong to the company
    assert a("Shell/Chevron/file.pdf") == 0  # the deepest folder wins


def test_search_finds_the_passage_and_the_page():
    text = "[page 1]\nIntroduction to the group.\n\n[page 2]\nThe board has eleven directors and seven are independent.\n\n[page 3]\nCapex guidance is 16 billion dollars."
    ix = search.Index([{"name": "ar.pdf", "text": text, "pages": 3}])
    hit = ix.search("how many independent directors")[0]
    assert hit["file"] == "ar.pdf" and "seven are independent" in hit["text"] and hit["page"] == 2
    assert ix.search("capex guidance")[0]["page"] == 3
    assert "No passage" in ix.answer("zebra") and "ar.pdf" in ix.answer("capex")
    assert "eleven directors" in ix.page("ar", 2) and "No page 9" in ix.page("ar", 9)
    assert ix.search("capex", file="other") == []


def test_long_documents_are_cut_into_passages_with_pages():
    text = "\n".join(f"[page {k}]\n" + ("word " * 300) for k in range(1, 7))
    ps = search.passages("big.pdf", text)
    assert len(ps) >= 3 and ps[0]["page"] == 1 and ps[-1]["page"] >= 5 and all(p["file"] == "big.pdf" for p in ps)


def test_library_is_kept_per_assessment(client):
    sc = library.scope("CVX", "2026-Q3"); other = library.scope("XOM", "2026-Q3"); k = library.sha(b"file")
    library.put(sc, k, {"text": "hello", "pages": 2, "size": 4})
    assert library.get(sc, k)["text"] == "hello" and library.get(other, k) is None  # nothing is shared between assessments
    library.update(sc, k, facts="sheet"); assert library.get(sc, k)["facts"] == "sheet" and library.get(sc, k)["text"] == "hello"


def test_reading_assigns_subjects_and_reuses_what_was_read(client, monkeypatch):
    calls = []
    real = U.documents.extract
    monkeypatch.setattr(U.documents, "extract", lambda *a, **k: calls.append(a[0]) or real(*a, **k))
    b64 = lambda t: base64.b64encode(t.encode()).decode()
    docs = [{"name": "Energy/Shell/a.txt", "data_b64": b64("Shell board facts")}, {"name": "b.txt", "data_b64": b64("Chevron board facts")}]
    who = lambda n: subjects.assign(n, CO, PEERS)
    sc = library.scope("CVX", "2026-Q3")
    out, probs = U.extract_documents(docs, scope=sc, who=who, as_text=True)
    assert not probs and {d["name"]: d["subject"] for d in out} == {"Energy/Shell/a.txt": 2, "b.txt": 0} and len(calls) == 2
    out, probs = U.extract_documents(docs, scope=sc, who=who, as_text=True)  # the same bytes again: not read again
    assert len(calls) == 2 and all(d.get("cached") for d in out) and out[0]["text"] == "Shell board facts"
    out, _ = U.extract_documents([dict(docs[1], subject=1)], scope=sc, who=who, as_text=True)
    assert out[0]["subject"] == 1  # what the director chose on the page wins over the folder


def test_fact_sheets_and_the_cross_document_review():
    long = "[page 1]\n" + "Revenue 12 billion. " * 3000
    docs = [{"name": "a.pdf", "text": long, "subject": 0}, {"name": "b.pdf", "text": long, "subject": 0}, {"name": "tiny.txt", "text": "short", "subject": 0}]
    asked = []
    def ask(prompt, label, max_tokens=0):
        asked.append(label); return "- Revenue 12 billion [p.1]" if "fact sheet" in label else "Inconsistencies: none"
    findings, notes = factsheet.prepare(docs, ["Chevron"], ask=ask)
    assert docs[0]["facts"].startswith("- Revenue") and docs[1]["facts"] and "facts" not in docs[2]  # a short file needs no sheet
    assert findings == {0: "Inconsistencies: none"} and not notes and any("review" in a for a in asked)
    def failing(prompt, label, max_tokens=0): raise factsheet.FactError("no key")
    d = [{"name": "c.pdf", "text": long, "subject": 0}]
    assert "no fact sheet" in factsheet.build_sheets(d, ask=failing)[0] and "facts" not in d[0]


def test_provided_documents_go_whole_when_small_and_searchable_when_large(monkeypatch):
    class S:  # a subject
        def __init__(self, name): self.name = name
    subs = [S("Chevron"), S("Shell")]
    small = [{"name": "s.txt", "text": "board facts", "subject": 0}]
    blocks, ix = checks._provided(subs, small)
    assert 0 in blocks and not ix and "board facts" in blocks[0][-1]["text"] and 1 not in blocks
    big = "[page 1]\n" + "Dividend policy and buybacks. " * 12000
    docs = [{"name": "ar.pdf", "text": big, "facts": "- Dividend 2.5 [p.1]", "subject": 1}, {"name": "s.txt", "text": "board facts", "subject": 0}]
    blocks, ix = checks._provided(subs, docs, {1: "Inconsistencies: none"})
    assert 1 in ix and 0 not in ix and "search_provided_documents" in blocks[1][0]["text"]
    assert "Dividend 2.5" in blocks[1][0]["text"] and "Inconsistencies: none" in blocks[1][0]["text"] and "Dividend policy and buybacks. Dividend" not in blocks[1][0]["text"]


def test_conversation_serves_search_calls_then_takes_the_submission():
    tool = lambda id, name, inp: types.SimpleNamespace(type="tool_use", id=id, name=name, input=inp)
    turns = [types.SimpleNamespace(stop_reason="tool_use", content=[tool("t1", "search_provided_documents", {"query": "capex", "file": ""})]),
             types.SimpleNamespace(stop_reason="tool_use", content=[tool("t2", "submit_x", {"ok": 1})])]
    c = conversation.Conv("t", [], "go", handlers={"search_provided_documents": lambda inp: "passage about " + inp["query"]})
    c.turn = lambda: turns.pop(0)
    got = []
    c.submit("submit_x", lambda inp: got.append(inp) or [])
    assert got == [{"ok": 1}]
    answer = [m for m in c.messages if m["role"] == "user" and isinstance(m["content"], list)][0]["content"][0]
    assert answer["tool_use_id"] == "t1" and answer["content"] == "passage about capex"


def test_each_fact_sheet_is_kept_as_soon_as_it_is_made(monkeypatch):
    long = "[page 1]\n" + "Revenue 12 billion. " * 3000
    docs = [{"name": f"{k}.pdf", "text": long + "x" * k, "subject": 0} for k in range(3)]
    kept = []
    def ask(prompt, label, max_tokens=0):
        if "0.pdf" in label: raise factsheet.FactError("busy")  # one document fails
        return "- fact"
    notes = factsheet.build_sheets(docs, ask=ask, on_sheet=lambda d: kept.append(d["name"]))
    assert sorted(kept) == ["1.pdf", "2.pdf"] and "facts" not in docs[0] and "0.pdf: no fact sheet" in notes[0]
    monkeypatch.setattr(factsheet, "MAX_INPUT_TOKENS", 30_000)  # a cap: documents that do not fit are searched only
    docs = [{"name": f"{k}.pdf", "text": long + "x" * k, "subject": 0} for k in range(3)]
    notes = factsheet.build_sheets(docs, ask=lambda p, l, max_tokens=0: "- fact")
    assert sum(1 for d in docs if d.get("facts")) == 1 and sum("over the" in n for n in notes) == 2


def test_job_messages_are_written_to_a_log_file(client):
    from app.services import jobs
    j = jobs.submit("t", lambda job: job.update(5, "Extracting key facts: 3 of 9 sections done"))
    jobs.wait(j.id)
    text = (storage.root() / "logs" / "jobs.log").read_text(encoding="utf-8")
    assert j.id in text and "Extracting key facts: 3 of 9 sections done" in text and "Done" in text


def test_only_the_companys_documents_get_fact_sheets_by_default(monkeypatch):
    from app.services import runs
    long = "[page 1]\n" + "Revenue 12 billion. " * 3000
    docs = [{"name": "co.pdf", "text": long, "subject": 0}, {"name": "peer.pdf", "text": long, "subject": 1}]
    seen = []
    def ask(prompt, label, max_tokens=0, say=None):
        seen.append(label); return "- fact"
    monkeypatch.setattr(factsheet, "ask_text", ask)
    job = types.SimpleNamespace(update=lambda *a, **k: None)
    monkeypatch.delenv("BOARD_DOC_ANALYSIS", raising=False)
    runs.analyse_documents(job, docs, ["Chevron", "Shell"], "2026-Q4", "CVX")
    assert docs[0].get("facts") and "facts" not in docs[1] and not any("peer.pdf" in s for s in seen)
    monkeypatch.setenv("BOARD_DOC_ANALYSIS", "all"); docs[0].pop("facts")
    runs.analyse_documents(job, docs, ["Chevron", "Shell"], "2026-Q4", "CVX")
    assert docs[0].get("facts") and docs[1].get("facts")
    monkeypatch.setenv("BOARD_DOC_ANALYSIS", "off"); docs[0].pop("facts"); docs[1].pop("facts")
    assert runs.analyse_documents(job, docs, ["Chevron", "Shell"], "2026-Q4", "CVX") == {} and "facts" not in docs[0]


def test_reads_of_supplied_documents_count_for_the_retrieval_review(monkeypatch):
    from app.agents import nodes
    s = nodes.Subject("Chevron", "CVX", "company", "E")
    assert set(s.counts) >= {"web_fetch", "doc_search", "doc_page"}
    assert nodes.SUBSCRIPTION.search("ISS and Glass Lewis vote recommendation reports") and nodes.SUBSCRIPTION.search("Moody's full credit opinion")
    assert not nodes.SUBSCRIPTION.search("Board terms of reference before April 2026") and cfg.REVIEW_ROUNDS == 1


def test_the_research_prompt_carries_the_scoring_discipline():
    from app.agents.tools import render_prompt
    text = render_prompt("subject.md", today="2026-11-04", as_of="2026-11-04", checklist="CHECKLIST", period="2026-Q4", name="Chevron", ticker="CVX", role="the company being assessed", peerset="x",
                         prefix="E", behaviour_from="2024-11", trend_from="FY2021", search_budget=60, fetch_budget=60)
    assert "Anchor test" in text and "Direct support" in text and "Checkable limits" in text
    assert "chief executive and other executive officers" in text and "$" not in text.replace("2026", "")


def test_an_unexpected_error_is_logged_and_answered_as_json(client, monkeypatch):
    from fastapi.testclient import TestClient
    from app.services import repo
    def boom(*a, **k): raise RuntimeError("disk exploded")
    monkeypatch.setattr(repo, "list_ids", boom)
    r = TestClient(client.app, raise_server_exceptions=False).get("/api/companies")
    assert r.status_code == 500 and "disk exploded" in r.json()["error"] and "errors.log" in r.json()["error"]
    text = (storage.root() / "logs" / "errors.log").read_text(encoding="utf-8")
    assert "GET /api/companies" in text and "RuntimeError: disk exploded" in text


def test_anchor_audit_reads_rationales_against_the_anchors(client, monkeypatch):
    from app.api import assessments
    from app.services import audit, repo
    seen = {}
    def ask(prompt, label):
        seen["prompt"] = prompt
        return 'Here you go: [{"id": "5.4", "strict_score": 3, "reason": "the rationale names the Mixed anchor"}, {"id": "1.1", "strict_score": 2, "reason": "ok"}]'
    monkeypatch.setattr(audit, "_ask", ask)
    items = [{"id": "5.4", "name": "Response to pressure", "score": 4, "rationale": "Cost came first: the Mixed anchor."},
             {"id": "1.1", "name": "Customer evidence", "score": 2, "rationale": "Volumes only."}, {"id": "1.2", "name": "x", "score": None, "rationale": ""}]
    rows = audit.audit(items)
    assert [(r["id"], r["score"], r["strict_score"]) for r in rows] == [("5.4", 4, 3), ("1.1", 2, 2)]  # an indicator with no score is not audited
    assert "<anchor_3>" in seen["prompt"] and "Cost came first" in seen["prompt"] and 'id="1.2"' not in seen["prompt"]
    monkeypatch.setattr(assessments, "_company", lambda cid: None)
    monkeypatch.setattr(repo, "view", lambda cid, mode=None: {"ind": {"5.4": {"name": "Response to pressure", "score": 4, "rationale": "Cost came first: the Mixed anchor."}}})
    r = client.post("/api/companies/demo/anchor-audit")
    assert r.status_code == 200 and r.json()["differs"] == 1 and r.json()["audit"][0]["strict_score"] == 3


def test_the_prompt_reads_5_4_and_5_2_as_the_framework_defines_them():
    from app.agents.tools import render_prompt
    text = render_prompt("subject.md", today="2026-11-04", as_of="2026-11-04", checklist="CHECKLIST", period="2026-Q4", name="Chevron", ticker="CVX", role="the company being assessed", peerset="x",
                         prefix="E", behaviour_from="2024-11", trend_from="FY2021", search_budget=60, fetch_budget=60)
    assert "which lever" in text and "score 5.4 at 3 or below" in text and "8-K Item 5.02 filings of the last five years" in text and "waiver or extension of an age or term limit" in text


def test_the_1_4_ruling_reaches_every_research_step():
    from app.agents import tools
    text = tools.system_blocks()[0]["text"]
    assert "Scoring ruling (methodology owner)" in text and "Safety, operating, production, cost, emissions" in text and "product quality, service levels" in text


def test_the_1_4_ruling_can_be_switched_off(monkeypatch):
    from app.agents import tools
    try:
        monkeypatch.delenv("BOARD_RULING_1_4", raising=False); tools.system_blocks.cache_clear()
        on = tools.system_blocks()[0]["text"]
        assert "Scoring ruling (methodology owner)" in on and "<!--" not in on and tools.ruling_1_4_on()
        monkeypatch.setenv("BOARD_RULING_1_4", "off"); tools.system_blocks.cache_clear()
        off = tools.system_blocks()[0]["text"]
        assert "Scoring ruling" not in off and "product quality, service levels" not in off and "<!--" not in off and not tools.ruling_1_4_on()
        assert "### 1.4 Customer-linked accountability" in off and "Board lens:** Has the compensation committee put a meaningful customer or quality metric" in off  # the rest of 1.4 stays
        assert len(on) > len(off)
    finally:
        monkeypatch.delenv("BOARD_RULING_1_4", raising=False); tools.system_blocks.cache_clear()


def test_old_search_and_page_results_are_cut_when_the_context_grows():
    c = conversation.Conv("t", [], "go", handlers={"search_provided_documents": lambda inp: "x"})
    for k in range(15):
        c.served.add(f"t{k}")
        c.messages.append({"role": "assistant", "content": []})
        c.messages.append({"role": "user", "content": [{"type": "tool_result", "tool_use_id": f"t{k}", "content": "passage " * 500}]})
    c.messages.append({"role": "user", "content": [{"type": "tool_result", "tool_use_id": "other", "content": "keep me"}]})  # not a document result
    assert c.prune_served(3) == 12
    results = [b for m in c.messages if m["role"] == "user" and isinstance(m["content"], list) for b in m["content"]]
    assert sum(b["content"] == conversation.DOC_STUB for b in results) == 12
    assert results[-4]["content"].startswith("passage") and results[-1]["content"] == "keep me"  # the newest three and the other tool result stay
    assert c.prune_served(3) == 0  # already cut results are not cut again


def test_a_rejected_prompt_is_cut_harder_up_to_twice():
    import anthropic, httpx
    c = conversation.Conv("t", [], "go", handlers={"read_provided_page": lambda inp: "x"})
    for k in range(20):
        c.served.add(f"t{k}")
        c.messages.append({"role": "user", "content": [{"type": "tool_result", "tool_use_id": f"t{k}", "content": "page " * 800}]})
    resp = httpx.Response(400, request=httpx.Request("POST", "http://x"))
    boom = anthropic.BadRequestError("prompt is too long: 1682773 tokens > 1000000 maximum", response=resp, body={"error": {"type": "invalid_request_error"}})
    calls = []
    def fake_retry(fn, label, stop=None, say=None):
        calls.append(len(calls))
        if len(calls) <= 2: raise boom
        return "accepted"
    from app.agents import client as cl
    old = cl.call_with_retry; cl.call_with_retry = fake_retry
    try: assert c._request() == "accepted"  # rejected twice, cut harder each time, accepted on the third try
    finally: cl.call_with_retry = old
    stubbed = sum(1 for m in c.messages if isinstance(m["content"], list) for b in m["content"] if b.get("content") == conversation.DOC_STUB)
    assert len(calls) == 3 and stubbed == 20 and c.shrink == 2  # first cut kept 3, the second kept none


def test_a_page_read_is_limited():
    ix = search.Index([{"name": "big.txt", "text": "word " * 20000}])
    out = ix.page("big", 1)
    assert len(out) < search.PAGE_CHARS + 300 and "first 12000 characters" in out
