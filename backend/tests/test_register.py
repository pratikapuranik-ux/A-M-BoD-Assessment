"""The document register logic: what a file really is, which copies are set aside, how a register overrides file names."""
import io

from openpyxl import Workbook

from app.services import register as R

CO = {"name": "CBRE Group, Inc.", "ticker": "CBRE"}
PEERS = [{"name": "Jones Lang LaSalle", "ticker": "JLL"}]
SEC = "UNITED STATES SECURITIES AND EXCHANGE COMMISSION Washington, D.C. 20549\n"


def doc(name, text="", subject=0, sha="", pages=10):
    return {"name": name, "text": text, "subject": subject, "sha": sha, "pages": pages}


def test_cover_page_beats_the_file_name():
    k = R.identify("10-Q 0001138118-26-000005.pdf", SEC + "FORM 10-K\nANNUAL REPORT PURSUANT TO SECTION 13\nFor the fiscal year ended December 31, 2025", ".pdf")
    assert (k["category"], k["kind"]) == ("Annual filing", "10-K") and "FY 2025" in k["period"] and "Misnamed" in k["flag"]
    assert R.cite_as("CBRE", k) == "CBRE FY2025 10-K"


def test_code_named_proxy_and_a_slide_deck_that_quotes_form_10k():
    p = R.identify("24241711-c95e-495a-9ec7-71c5aa16413a.pdf", SEC + "SCHEDULE 14A Proxy Statement\n" + "x " * 50 + "Annual Meeting of Shareholders will be held on May 14, 2026", ".pdf")
    assert p["category"] == "Proxy / circular" and p["period"] == "2026 annual meeting" and "Unnamed (code file name)" in p["flag"]
    s = R.identify("Q1-2026-Earnings-Slides.pdf", "Safe harbor. See our Form 10-K for the year ended December 31, 2025", ".pdf")
    assert (s["category"], s["period"]) == ("Presentation", "Q1 2026") and R.cite_as("JLL", s) == "JLL Q1 2026 slides"


def _register():
    wb = Workbook(); ws = wb.active; ws.title = "Document register"
    ws.append(["Document register"]); ws.append(["note"])
    ws.append(list(R.HEAD_TITLES))
    ws.append(["CBRE", "CBRE.zip", "a.pdf", "Annual filing", "Form 10-K (annual report)", "FY 2025", "", "CBRE FY2025 10-K", 3, "Yes", "Use", "Misnamed", "is the 10-K"])
    ws.append(["JLL", "JLL.zip", "j.xlsx", "Excel supplement", "Financial supplement (Excel)", "Q1 2026", "", "JLL Q1 2026 supplement", "", "Yes (Excel)", "Use", "", ""])
    b = io.BytesIO(); wb.save(b); return b.getvalue()


def test_register_overrides_and_sets_aside_the_misfiled_copy():
    rows = R.from_xlsx(_register()); assert len(rows) == 2
    kept, ignored, notes = R.apply([doc("a.pdf", "FORM 10-Q", 0), doc("j.xlsx", "x", 0)], CO, PEERS, rows)
    assert [d["ident"]["cite_as"] for d in kept] == ["CBRE FY2025 10-K"] and kept[0]["ident"]["source"] == "register"
    assert ignored[0]["name"] == "j.xlsx" and "misfiled" in ignored[0]["ident"]["use"] and any("set aside" in n for n in notes)


def test_duplicates_keep_the_longer_copy_and_a_plain_workbook_is_not_a_register():
    kept, ignored, _ = R.apply([doc("p1.pdf", SEC + "SCHEDULE 14A Proxy Statement annual meeting May 21, 2026", pages=117, sha="a"),
                                doc("p2.pdf", SEC + "SCHEDULE 14A Proxy Statement annual meeting May 21, 2026", pages=121, sha="b")], CO, PEERS)
    assert [d["name"] for d in kept] == ["p2.pdf"] and ignored[0]["ident"]["use"] == "Ignore (duplicate)"
    wb = Workbook(); wb.active.append(["Revenue", 1]); b = io.BytesIO(); wb.save(b)
    assert R.from_xlsx(b.getvalue()) is None


def test_gaps_name_what_the_upload_lacks():
    kept, _, _ = R.apply([doc("t.pdf", "CORRECTED TRANSCRIPT Q1 2026 Earnings Call operator")], CO, PEERS)
    g = R.gaps(kept, ["CBRE Group, Inc.", "Jones Lang LaSalle"])
    assert any("annual filing" in x["gap"].lower() for x in g) and any("transcript" in x["gap"] for x in g) and not any(x["subject"] == "Jones Lang LaSalle" for x in g)


import pytest


@pytest.fixture(autouse=True)
def _own_store(tmp_path, monkeypatch):
    from app.services import doclearn
    monkeypatch.setattr(doclearn, "path", lambda: tmp_path / "learned" / "documents.json")


def test_a_register_teaches_and_the_lesson_places_an_unlabelled_file_of_another_company():
    odd = "Zorblax stakeholder bulletin covenant waiver lender consent amendment facility borrower schedule annex "
    taught = doc("0001-weird-name.pdf", odd * 6 + "tranche alpha", 0)
    rows = R.from_xlsx(_register())
    rows[0]["file name as it is today"] = "0001-weird-name.pdf"; rows[0]["category"] = "Press release"; rows[0]["what it really is"] = "Lender consent notice"; rows[0]["cite as"] = "CBRE lender notice"
    from app.services import doclearn
    kept, _, notes = R.apply([taught], CO, PEERS, rows)
    assert any("Learned from the register" in n for n in notes) and doclearn.load()
    # a later upload, no register, another company, a different name, a cover the rules cannot place, but it reads like what was taught
    later = doc("9999-other-name.pdf", odd * 6 + "tranche beta", 1)
    kept, _, _ = R.apply([later], CO, PEERS)
    assert kept[0]["ident"]["category"] == "Press release" and "learned" in kept[0]["ident"]["source"]


def test_a_model_is_asked_only_when_nothing_learned_fits_and_must_answer_with_a_known_category():
    d = doc("mystery.pdf", "completely unfamiliar text about wombats and ledgers " * 20, 0)
    kept, _, _ = R.apply([d], CO, PEERS, ask=lambda p, l: '{"category": "Transcript", "what": "Earnings call transcript", "kind": "call"}')
    assert kept[0]["ident"]["category"] == "Transcript" and "model" in kept[0]["ident"]["source"]
    d2 = doc("mystery2.pdf", "completely unfamiliar text about wombats and ledgers " * 20, 0)
    kept, _, _ = R.apply([d2], CO, PEERS, ask=lambda p, l: '{"category": "Banana"}')
    assert kept[0]["ident"]["category"] == "Other"
