"""The documents are fitted to what one request can hold (the model call is replaced here)."""
import pytest

from app.services import digest


def doc(name, tokens_k, pdf=False, text=True):
    body = ("Revenue 12 | 14" + chr(10)) * 100
    n = int(tokens_k * 1000 * digest.CHARS_PER_TOKEN / len(body)) or 1
    return {"name": name, "pages": 10, "text": body * n if text else "", "pdf_b64": "x" if pdf else None}


@pytest.fixture
def asked(monkeypatch):
    calls = []
    def ask(text, name, i, n, label):
        calls.append((name, i, n)); return "kept " + text[:100]
    monkeypatch.setattr(digest, "_ask", ask)
    return calls


def test_under_budget_is_untouched(asked):
    docs = [doc("a.txt", 100)]
    assert digest.fit(docs, budget=500_000) == [] and not asked and not docs[0].get("condensed")


def test_pdf_pages_become_text_first(asked):
    docs = [doc("a.pdf", 10, pdf=True)]  # 10 pages x 3000 = 30k as pages, ~10k as text
    docs[0]["pages"] = 400
    notes = digest.fit(docs, budget=100_000)
    assert docs[0]["pdf_b64"] is None and not asked and "read as text" in notes[0]


def test_largest_documents_are_condensed_until_it_fits(asked):
    docs = [doc("big.txt", 900), doc("mid.txt", 200), doc("tiny.txt", 10)]
    notes = digest.fit(docs, progress=lambda m: None, budget=500_000)
    names = {c[0] for c in asked}
    assert "big.txt" in names and "tiny.txt" not in names
    assert docs[0]["condensed"] and not docs[2].get("condensed") and "condensed" in notes[0]
    assert max(c[2] for c in asked) > 1  # a long document goes in sections


def test_cannot_fit_names_the_largest(monkeypatch):
    monkeypatch.setattr(digest, "_ask", lambda text, name, i, n, label: text)  # condensing that saves nothing
    with pytest.raises(digest.DigestError, match="big.txt"):
        digest.fit([doc("big.txt", 900)], budget=100_000)
