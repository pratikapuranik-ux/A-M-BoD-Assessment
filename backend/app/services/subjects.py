"""Which subject (the company or one of its peers) a document belongs to, from its folder names.

A file at 'Energy test/Shell/annual-report.pdf' belongs to the subject whose name or ticker matches a folder on its path, the deepest
folder first. A file in no matching folder belongs to the company. Spelling slips ('ExxxonMobil') are tolerated.
"""
from __future__ import annotations

import re
from difflib import SequenceMatcher

COMPANY = 0  # subject 0 is the company, 1.. are the peers in the order given
_SUFFIX = {"corporation", "corp", "inc", "incorporated", "plc", "ltd", "limited", "group", "company", "co", "holdings", "holding", "sa", "ag", "nv", "se", "llc", "the"}


def display_name(s: str) -> str:
    """A name as typed, capitalised for reports: 'chevron' -> 'Chevron', 'EXXONMOBIL' -> 'Exxonmobil'. A name that already mixes cases
    ('ExxonMobil', 'bp p.l.c.' is not one) is left as given, and an all-capitals name of up to four letters ('BP') is kept as an acronym."""
    s = re.sub(r"\s+", " ", (s or "").strip())
    if not s or any(c.isupper() for c in s) and any(c.islower() for c in s): return s
    if s.isupper() and len(s.replace(" ", "")) <= 4: return s
    return " ".join(w[:1].upper() + w[1:].lower() if not w.isupper() or len(w) > 4 else w for w in s.split(" "))


def norm(s: str) -> str:
    """Lower case, letters and digits only, without company suffixes: 'Exxon Mobil Corporation' -> 'exxonmobil'."""
    parts = [p for p in re.split(r"[^a-z0-9]+", (s or "").lower()) if p and p not in _SUFFIX]
    return "".join(parts)


def _match(folder: str, name: str, ticker: str) -> bool:
    f, n, t = norm(folder), norm(name), norm(ticker)
    if not f: return False
    if t and f == t: return True
    if not n: return False
    if len(f) >= 3 and (f == n or f in n or n in f): return True
    return SequenceMatcher(None, f, n).ratio() >= 0.8


def assign(path: str, company: dict, peers: list[dict]) -> int:
    """0 for the company, 1.. for a peer. `company` and each peer are {'name', 'ticker'}."""
    folders = [p for p in re.split(r"[\\/]+", path or "")[:-1] if p]
    subjects = [company] + list(peers)
    for folder in reversed(folders):
        for i, s in enumerate(subjects):
            if _match(folder, s.get("name", ""), s.get("ticker", "")): return i
    return COMPANY


NOT_USED = -1  # a file in the folder of a company that is not in this assessment


def assign_many(paths: list[str], company: dict, peers: list[dict]) -> list[int]:
    """assign() for a whole upload. Folders named after the company and its peers sit side by side (…/Chevron, …/BP). A file in a
    folder at that level that matches none of them belongs to some other company (a former peer, say), so it is NOT_USED
    rather than quietly counted as the company's own."""
    subs = [company] + list(peers)
    found = []
    for p in paths:
        folders = [f for f in re.split(r"[\/]+", p or "")[:-1] if f]
        hit = next(((i, d) for d in range(len(folders) - 1, -1, -1) for i, s in enumerate(subs) if _match(folders[d], s.get("name", ""), s.get("ticker", ""))), None)
        found.append((len(folders), hit))
    depths = [h[1] for _, h in found if h]
    if not depths: return [COMPANY] * len(paths)
    level = max(set(depths), key=depths.count)
    return [h[0] if h else (NOT_USED if n > level else COMPANY) for n, h in found]
