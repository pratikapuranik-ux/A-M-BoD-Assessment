"""Teach the app from a document register and the files it describes.

    python scripts/learn_register.py "C:/path/Document_Register.xlsx" "C:/path/CBRE.zip" "C:/path/JLL.zip" ...   (zips or folders)

For every file the register describes (matched by file name, ignoring rows marked Ignore), the first pages are read, fingerprinted and kept
with the register's answer in storage/learned/documents.json. The app also does this by itself whenever a register is among the files of a
run; this script is for teaching it ahead of time. Only word lists from cover pages are stored, never document text. Reading is limited to
the first three pages of each PDF, so a folder of long filings takes a minute, not an hour.
"""
from __future__ import annotations

import io
import os
import sys
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.services import doclearn, register  # noqa: E402


def first_pages(raw: bytes, ext: str) -> str:
    if ext == ".pdf":
        try:
            from pypdf import PdfReader
            rd = PdfReader(io.BytesIO(raw))
            return "\n".join(f"[page {k + 1}]\n" + (rd.pages[k].extract_text() or "") for k in range(min(3, len(rd.pages))))
        except Exception:  # noqa: BLE001 - an unreadable file teaches nothing
            return ""
    return "[sheet]" if ext == ".xlsx" else ""


def files(sources: list[str]):
    for s in sources:
        p = Path(s)
        if p.is_dir():
            for f in p.rglob("*"):
                if f.is_file(): yield f.name, f.read_bytes
        elif p.suffix.lower() == ".zip":
            zf = zipfile.ZipFile(p)
            for i in zf.infolist():
                if not i.is_dir(): yield os.path.basename(i.filename), (lambda zf=zf, i=i: zf.read(i))


def main(argv: list[str]) -> int:
    if len(argv) < 2:
        print(__doc__); return 2
    rows = register.from_xlsx(Path(argv[0]).read_bytes())
    if not rows:
        print("That workbook is not a document register (no 'File name as it is today' and 'Cite as' columns)."); return 1
    by = {}
    for r in rows: by.setdefault(os.path.basename(r["file name as it is today"]).lower(), r)
    seen = new = 0
    for name, read in files(argv[1:]):
        r = by.get(name.lower())
        if not r or not (r.get("use?") or "Use").lower().startswith("use"): continue
        seen += 1; ext = os.path.splitext(name)[1].lower()
        text = first_pages(read(), ext)
        label = {"category": r.get("category", ""), "what": r.get("what it really is", ""), "kind": register.kind_of_row(r)}
        if doclearn.learn(doclearn.fingerprint(name, text, ext), label): new += 1
    print(f"{len(rows)} register rows; matched {seen} files; learned {new} new example(s); {len(doclearn.load())} in the store ({doclearn.path()})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
