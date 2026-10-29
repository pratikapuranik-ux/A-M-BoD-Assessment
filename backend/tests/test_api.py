"""API tests (port of tests/test_server.py): views, import end to end, API smoke on an empty start, mocked research, jobs,
ids, periods, survey guardrails, uploads. Temp SQLite + temp storage (see conftest.py). No model calls: research is mocked.

    cd backend && python -m pytest tests/test_api.py
"""
import base64
import copy
import io
import json
import os
import re
import threading
import types
from pathlib import Path

import pytest

from app.domain import view as convert
from app.services import documents as extract
from app.services import jobs, repo, runs, storage

FIX = Path(__file__).parent / "fixtures"


def load(name):
    with open(FIX / name, encoding="utf-8") as f: return json.load(f)


def wait_job(c, jid):
    jobs.wait(jid, 600); return c.get(f"/api/jobs/{jid}").json()


def renamed(run, name="Testco Corporation", ticker="TST"):
    run = copy.deepcopy(run); comp = convert.company_of(run); comp["name"] = name; comp["ticker"] = ticker; run.pop("history", None); run["run"].pop("simulated", None); return run


def mock_research(**kw):
    class ResearchError(RuntimeError): pass
    class ResearchInvalid(ResearchError):
        def __init__(self, msg, problems=()): super().__init__(msg); self.problems = list(problems)
    return types.SimpleNamespace(research_enabled=lambda: (True, "mock"), ResearchError=ResearchError, ResearchInvalid=ResearchInvalid, **kw)


@pytest.fixture
def mocked(monkeypatch):
    def install(mod): monkeypatch.setattr(runs, "research_module", lambda: mod); return mod
    return install


# ---------------- convert ----------------

def test_view_from_fixture_runs():
    V = json.loads(json.dumps(convert.to_view(load("outside_in_run.json"), load("inside_out_run.json"), None, {"id": "fixture"})))
    assert V["meta"]["prefixes"] == {"E": "Chevron", "X": "ExxonMobil", "B": "BP"} and V["meta"]["id"] == "fixture"
    assert set(V) >= set(convert.base_view()) and "simulated" not in json.dumps(V["meta"]) and "final" not in V["io"]


def test_short_names():
    assert convert.short_name("Exxon Mobil (ExxonMobil Holdings Corporation)") == "ExxonMobil"
    assert convert.short_name("BP p.l.c.") == "BP" and convert.short_name("Chevron Corporation") == "Chevron"


# ---------------- API ----------------

def test_api_smoke(client):
    h = client.get("/api/health").json(); assert h["ok"] is True and "enabled" in h["research"] and "reason" in h["research"]
    assert client.get("/api/framework").json()["rule_version"] == "1.2"
    assert client.get("/api/companies").json() == [], "a fresh start must have no companies"
    r = client.get("/api/companies/nope/view"); assert r.status_code == 404 and "error" in r.json()
    assert client.get("/api/jobs/nope").status_code == 404 and client.delete("/api/companies/nope").status_code == 404
    r = client.get("/api/nothing/here"); assert r.status_code == 404 and r.json()["error"] == "no API route /api/nothing/here"
    assert client.get("/").status_code == 200
    r = client.post("/api/research", content=b"{", headers={"content-type": "application/json"}); assert r.status_code == 400 and r.json()["error"] == "request body must be JSON"


def test_research_disabled_reports_reason_and_persists_nothing(client, monkeypatch):
    monkeypatch.setattr(runs, "research_module", lambda: types.SimpleNamespace(research_enabled=lambda: (False, "no key")))
    assert client.get("/api/health").json()["research"] == {"enabled": False, "reason": "no key"}
    r = client.post("/api/research", json={"company": "Offco", "ticker": "OFF", "peers": [{"name": "A"}, {"name": "B"}], "period": "2026-Q4"})
    assert r.status_code == 503 and r.json()["error"] == "research is not available: no key" and r.json()["problems"] == []
    assert repo.list_ids() == []


