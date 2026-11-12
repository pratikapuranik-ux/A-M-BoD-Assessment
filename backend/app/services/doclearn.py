"""What the app has learned about documents, from every register it has been given.

A document register (an A&M Excel file that says what each supplied file really is) is ground truth. Each time one is uploaded, every file
it describes is fingerprinted (the shape of its file name and the words on its cover page, not its content) and kept with the register's
answer (category, what it is, kind). Later, a file nobody registered and the cover-page rules cannot place is compared with what was
learned: the closest examples decide, and if they are not close enough a model is shown the best few examples and the cover page and asked.

Nothing here names a company or a document type: the types come from the registers. The store is a local JSON file (storage/learned/documents.json);
it holds word lists from public cover pages, never document text.
"""
from __future__ import annotations

import json
import math
import os
import re
import threading
from collections import Counter
from pathlib import Path

from app.services import storage

MAX_EXAMPLES = 6000
COVER_CHARS = 2500
TOP_WORDS = 70
MIN_CONFIDENCE = 0.45  # the nearest examples must be at least this close to be believed
STOP = set("the and for are was were with that this from have has had not but its our their you your all any may will shall per under into over than also such which these those "
           "inc corp ltd llc plc company group page pages table contents form report annual quarterly january february march april may june july august september october november december".split())
_lock = threading.Lock()


def path() -> Path:
    return storage.root() / "learned" / "documents.json"


def _words(text: str) -> list[str]:
    return [w for w in re.findall(r"[a-z][a-z0-9&.-]{2,}", re.sub(r"\[(?:page|slide|sheet)[^\]]*\]", " ", (text or "").lower())) if w.strip(".-") not in STOP]


def shape(name: str) -> str:
    """The pattern of a file name with identifiers masked: '10-Q 0001138118-26-000005.pdf' -> '10 q 0'; 'Q3-2026-Earnings-Slide-Deck.pdf' -> 'q 0 earnings slide deck'."""
    stem = os.path.splitext(os.path.basename(name or ""))[0].lower()
    stem = re.sub(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}", " code ", stem)
    stem = re.sub(r"\d+", "0", stem)
    return " ".join(dict.fromkeys(t for t in re.split(r"[^a-z]+", stem.replace("0", " 0 ")) if t))


def fingerprint(name: str, text: str, ext: str = "") -> dict:
    """The learnable face of a file: its name shape, extension and the words most used on its cover pages."""
    c = Counter(_words((text or "")[:COVER_CHARS]))
    return {"shape": shape(name), "ext": (ext or os.path.splitext(name or "")[1]).lower(), "tokens": [w for w, _ in c.most_common(TOP_WORDS)]}


def load() -> list[dict]:
    try: return json.loads(path().read_text(encoding="utf-8"))
    except (OSError, ValueError): return []


def learn(fp: dict, label: dict, source: str = "register") -> bool:
    """Keeps one example (a fingerprint and the answer for it). The same name shape, cover words and answer are kept once. Returns whether it was new."""
    if not fp.get("tokens") and not fp.get("shape"): return False
    ex = {**fp, "category": label.get("category", ""), "what": label.get("what", ""), "kind": label.get("kind", ""), "source": source}
    if not ex["category"]: return False
    with _lock:
        data = load(); key = (ex["shape"], ex["category"], ex["kind"], tuple(ex["tokens"][:12]))
        if any((d.get("shape"), d.get("category"), d.get("kind"), tuple((d.get("tokens") or [])[:12])) == key for d in data): return False
        data.append(ex); data = data[-MAX_EXAMPLES:]
        p = path(); p.parent.mkdir(parents=True, exist_ok=True)
        blob = json.dumps(data, ensure_ascii=False)
        try:
            tmp = p.with_suffix(".tmp"); tmp.write_text(blob, encoding="utf-8"); tmp.replace(p)
        except OSError:  # a synced folder (OneDrive) can hold the file open: write in place instead
            p.write_text(blob, encoding="utf-8")
    return True


def _score(fp: dict, ex: dict, idf: dict[str, float]) -> float:
    a, b = set(fp.get("tokens") or []), set(ex.get("tokens") or [])
    cover = 0.0
    if a and b:
        inter = sum(idf.get(w, 1.0) for w in a & b); union = sum(idf.get(w, 1.0) for w in a | b)
        cover = inter / union if union else 0.0
    sa, sb = set((fp.get("shape") or "").split()) - {"0"}, set((ex.get("shape") or "").split()) - {"0"}
    name = (len(sa & sb) / len(sa | sb)) if sa and sb else 0.0
    s = 0.7 * cover + 0.3 * name
    if fp.get("ext") and ex.get("ext") and fp["ext"] != ex["ext"] and {fp["ext"], ex["ext"]} & {".xlsx", ".pptx", ".docx"}: s *= 0.4  # a workbook is never a filing
    return s


def nearest(fp: dict, k: int = 6) -> list[tuple[float, dict]]:
    data = load()
    if not data: return []
    df: Counter = Counter()
    for d in data: df.update(set(d.get("tokens") or []))
    n = len(data); idf = {w: math.log(1 + n / c) for w, c in df.items()}
    return sorted(((_score(fp, d, idf), d) for d in data), key=lambda t: -t[0])[:k]


def classify(fp: dict) -> tuple[dict | None, float]:
    """The answer the closest learned examples agree on, and how sure that is (0-1). None when nothing learned is close enough."""
    near = [(s, d) for s, d in nearest(fp) if s > 0]
    if not near: return None, 0.0
    votes: Counter = Counter()
    for s, d in near: votes[(d["category"], d.get("kind", ""))] += s
    (cat, kind), w = votes.most_common(1)[0]
    best = next(d for s, d in near if (d["category"], d.get("kind", "")) == (cat, kind))
    conf = max(s for s, d in near if (d["category"], d.get("kind", "")) == (cat, kind)) * (w / sum(votes.values()))
    return ({"category": cat, "kind": kind, "what": best.get("what", "")}, conf) if conf >= MIN_CONFIDENCE else (None, conf)


def ask_model(name: str, text: str, fp: dict, categories: tuple[str, ...], ask) -> dict | None:
    """When nothing learned fits: a model reads the cover page with the best few learned examples, and answers as JSON. None when it cannot."""
    shots = "\n".join(f'- file name pattern "{d.get("shape")}", cover words {", ".join((d.get("tokens") or [])[:12])}  =>  category "{d["category"]}", what "{d.get("what")}", kind "{d.get("kind")}"'
                      for _, d in nearest(fp, 8))
    prompt = (f"Identify what this supplied document really is, from its first pages; the file name can be wrong or meaningless. Categories: {', '.join(categories)}.\n"
              f"Examples of documents already identified by the team:\n{shots or '(none yet)'}\n\nFile name: {name}\nFirst pages:\n{(text or '')[:COVER_CHARS]}\n\n"
              'Answer with one JSON object only: {"category": one of the categories, "what": a short description such as "Form 10-Q", "kind": a short lowercase label such as "10-Q"}.')
    try: raw = ask(prompt, f"identify {name[:40]}")
    except Exception:  # noqa: BLE001 - identification is best effort
        return None
    m = re.search(r"\{.*\}", raw or "", re.S)
    try: out = json.loads(m.group(0)) if m else None
    except ValueError: return None
    if not isinstance(out, dict) or out.get("category") not in categories: return None
    return {"category": out["category"], "what": str(out.get("what") or out["category"])[:80], "kind": str(out.get("kind") or "")[:30]}
