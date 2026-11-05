"""Rules 16-17 (skill v1.3): the retrieval log, the fact sheet, source eligibility and time windows, plus the small report helpers."""
import copy
import datetime as dt
import sys
from pathlib import Path

import pytest

BACKEND = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND))
from app.domain import retrieval as RT, skill  # noqa: E402
from app.services import subjects  # noqa: E402

AS_OF = dt.date(2026, 10, 29)
IND_IDS = skill.IND_IDS


def complete_log(name="Acme"):
    items = {it["id"]: ({"status": "not_applicable", "reason": "No pending transaction"} if it["id"] == "R5" else
                        {"status": "found", "documents": ["doc"], "years": [2021, 2022, 2023, 2024, 2025],
                         **({"from": str(RT.months_before(AS_OF, 36)), "to": str(AS_OF), "filings_reviewed": 40} if it["id"] == "R4" else {})})
             for it in RT.SPEC["retrieval_items"]}
    pack = RT.pack_of("energy")
    regs = {r["id"]: ({"status": "not_applicable", "reason": "n/a"} if r.get("applies_if") else
                      {"status": "searched", "query": r["query"].replace("{company}", name), "date": str(AS_OF), "hits": []}) for r in pack["registers"]}
    es = {q["id"]: {"query": q["query"].replace("{company}", name), "from": str(RT.months_before(AS_OF, 24)), "to": str(AS_OF), "results_reviewed": 8, "hits": []}
          for q in RT.SPEC["event_sweep"]}
    facts = {i: {f: {"status": "found", "value": "v", "evidence": ["E01"]} for f, _ in RT.SPEC["fact_sheet"][i]} for i in IND_IDS}
    return {"items": items, "registers": regs, "event_sweep": es}, facts


def make_run(version="1.3", **evidence_over):
    log, facts = complete_log()
    ev = {"E01": {"document": "10-K", "date": "2026-02-20", "event_date": "2026-02-20", "evidence_class": "strong_direct", "source_type": "company",
                  "url": "https://www.sec.gov/x", "excerpt": "x"}}
    ev["E01"].update(evidence_over)
    cell = {"score": 3, "confidence": "Medium", "evidence": ["E01"], "rationale": "r"}
    sub = {"name": "Acme", "role": "company", "indicators": {i: {"board": dict(cell)} for i in IND_IDS}, "retrieval_log": log, "facts": facts}
    return {"run": {"rule_version": version, "as_of": str(AS_OF), "sector": "energy", "extra_registers": []}, "subjects": [sub], "evidence": ev, "coverage": {}}


def issues(run):
    p, w = [], []
    RT.check_run(run, p, w)
    return p, w


def test_a_complete_log_and_fact_sheet_pass():
    assert issues(make_run())[0] == []


def test_a_v1_2_run_is_not_held_to_the_log():
    run = make_run("1.2"); run["subjects"][0].pop("retrieval_log")
    assert issues(run) == ([], [])


def test_a_missing_log_or_entry_blocks():
    run = make_run(); run["subjects"][0].pop("retrieval_log")
    assert any("retrieval_log" in w and "missing" in m for _, w, m in issues(run)[0])
    run = make_run(); del run["subjects"][0]["retrieval_log"]["event_sweep"]["ES07"]
    assert any(w == "event_sweep.ES07" for _, w, _ in issues(run)[0])
    run = make_run(); del run["subjects"][0]["facts"]["1.4"]["cascade_below_csuite"]
    assert any(w == "facts.1.4.cascade_below_csuite" for _, w, _ in issues(run)[0])


def test_sweeps_must_reach_the_as_of_date_and_cover_the_window():
    run = make_run(); run["subjects"][0]["retrieval_log"]["event_sweep"]["ES01"]["to"] = "2026-09-01"
    assert any("must reach run.as_of" in m for _, _, m in issues(run)[0])
    run = make_run(); run["subjects"][0]["retrieval_log"]["event_sweep"]["ES02"]["from"] = "2025-06-01"
    assert any("must cover 24 months" in m for _, _, m in issues(run)[0])
    run = make_run(); run["subjects"][0]["retrieval_log"]["items"]["R4"]["to"] = "2026-10-25"  # inside the 7-day tolerance
    assert not any(w == "retrieval_log.R4" for _, w, _ in issues(run)[0])


def test_only_r5_may_be_not_applicable_and_gaps_need_queries():
    run = make_run(); run["subjects"][0]["retrieval_log"]["items"]["R3"] = {"status": "not_applicable", "reason": "x"}
    assert any("only for R5" in m for _, _, m in issues(run)[0])
    run = make_run(); run["subjects"][0]["retrieval_log"]["items"]["R8"] = {"status": "unavailable"}
    assert any("needs the queries" in m for _, _, m in issues(run)[0])