def test_import_end_to_end(client):
    bad = renamed(load("outside_in_run.json")); convert.company_of(bad)["indicators"]["1.1"]["board"]["score"] = 7
    r = client.post("/api/companies/import", json={"outside_in": bad}); assert r.status_code == 422 and any("not an integer" in p for p in r.json()["problems"])
    sim = renamed(load("outside_in_run.json")); sim["run"]["simulated"] = True
    r = client.post("/api/companies/import", json={"outside_in": sim}); assert r.status_code == 422 and any("simulated" in p for p in r.json()["problems"])
    oi = renamed(load("outside_in_run.json")); prior = renamed(load("prior_2026-Q3_simulated_run.json"))
    r = client.post("/api/companies/import", json={"outside_in": oi, "priors": [prior]}); assert r.status_code == 200, r.text
    body = r.json(); assert body["id"] == "testco"
    j = wait_job(client, body["job_id"]); assert j["status"] == "done", j
    assert client.post("/api/companies/import", json={"outside_in": oi}).status_code == 409
    s = next(x for x in client.get("/api/companies").json() if x["id"] == "testco")
    assert s["stages"] == {"outside_in": True, "inside_out": False} and s["source"] == "imported" and s["prior_period"] == "2026-Q3"
    v = client.get("/api/companies/testco/view").json()
    assert v["meta"]["company"] == "Testco Corporation" and v["meta"]["short"] == "Testco" and v["io"] is None and v["prior"]["period"] == "2026-Q3"
    assert set(v["files"]) == {"oi_docx", "oi_html", "prior_docx", "quest"}
    for k, url in v["files"].items():
        # the dashboards render in an iframe, so they are served inline; the Word files download
        want = "inline" if k.endswith("_html") else "attachment"
        r = client.get(url); assert r.status_code == 200 and len(r.content) > 1000 and want in r.headers.get("content-disposition", ""), k
    assert client.get("/api/companies/testco/view?mode=internal_dry_run").json()["meta"]["mode"] == "internal_dry_run"
    assert client.get("/api/companies/testco/view?mode=bogus").status_code == 400 and client.get("/api/companies/testco/files/nope").status_code == 404
    assert [(p["period"], p["stage"]) for p in v["priors"]] == [("2026-Q3", "outside_in")]
    later = copy.deepcopy(oi); later["run"]["period"] = "2027-Q1"; repo.new_period("testco", later)  # a later quarter joins the earlier ones
    v = client.get("/api/companies/testco/view").json()
    assert v["meta"]["period"] == "2027-Q1" and [p["period"] for p in v["priors"]] == ["2026-Q3", "2026-Q4"] and v["prior"]["period"] == "2026-Q4"
    assert client.delete("/api/companies/testco").json()["ok"] and client.get("/api/companies/testco/view").status_code == 404
    assert not (storage.root() / "testco").exists()


def test_import_replace(client):
    oi = renamed(load("outside_in_run.json"), "Replaceco", "RPL")
    r = client.post("/api/companies/import", json={"outside_in": oi}); assert wait_job(client, r.json()["job_id"])["status"] == "done"
    r = client.post("/api/companies/import", json={"outside_in": oi, "replace": True}); assert r.status_code == 200 and wait_job(client, r.json()["job_id"])["status"] == "done"
    assert client.delete("/api/companies/replaceco").status_code == 200


