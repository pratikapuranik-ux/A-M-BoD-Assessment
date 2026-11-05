"""Search the documents supplied on one subject (the company or a peer).

The text of each document is cut into passages that keep their file name and page, and ranked locally with BM25 (no model call, no
cost). The research agent is given a tool that returns the best passages for a query, so what it pays for follows what it reads, not
how much was uploaded.
"""
from __future__ import annotations

import math
import re
from collections import Counter

PASSAGE_WORDS = 450  # target size of one passage
MAX_PASSAGE_WORDS = 700  # a single paragraph or table longer than this is cut
RESULTS = 6
PAGE_CHARS = 12000  # the most one page read returns (about 3,700 tokens)
K1, B = 1.5, 0.75
STOP = set("a an and are as at be by for from has have in is it its of on or that the this to was were will with".split())
PAGE_RE = re.compile(r"^\[(?:page|slide) (\d+)\]", re.I)
WORD_RE = re.compile(r"[a-z0-9][a-z0-9.%&'-]*")


def words(text: str) -> list[str]:
    return [w.strip(".%&'-") for w in WORD_RE.findall(text.lower()) if w not in STOP]


def passages(name: str, text: str) -> list[dict]:
    """Split a document into passages of about PASSAGE_WORDS words, at paragraph breaks, each with the page it starts on."""
    out: list[dict] = []; cur: list[str] = []; n = 0; page = 1; start = 1

    def flush():
        nonlocal cur, n, start
        if cur: out.append({"file": name, "page": start, "text": "\n".join(cur).strip()})
        cur = []; n = 0; start = page

    for line in text.split("\n"):
        m = PAGE_RE.match(line.strip())
        if m:  # a passage never spans pages, so its page is always the one to cite
            flush(); page = int(m.group(1)); start = page
        k = len(line.split())
        if k > MAX_PASSAGE_WORDS:  # an unbroken block: cut it
            toks = line.split()
            for i in range(0, len(toks), MAX_PASSAGE_WORDS):
                if cur: flush()
                cur = [" ".join(toks[i:i + MAX_PASSAGE_WORDS])]; n = MAX_PASSAGE_WORDS; flush()
            continue
        if n + k > PASSAGE_WORDS and cur and not line.strip().startswith("|"): flush()  # keep a table together where it fits
        elif n + k > MAX_PASSAGE_WORDS and cur: flush()
        if not cur: start = page
        cur.append(line); n += k
    flush()
    return [p for p in out if p["text"]]


def page_texts(name: str, text: str) -> dict[tuple[str, int], str]:
    """Text of each page of a document, by (file, page), from its [page N] / [slide N] markers (page 1 is everything if there are none)."""
    out: dict[tuple[str, int], list[str]] = {}; page = 1
    for line in text.split("\n"):
        m = PAGE_RE.match(line.strip())
        if m: page = int(m.group(1))
        out.setdefault((name, page), []).append(line)
    return {k: "\n".join(v).strip() for k, v in out.items()}


class Index:
    """BM25 over the passages of the documents given."""

    def __init__(self, docs: list[dict]):
        self.docs = [d for d in docs if (d.get("text") or "").strip()]
        self.items: list[dict] = []
        for d in self.docs: self.items += passages(d.get("name") or "document", d["text"])
        self.pages: dict[tuple[str, int], str] = {}
        for d in self.docs: self.pages.update(page_texts(d.get("name") or "document", d["text"]))
        self.tf = [Counter(words(p["file"] + " " + p["text"])) for p in self.items]
        self.len = [sum(t.values()) for t in self.tf]
        self.avg = (sum(self.len) / len(self.len)) if self.len else 1.0
        df: Counter = Counter()
        for t in self.tf: df.update(t.keys())
        n = len(self.items)
        self.idf = {w: math.log(1 + (n - c + 0.5) / (c + 0.5)) for w, c in df.items()}

    def search(self, query: str, file: str = "", k: int = RESULTS) -> list[dict]:
        q = words(query)
        if not q or not self.items: return []
        scored = []
        for i, t in enumerate(self.tf):
            if file and file.lower() not in self.items[i]["file"].lower(): continue
            s = 0.0
            for w in q:
                f = t.get(w, 0)
                if f: s += self.idf.get(w, 0) * f * (K1 + 1) / (f + K1 * (1 - B + B * self.len[i] / self.avg))
            if s > 0: scored.append((s, i))
        scored.sort(reverse=True)
        return [self.items[i] for _, i in scored[:k]]

    def answer(self, query: str, file: str = "") -> str:
        """The tool result for one query: the best passages with their file and page."""
        hits = self.search(query, file)
        if not hits:
            return "No passage in the supplied documents matches this query. Try different words, or drop the file filter."
        return "\n\n".join(f'<passage file="{h["file"]}" page="{h["page"]}">\n{h["text"]}\n</passage>' for h in hits)

    def page(self, file: str, n: int) -> str:
        """One page exactly as extracted (the source for checking a figure)."""
        hit = [(k, t) for k, t in self.pages.items() if k[1] == n and file.lower() in k[0].lower()]
        if not hit: return f"No page {n} found in a file matching '{file}'. Check the file name and the page from a search result."
        if len(hit) > 1: return "More than one file matches; give more of the file name: " + "; ".join(k[0] for k, _ in hit[:8])
        (name, _), text = hit[0]
        cut = "\n[the page is longer; this is its first 12000 characters]" if len(text) > PAGE_CHARS else ""
        return f'<page file="{name}" page="{n}">\n{text[:PAGE_CHARS]}{cut}\n</page>'

    def summary(self) -> str:
        """One line per document for the prompt (names and sizes only)."""
        shown = [f"- {d.get('name')} ({d.get('pages') or '?'} pages)" for d in self.docs[:60]]
        more = f"\n- and {len(self.docs) - 60} more" if len(self.docs) > 60 else ""
        return "\n".join(shown) + more
