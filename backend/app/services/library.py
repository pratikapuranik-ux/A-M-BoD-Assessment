"""A per-assessment store of what has been read from each supplied file, so a retry or re-run never reads it again.

Files are keyed by the fingerprint of their bytes and stored under the assessment (company ticker and period): nothing is shared
between assessments, so one client's files are never visible to another's. Only the extracted text is kept, not the file.
"""
from __future__ import annotations

import hashlib
import json
import re
import time
from pathlib import Path

from app.log import get_logger
from app.services import storage

log = get_logger(__name__)
KEEP_DAYS = 30
FIELDS = ("text", "pages", "size", "transcribed", "facts")


def root() -> Path:
    d = storage.root() / "_library"; d.mkdir(parents=True, exist_ok=True); return d


def sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def scope(ticker: str, period: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", f"{ticker}-{period}".lower()).strip("-") or "assessment"


def _path(sc: str, key: str) -> Path:
    return root() / sc / f"{key}.json"


def get(sc: str, key: str) -> dict | None:
    p = _path(sc, key)
    try:
        d = json.loads(p.read_text(encoding="utf-8")); p.touch(); return d
    except (OSError, ValueError):
        return None


def put(sc: str, key: str, doc: dict) -> None:
    if not (doc.get("text") or "").strip(): return
    p = _path(sc, key)
    try:
        p.parent.mkdir(parents=True, exist_ok=True)
        tmp = p.with_suffix(".tmp"); tmp.write_text(json.dumps({k: doc.get(k) for k in FIELDS}), encoding="utf-8"); tmp.replace(p)
    except OSError as e:
        log.warning("library_write_failed", error=str(e))


def update(sc: str, key: str, **fields) -> None:
    """Add fields (e.g. a fact sheet) to a stored file."""
    cur = get(sc, key)
    if cur is not None: put(sc, key, {**cur, **fields})


def sweep(days: int = KEEP_DAYS) -> None:
    """Remove stored files not used for `days` days (and empty assessment folders)."""
    cutoff = time.time() - days * 86400
    try:
        for d in root().iterdir():
            if not d.is_dir(): continue
            for f in d.iterdir():
                if f.is_file() and f.stat().st_mtime < cutoff: f.unlink(missing_ok=True)
            if not any(d.iterdir()): d.rmdir()
    except OSError as e:
        log.warning("library_sweep_failed", error=str(e))