def test_research_mocked(client, mocked):
    calls = {}
    def run_outside_in(company, ticker, peers, period, mode, progress):
        calls["oi"] = (company, ticker, peers, period, mode); progress(50, "half way"); return renamed(load("outside_in_run.json"), "Mockco Inc.", "MCK")
    def run_inside_out(oi_run, documents, answers, ratings, progress):
        calls["io"] = (documents, answers, ratings); progress(50, "reading")
        io_run = renamed(load("inside_out_run.json"), "Mockco Inc.", "MCK"); io_run["run"]["simulated"] = False; io_run.pop("self_assessment_answers", None); return io_run
    mocked(mock_research(run_outside_in=run_outside_in, run_inside_out=run_inside_out))
    c = client
    assert c.get("/api/health").json()["research"] == {"enabled": True, "reason": "mock"}
    r = c.post("/api/research", json={"company": "Mockco Inc.", "ticker": "MCK", "peers": [{"name": "A"}], "period": "2026-Q4", "mode": "director_request"})
    assert r.status_code == 400 and r.json()["problems"]
    r = c.post("/api/research", json={"company": "Mockco Inc.", "ticker": "MCK", "peers": [{"name": "A", "ticker": "A"}, {"name": "B", "ticker": "B"}], "period": "2026-Q4", "mode": "director_request"})
    j = wait_job(c, r.json()["job_id"]); assert j["status"] == "done", j
    cid = j["result"]["company_id"]; assert cid == "mockco" and calls["oi"][3] == "2026-Q4"
    assert any("half way" in x for x in j["log"])
    assert next(x for x in c.get("/api/companies").json() if x["id"] == cid)["source"] == "research"
    doc = {"slot": 1, "name": "minutes.txt", "mime": "text/plain", "data_b64": base64.b64encode(b"Board minutes: buyback approved").decode()}
    assert c.post(f"/api/companies/{cid}/inside-out", json={"documents": [dict(doc, slot=99)]}).status_code == 400
    # anonymity guardrail: no inside-out view until three people have answered the self-assessment
    r = c.post(f"/api/companies/{cid}/inside-out", json={"mode": "director_request", "documents": [doc]})
    assert r.status_code == 200, r.json()  # zero responses is allowed: the run uses the board documents alone
    assert wait_job(c, r.json()["job_id"])["status"] == "done" and not any(calls["io"][1].values())
    repo.delete_run(cid, "inside_out")
    r = c.post(f"/api/companies/{cid}/inside-out", json={"documents": []}); assert r.status_code == 409 and "add board documents" in r.json()["error"]
    st =c.post(f"/api/companies/{cid}/survey/invite", json={"emails": ["a@example.org", "b@example.org", "c@example.org", "a@example.org"]}).json()
    assert len(st["invites"]) == 3 and st["responses"] == 0 and all("?take=" in i["link"] for i in st["invites"])
    assert c.post(f"/api/companies/{cid}/survey/invite", json={"emails": ["not-an-email"]}).status_code == 400
    tok = [i["token"] for i in st["invites"]]
    form = c.get(f"/api/survey/{tok[0]}").json()
    assert form["company"] == "Mockco Inc." and len(form["questions"]) == 12 and set(form) == {"company", "period", "responded", "min", "questions"}
    for k, t in enumerate(tok[:2]):
        assert c.post(f"/api/survey/{t}", json={"answers": {"1": f"Customer item {k}"}, "ratings": {"1": 3}}).status_code == 200
    assert c.post(f"/api/survey/{tok[0]}", json={"answers": {"1": "again"}}).status_code == 409
    assert c.post(f"/api/companies/{cid}/inside-out", json={"documents": [doc]}).status_code == 409
    assert c.post(f"/api/companies/{cid}/survey/responses", json={"answers": {"2": "Paper return"}, "ratings": {"2": 5}}).json()["responses"] == 3
    stored = json.dumps(repo.load_survey(cid)["responses"])
    assert not any(t in stored for t in tok) and "example.org" not in stored  # responses carry no link to who answered
    assert c.get("/api/survey/nope").status_code == 404
    r = c.post(f"/api/companies/{cid}/inside-out", json={"mode": "director_request", "documents": [doc]})
    assert r.status_code == 200, r.text
    j = wait_job(c, r.json()["job_id"]); assert j["status"] == "done", j
    d = calls["io"][0][0]; assert d["slot"] == 1 and "buyback" in d["text"] and d["pdf_b64"] is None
    a1 = calls["io"][1]["1"]; assert "Customer item 0" in a1 and "Customer item 1" in a1 and a1.count("Response ") == 2 and re.fullmatch(r"Response [123]: Paper return", calls["io"][1]["2"])
    v = c.get(f"/api/companies/{cid}/view").json()
    # anonymity: the answers reach the research step but are never stored in the run or exposed in the view
    assert "Customer item" not in json.dumps(v["io"]) and "self_assessment_answers" not in json.dumps(repo.read_run(cid, "inside_out"))
    assert "io_docx" in v["files"] and "pack" not in v["files"]
    assert c.delete(f"/api/companies/{cid}").status_code == 200