def test_general_sector_needs_a_named_register():
    run = make_run(); run["run"]["sector"] = "general"
    assert any(w == "run.extra_registers" for _, w, _ in issues(run)[0])


def test_source_type_and_class_must_agree():
    p, _ = issues(make_run(evidence_class="strong_direct", source_type="approved_news", outlet="Reuters"))
    assert any("not allowed for source_type 'approved_news'" in m for _, _, m in p)
    p, _ = issues(make_run(evidence_class="direct", source_type="approved_news", outlet="Some Blog Daily"))
    assert any("not on the approved news list" in m for _, _, m in p)
    p, _ = issues(make_run(evidence_class="direct", source_type="approved_news", outlet="Reuters", url="https://www.reuters.com/a"))
    assert p == []
    p, _ = issues(make_run(evidence_class="direct", source_type="company", url="https://www.reddit.com/r/x"))
    assert any("excluded by the guardrails" in m for _, _, m in p)
    p, _ = issues(make_run(source_type="made_up"))
    assert any("source_type must be one of" in m for _, _, m in p)


def test_windows_are_measured_from_as_of_with_event_date():
    run = make_run(event_date="2023-01-10", date="2023-01-10")  # outside the 24-month window of the behaviour indicators, inside the 5-year one
    p, _ = issues(run)
    assert any(i in w for _, w, _ in p for i in ("3.2", "4.1", "6.3")) and not any(w in ("3.4", "5.1", "6.2") for _, w, _ in p)
    run = make_run(); run["evidence"]["E01"].pop("event_date")
    assert any("needs event_date" in m for _, _, m in issues(run)[0])


def test_recent_is_recomputed_from_as_of():
    run = make_run(date="2026-09-01", event_date="2026-09-01", recent=False)
    issues(run)
    assert run["evidence"]["E01"]["recent"] is True
    run = make_run(date="2026-02-20", recent=True); issues(run)
    assert run["evidence"]["E01"]["recent"] is False


def test_inside_out_evidence_is_not_typed_or_windowed():
    run = make_run(); run["evidence"]["IO01"] = {"document": "minutes", "date": "2026-11-05", "evidence_class": "inside_out", "excerpt": "x"}
    assert issues(run)[0] == []


def test_lists_become_the_run_files_log_and_fact_sheet():
    lists = {"retrieval_items": [{"id": "R1", "status": "found", "documents": ["a"], "queries": [], "years": [2025], "from": "", "to": "", "filings_reviewed": -1, "feed": "", "reason": ""}],
             "registers": [{"id": "REG-E1", "status": "searched", "query": "q", "date": "2026-10-29", "hits": [], "reason": ""}],
             "event_sweep": [{"id": "ES01", "query": "q", "from": "2024-10-29", "to": "2026-10-29", "results_reviewed": 0, "hits": []}],
             "facts": [{"indicator": "1.4", "field": "f", "status": "found", "value": "v", "evidence": ["E01"], "where_searched": ""}]}
    log, facts = RT.log_from_lists(lists)
    assert log["items"]["R1"] == {"status": "found", "documents": ["a"], "years": [2025]}
    assert log["event_sweep"]["ES01"]["results_reviewed"] == 0 and facts["1.4"]["f"]["value"] == "v"


def test_the_checklist_names_every_query_and_fact():
    text = RT.checklist("Chevron", AS_OF, "energy")
    assert "ES14" in text and "REG-E1" in text and "attorney general sues Chevron" in text and str(RT.months_before(AS_OF, 24)) in text
    assert all(f in text for f, _ in RT.SPEC["fact_sheet"]["1.4"])


def test_sector_is_inferred_from_the_names():
    assert RT.sector_for("Chevron", "Acme") == "energy" and RT.sector_for("Kraft Heinz", "General Mills") == "general"


def test_names_are_capitalised_for_reports():
    d = subjects.display_name
    assert d("chevron") == "Chevron" and d("british petroleum") == "British Petroleum" and d("ExxonMobil") == "ExxonMobil" and d("BP") == "BP"


def test_document_counts_are_worded_by_kind():
    from app.services import deliverables as D
    out = D.doc_summary(["Board and committee minutes (12 months)", "Skills matrix and board/CEO succession plans", "Treasury and liquidity reports"])
    assert out.startswith("3 documents, all board minutes, packs and papers")
    out = D.doc_summary(["10K 2025.pdf", "chevron-proxy-statement-2026.pdf", "2026_2q_earnings_release.pdf"])
    assert "mainly" in out and "news" not in out and out.endswith("Dated 2025 to 2026.")