def test_company_ids(client):
    assert convert.slug("株式会社トヨタ", "7203") == "7203" and re.fullmatch(r"co-[0-9a-f]{10}", convert.slug("Сбербанк"))
    assert convert.slug("Сбербанк") != convert.slug("Газпром")
    long = "Samsung Electronics Co., Ltd. and Very Long Subsidiary Name International Holdings Incorporated"
    s = convert.slug(long); assert len(s) <= 56 and storage.valid_id(s) and storage.valid_id(s + "-99")
    r = client.post("/api/companies/import", json={"outside_in": renamed(load("outside_in_run.json"), long, "SMSN")})
    assert r.status_code == 200, r.text
    assert wait_job(client, r.json()["job_id"])["status"] == "done" and repo.exists(r.json()["id"])
    assert client.delete(f"/api/companies/{r.json()['id']}").status_code == 200


def test_import_rejects_bad_priors(client):
    oi = renamed(load("outside_in_run.json"), "Priorco"); p = renamed(load("prior_2026-Q3_simulated_run.json"), "Priorco")
    later = copy.deepcopy(p); later["run"]["period"] = "2027-Q1"
    r = client.post("/api/companies/import", json={"outside_in": oi, "priors": [p, copy.deepcopy(p), later]})
    assert r.status_code == 422 and any("more than once" in x for x in r.json()["problems"]) and any("2027-Q1 is not earlier" in x for x in r.json()["problems"])


def test_new_period_rules(client):
    oi = renamed(load("outside_in_run.json"), "Periodco", "PRD"); io = renamed(load("inside_out_run.json"), "Periodco", "PRD")
    cid = repo.create(oi, io); repo.add_response(cid, {"1": "a"}, {})
    assert repo.new_period(cid, copy.deepcopy(oi)) is not None, "a same-period refresh returns a backup"
    assert len(repo.load_survey(cid)["responses"]) == 1 and repo.read_run(cid, "inside_out") and repo.priors(cid) == []
    early = copy.deepcopy(oi); early["run"]["period"] = "2026-Q3"
    with pytest.raises(ValueError, match="earlier than the 2026-Q4"): repo.new_period(cid, early)
    later = copy.deepcopy(oi); later["run"]["period"] = "2027-Q1"
    assert repo.new_period(cid, later) is None
    assert repo.load_survey(cid) == {"invites": [], "responses": []} and repo.read_run(cid, "inside_out") is None
    assert [p["run"]["stage"] for p in repo.priors(cid)] == ["inside_out"]
    with pytest.raises(ValueError): repo.new_period(cid, copy.deepcopy(oi))
    repo.delete_company(cid)


def test_restore_after_same_period_refresh(client):
    oi = renamed(load("outside_in_run.json"), "Restoreco", "RST"); cid = repo.create(oi)
    new = copy.deepcopy(oi); new["run"]["mode"] = "internal_dry_run"
    backup = repo.new_period(cid, new); assert repo.read_run(cid, "outside_in")["run"]["mode"] == "internal_dry_run"
    repo.restore(cid, backup); assert repo.read_run(cid, "outside_in") == oi
    repo.delete_company(cid)


def test_research_is_fresh_by_default(client, mocked):
    mocked(mock_research(run_outside_in=lambda company, ticker, peers, period, m, progress: renamed(load("outside_in_run.json"), company, ticker), run_inside_out=None))
    peers = [{"name": "A", "ticker": "A"}, {"name": "B", "ticker": "B"}]
    go = lambda: wait_job(client, client.post("/api/research", json={"company": "Freshco", "ticker": "FSH", "peers": peers, "period": "2026-Q4"}).json()["job_id"])
    a, b = go()["result"]["company_id"], go()["result"]["company_id"]
    assert a != b, "a second run for the same company is a new standalone assessment, not a refresh of the saved one"
    assert repo.priors(a) == [] and repo.priors(b) == [], "no saved earlier quarter is attached"
    for cid in (a, b): assert client.delete(f"/api/companies/{cid}").status_code == 200


def test_jobs_ids_and_refresh_via_research(client, mocked, monkeypatch):
    monkeypatch.setenv("NEXUS_REUSE_HISTORY", "1")  # the legacy "new period of a company on file" behaviour is opt-in
    gate = threading.Event(); mode = {"bad": False, "raise": None}
    def run_outside_in(company, ticker, peers, period, m, progress):
        gate.wait(30)
        if mode["raise"]: raise mode["raise"]
        r = renamed(load("outside_in_run.json"), company, ticker); r["run"]["period"] = period
        if mode["bad"]: convert.company_of(r)["indicators"]["1.1"]["board"]["score"] = 7
        return r
    mod = mocked(mock_research(run_outside_in=run_outside_in, run_inside_out=None)); c = client
    peers = [{"name": "A", "ticker": "A"}, {"name": "B", "ticker": "B"}]
    go = lambda name, ticker="GTC", period="2026-Q4": c.post("/api/research", json={"company": name, "ticker": ticker, "peers": peers, "period": period})
    try:
        a = go("Gateco Inc.").json()["job_id"]
        r = go("Gateco Inc."); assert r.status_code == 409 and r.json()["job_id"] == a, "a second start returns the live job"
        gate.set(); j = wait_job(c, a); assert j["status"] == "done" and j["result"]["company_id"] == "gateco", j
        j = wait_job(c, go("Gateco Ltd", "GTX").json()["job_id"]); assert j["result"]["company_id"] == "gateco-2", "a different company with the same slug"
        assert repo.load_meta("gateco")["ticker"] == "GTC"
        gate.clear(); a = go("Gateco Inc.").json()["job_id"]
        r = c.delete("/api/companies/gateco"); assert r.status_code == 409 and r.json()["error"] == "a job is running for this company"
        r = c.post("/api/companies/gateco/inside-out", json={}); assert r.status_code == 409 and r.json()["job_id"] == a
        gate.set(); assert wait_job(c, a)["status"] == "done"
        r = go("Gateco Inc.", period="2026-Q3"); assert r.status_code == 409 and "earlier than the 2026-Q4" in r.json()["error"]
        before = repo.read_run("gateco", "outside_in"); mode["bad"] = True
        j = wait_job(c, go("Gateco Inc.").json()["job_id"]); assert j["status"] == "error" and "previous 2026-Q4 assessment was kept" in j["error"]
        assert repo.read_run("gateco", "outside_in") == before and "problems" not in repo.load_meta("gateco")
        mode["bad"] = False; mode["raise"] = mod.ResearchInvalid("The scores still break 1 rule(s).", [("Gateco Inc.", "1.1/board", "score 5 needs more")])
        j = wait_job(c, go("Gateco Inc.").json()["job_id"])
        assert j["error"] == "The scores still break 1 rule(s)." and j["problems"] == ["[Gateco Inc.] 1.1/board: score 5 needs more"]
        assert repo.read_run("gateco", "outside_in") == before, "a failed research run persists nothing"
        for cid in ("gateco", "gateco-2"): assert c.delete(f"/api/companies/{cid}").status_code == 200
    finally:
        gate.set()


def test_failed_research_on_new_company_stores_nothing(client, mocked):
    def run_outside_in(*a, **k): raise mock.ResearchError("the model refused")
    mock = mocked(mock_research(run_outside_in=run_outside_in, run_inside_out=None))
    r = client.post("/api/research", json={"company": "Failco", "ticker": "FLC", "peers": [{"name": "A"}, {"name": "B"}], "period": "2026-Q4"})
    j = wait_job(client, r.json()["job_id"]); assert j["status"] == "error" and j["error"] == "the model refused"
    assert not repo.exists("failco") and repo.list_ids() == []


def test_research_with_own_documents(client, mocked):
    got = {}
    def run_outside_in(company, ticker, peers, period, m, progress, documents=None):
        got["docs"] = documents; r = renamed(load("outside_in_run.json"), company, ticker); r["run"]["period"] = period; return r
    mocked(mock_research(run_outside_in=run_outside_in, run_inside_out=None))
    body = {"company": "Docco plc", "ticker": "DOC", "peers": [{"name": "A"}, {"name": "B"}], "period": "2026-Q4"}
    r = client.post("/api/research", json=dict(body, documents=[{"name": "notes.txt", "data_b64": base64.b64encode(b"Board met twice.").decode()}]))
    j = wait_job(client, r.json()["job_id"]); assert j["status"] == "done", j
    assert [(d["name"], d["text"]) for d in got["docs"]] == [("notes.txt", "Board met twice.")]
    r = client.post("/api/research", json=dict(body, documents=[{"name": "x.exe", "data_b64": "eA=="}]))
    assert r.status_code == 400 and "x.exe: unsupported file type" in r.json()["problems"][0]
    assert client.delete(f"/api/companies/{j['result']['company_id']}").status_code == 200


def test_leftovers_are_never_adopted(client, monkeypatch):
    d = storage.company_dir("leftco"); (d / "out").mkdir(parents=True); (d / "out" / "old.docx").write_bytes(b"old")
    monkeypatch.setattr(storage, "_rmtree", lambda _d: False)  # OneDrive holds the folder
    cid = repo.create(renamed(load("outside_in_run.json"), "Leftco"), cid="leftco")
    assert repo.load_survey(cid)["responses"] == [] and repo.priors(cid) == [] and not (storage.out_dir(cid) / "old.docx").exists()
    assert any(p.name.startswith("leftco.deleted-") for p in storage.root().iterdir()) and repo.list_ids().count("leftco") == 1
    repo.add_response(cid, {"1": "secret"}, {}); monkeypatch.undo(); repo.delete_company(cid)
    assert not repo.exists(cid) and repo.response_count(cid) == 0, "answers and the company go together"


def test_survey_guardrails(client, monkeypatch):
    c = client; cid = repo.create(renamed(load("outside_in_run.json"), "Surveyco plc", "SVY")); u = f"/api/companies/{cid}/survey"
    assert c.post(u + "/responses", json={"answers": {}, "ratings": {}}).status_code == 400
    assert c.post(u + "/responses", json={"answers": {"1": "Paper  one"}, "ratings": {"1": 3}}).status_code == 200
    r = c.post(u + "/responses", json={"answers": {"1": "paper one "}, "ratings": {"1": 3}}); assert r.status_code == 409 and r.json()["error"] == "this questionnaire has already been added"
    assert c.post(u + "/responses", json={"answers": {}, "ratings": {"2": 5}}).status_code == 200, "ratings alone are a return"
    assert c.post(u + "/responses", json={"answers": {"3": "x\x0by\x00"}, "ratings": {"1": True, "2": 3.0}}).status_code == 200
    s = repo.load_survey(cid)
    assert {"answers": {**{str(k): "" for k in range(1, 13)}, "3": "xy"}, "ratings": {}} in s["responses"], "control characters dropped, bool and float ratings ignored"
    assert all(set(r) == {"answers", "ratings"} for r in s["responses"]) and len(s["hashes"]) == 3
    assert c.post(u + "/invite", json={"emails": "a@x.org"}).status_code == 400 and c.post(u + "/invite", json={"emails": [1]}).status_code == 400
    for bad in ["<>", 'a"b@x.org', "a@x.org.", "x" * 250 + "@x.org", "a<b@x.org"]:
        assert c.post(u + "/invite", json={"emails": [bad]}).status_code == 400, bad
    assert c.post(u + "/invite", json={"emails": [f"p{k}@x.org" for k in range(51)]}).status_code == 400
    st = c.post(u + "/invite", json={"emails": ["Ann Lee <ann@x.org>", "bob@x.org"]}).json()
    assert [i["email"] for i in st["invites"]] == ["ann@x.org", "bob@x.org"] and st["local"] is False
    monkeypatch.setattr(repo, "MAX_INVITES", 3); assert c.post(u + "/invite", json={"emails": ["c@x.org", "d@x.org"]}).status_code == 400
    assert len(c.get(u).json()["invites"]) == 2, "an over-limit batch adds none"; monkeypatch.undo()
    monkeypatch.setenv("BOARD_PUBLIC_URL", "http://127.0.0.1:5173/")
    st = c.get(u).json(); assert st["invites"][0]["link"].startswith("http://127.0.0.1:5173/?take=") and st["local"] is True
    monkeypatch.setenv("BOARD_PUBLIC_URL", "https://board.example.org"); st = c.get(u).json()
    assert st["invites"][0]["link"].startswith("https://board.example.org/?take=") and st["local"] is False
    tok = st["invites"][0]["token"]  # an online response identical to a stored one is refused and leaves the link usable
    r = c.post(f"/api/survey/{tok}", json={"answers": {"1": "Paper one"}, "ratings": {"1": 3}}); assert r.status_code == 409 and "identical" in r.json()["error"]
    assert c.post(f"/api/survey/{tok}", json={"answers": {"1": "Online one"}}).status_code == 200
    assert c.delete(u + f"/invite/{tok}").status_code == 404, "answered invitations are kept"
    st = c.get(u).json(); assert (st["count"], st["min"], st["can_generate"], st["reason"]) == (4, 3, True, None)
    repo.set_used(cid, 4); assert c.get(u).json()["can_generate"] is True  # differencing: same responses, or MIN_RESPONSES more
    assert c.post(u + "/responses", json={"answers": {"1": "Fifth"}}).status_code == 200
    st = c.get(u).json(); assert st["can_generate"] is False and st["reason"].startswith("Wait for 2 more responses")
    monkeypatch.setattr(runs, "research_module", lambda: types.SimpleNamespace(research_enabled=lambda: (True, "mock")))
    r = c.post(f"/api/companies/{cid}/inside-out", json={"documents": []}); assert r.status_code == 409 and r.json()["error"] == st["reason"]
    from app.api import survey as sv  # each question shuffled and numbered on its own
    a, _ = sv.combine([{"answers": {"1": "a", "2": ""}, "ratings": {}}, {"answers": {"1": "", "2": "b"}, "ratings": {}}])
    assert a["1"] == "Response 1: a" and a["2"] == "Response 1: b"
    repo.delete_company(cid)


def test_upload_limits(client, monkeypatch):
    from docx import Document
    from pypdf import PdfWriter
    cid = repo.create(renamed(load("outside_in_run.json"), "Uploadco")); u = f"/api/companies/{cid}/inside-out"; c = client
    monkeypatch.setattr(runs, "research_module", lambda: types.SimpleNamespace(research_enabled=lambda: (True, "mock")))
    for _ in range(3): repo.add_response(cid, {"1": f"r{_}"}, {})
    b64 = lambda b: base64.b64encode(b).decode()
    w = PdfWriter()
    for _ in range(101): w.add_blank_page(72, 72)
    buf = io.BytesIO(); w.write(buf)
    r = c.post(u, json={"documents": [{"slot": 1, "name": "pack.pdf", "data_b64": b64(buf.getvalue())}]})
    assert r.status_code == 400 and any(p.startswith("pack.pdf: a scanned PDF (101 pages)") for p in r.json()["problems"])
    buf = io.BytesIO(); Document().save(buf)
    r = c.post(u, json={"documents": [{"slot": 1, "name": "empty.docx", "data_b64": b64(buf.getvalue())}]})
    assert r.status_code == 400 and "no readable text in empty.docx; export it as PDF or text" in r.json()["problems"]
    monkeypatch.setattr(extract, "MAX_FILE", 10)
    r = c.post(u, json={"documents": [{"slot": 1, "name": "big.txt", "data_b64": b64(b"x" * 11)}]})
    assert r.status_code == 400 and "big.txt: 0 MB; the limit is 0 MB per file" in r.json()["problems"]
    monkeypatch.setattr(extract, "MAX_FILE", 25 * 2**20); monkeypatch.setattr(extract, "MAX_UPLOAD", 30)
    r = c.post(u, json={"documents": [{"slot": 1, "name": "a.txt", "data_b64": b64(b"x" * 20)}, {"slot": 2, "name": "b.txt", "data_b64": b64(b"y" * 20)}]})
    assert r.status_code == 400 and r.json()["error"].startswith("b.txt: the documents together exceed")
    repo.delete_company(cid)


def test_deleted_company_has_no_orphans(client):
    from sqlalchemy import func, select
    from app import models
    from app.db import session_scope
    cid = repo.create(renamed(load("outside_in_run.json"), "Orphanco"), load("inside_out_run.json") and None)
    repo.add_invites(cid, ["z@x.org"]); repo.add_response(cid, {"1": "q"}, {}); repo.delete_company(cid)
    with session_scope() as s:
        for t in (models.StageRun, models.SurveyInvite, models.SurveyResponse, models.SurveyHash, models.PriorRun, models.Deliverable):
            assert s.scalar(select(func.count()).select_from(t).where(t.company_id == cid)) == 0, t.__tablename__


def test_the_dimension_rating_takes_the_whole_five_point_scale(client):
    """Day 2 (1) to Day 1 (5), with the two intermediate points; anything off the scale is dropped."""
    from app.api import survey as sv
    _, r = sv.clean_response({"answers": {}, "ratings": {"1": 1, "2": 2, "3": 3, "4": 4, "5": 5}}, paper=True)
    assert r == {"1": 1, "2": 2, "3": 3, "4": 4, "5": 5}
    _, r = sv.clean_response({"answers": {}, "ratings": {"1": 0, "2": 6, "3": True, "4": 2.0, "5": 4}}, paper=True)
    assert r == {"5": 4}, "out of range, bool and float are ignored"


def test_action_edit_add_delete(client):
    oi = renamed(load("outside_in_run.json"))
    r = client.post("/api/companies/import", json={"outside_in": oi}); assert r.status_code == 200, r.json()
    cid = r.json()["id"]; wait_job(client, r.json()["job_id"])
    u = f"/api/companies/{cid}/actions"
    n0 = len(client.get(f"/api/companies/{cid}/view").json()["actions"])
    assert client.put(u + "/1", json={"heading": "  New heading "}).status_code == 200
    assert client.get(f"/api/companies/{cid}/view").json()["actions"][0]["heading"] == "New heading"
    assert repo.read_run(cid, "outside_in")["actions"][0]["edited"] is True and "edited" not in repo.read_run(cid, "outside_in")["actions"][1]
    assert client.put(u + "/1", json={"heading": " "}).status_code == 400 and client.put(u + "/99", json={"heading": "x"}).status_code == 404
    assert client.delete(u + "/1").json()["count"] == n0 - 1
    r = client.post(u, json={"heading": "Added", "description": "d", "measures": ["m"], "target": "2027-Q2"}); assert r.status_code == 200
    assert client.post(u, json={"description": "no heading"}).status_code == 400
    assert repo.read_run(cid, "outside_in")["actions"][-1]["edited"] is True
    while len(repo.read_run(cid, "outside_in")["actions"]) < 5: assert client.post(u, json={"heading": "x"}).status_code == 200
    assert client.post(u, json={"heading": "sixth"}).status_code == 409
    assert client.put("/api/companies/nope/actions/1", json={"heading": "x"}).status_code == 404
