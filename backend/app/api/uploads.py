"""Document uploads -> extracted text/PDF payloads for the research agents.

A file reaches the server in one of two ways:
  * staged: the browser POSTs each file's raw bytes to /api/uploads (streamed to disk, one request per file, so no request
    ever has to hold every file at once), then names it by `upload_id` in the research / inside-out request;
  * inline: `data_b64` in the JSON request (kept for small API clients and tests).
A .zip is unpacked here: each supported file inside becomes a document (in the zip's slot, for inside-out). Files inside a
zip that cannot be used (images, slides, password-protected, unreadable) are skipped and reported in `notes`, not errors.
Staged files are deleted as soon as they have been read; anything left behind is swept after a day.
"""
from __future__ import annotations

import base64
import io
import os
import re
import time
import uuid
import zipfile
from pathlib import Path
from typing import Callable

from fastapi import APIRouter, Request

from app.api.errors import ApiError
from app.log import get_logger
from app.services import documents, library, storage, subjects

log = get_logger(__name__)
router = APIRouter()
UPLOAD_ID = re.compile(r"[0-9a-f]{32}")
STALE_SECONDS = 24 * 3600


def staging_dir() -> Path:
    d = storage.root() / "_uploads"
    d.mkdir(parents=True, exist_ok=True)
    return d


def sweep_stale() -> None:
    """Remove staged files nobody claimed (an abandoned or failed request)."""
    d = storage.root() / "_uploads"
    if not d.is_dir(): return
    cutoff = time.time() - STALE_SECONDS
    for p in d.iterdir():
        try:
            if p.is_file() and p.stat().st_mtime < cutoff: p.unlink()
        except OSError: log.info("stale_upload_not_removed", file=p.name)


def is_zip(name: str | None) -> bool:
    return str(name or "").lower().endswith(".zip")


@router.post("/api/uploads")
async def stage_upload(request: Request, name: str = "document"):
    """Receive one file as the raw request body and keep it until the request that names it has read it."""
    uid = uuid.uuid4().hex; path = staging_dir() / uid; size = 0
    limit = documents.MAX_ZIP if is_zip(name) else documents.MAX_FILE
    try:
        with open(path, "wb") as f:
            async for chunk in request.stream():
                size += len(chunk)
                if size > limit:
                    raise ApiError(413, f"{name}: over the {limit // 2**20} MB limit per {'zip' if is_zip(name) else 'file'}")
                f.write(chunk)
        if size == 0: raise ApiError(400, f"{name}: empty file")
    except BaseException:
        path.unlink(missing_ok=True)
        raise
    return {"upload_id": uid, "name": name, "size": size}


@router.post("/api/documents/assign")
async def assign_documents(request: Request):
    """Which subject each file path belongs to, from its folder names: {'company': {name, ticker}, 'peers': [...], 'names': [paths]}
    -> {'subjects': [0 = company, 1.. = peer, per path]}. The page shows these for the director to confirm or change."""
    try: b = await request.json()
    except ValueError: raise ApiError(400, "send JSON")
    company = b.get("company") if isinstance(b.get("company"), dict) else {}
    peers = [p for p in (b.get("peers") or []) if isinstance(p, dict)]
    names = [str(n) for n in (b.get("names") or [])][:5000]
    return {"subjects": subjects.assign_many(names, company, peers)}


def _staged_path(d: dict) -> Path:
    uid = str(d.get("upload_id") or "")
    p = staging_dir() / uid
    if not UPLOAD_ID.fullmatch(uid) or not p.is_file():
        raise documents.ExtractError(f"{d.get('name') or 'document'}: the uploaded file is no longer on the server; add it again")
    return p


class Extracted(list):
    """The extracted documents, plus `notes`: things skipped inside zips, for the user to see."""
    def __init__(self): super().__init__(); self.notes: list[str] = []


_JUNK = {".ds_store", "thumbs.db", "desktop.ini"}
Progress = Callable[[str], None]


def precheck_documents(docs: list, *, max_slot: int | None = None) -> list[str]:
    """Problems that can be found without reading any file: shape, type, slot, a staged file that has gone, total size.
    Quick enough to run while the request waits; the reading itself happens in the job (extract_documents)."""
    probs: list[str] = []; total = 0
    for d in docs:
        if not isinstance(d, dict): probs.append("each document must be an object"); continue
        name = d.get("name") or "document"
        try:
            if d.get("upload_id"): total += _staged_path(d).stat().st_size
            else: total += len(str(d.get("data_b64") or "")) * 3 // 4
            if not is_zip(name) and documents.ext_of(name, d.get("mime")) not in documents.SUPPORTED:
                raise documents.ExtractError(f"{name}: unsupported file type (supported: {', '.join(documents.SUPPORTED)}, or a .zip of them)")
            if max_slot is not None and not 0 <= int(d.get("slot") or 0) <= max_slot:
                raise documents.ExtractError(f"{name}: slot must be 0-{max_slot}")
        except (documents.ExtractError, ValueError) as e:
            probs.append(str(e))
        if total > documents.MAX_UPLOAD:
            raise ApiError(400, f"{name}: the documents together exceed {documents.MAX_UPLOAD // 2**20} MB; send fewer or smaller files")
    return probs


class Opts:
    """How a batch is read: `scope` keeps what was read for reuse (None = do not), `who` names the subject a file belongs to
    (None = every file is subject 0), `as_text` turns every PDF into text (scans are transcribed) for searching."""
    def __init__(self, scope=None, who=None, as_text=False): self.scope, self.who, self.as_text = scope, who, as_text


def _read_one(name: str, raw: bytes, slot: int, mime, subject: int | None, o: Opts) -> dict:
    """Extract one file, or take what was read from the same bytes before; tag it with its subject."""
    key = library.sha(raw) if o.scope else None
    hit = library.get(o.scope, key) if key else None
    if hit:
        d = {"name": name, "slot": slot, "text": hit["text"], "pdf_b64": None, "pdf_big": False, "pages": hit.get("pages") or 1,
             "size": hit.get("size") or len(raw), "transcribed": bool(hit.get("transcribed")), "cached": True, "facts": hit.get("facts") or ""}
    else:
        d = documents.extract(name, raw, slot, mime)
        if o.as_text and d.get("pdf_b64"):
            if documents._has_text(d.get("text")): d["pdf_b64"] = None; d.pop("_raw", None)
            elif d.get("_raw") is not None: d.update(pdf_b64=None, needs_ocr=True)
        if key and (d.get("text") or "").strip() and not d.get("needs_ocr"): library.put(o.scope, key, d)
    d["_key"] = key
    d["subject"] = subject if subject is not None else (o.who(name) if o.who else 0)
    return d


def _zip_documents(source, zname: str, slot: int, subject: int | None, out: Extracted, budget: list[int], progress: Progress | None, o: Opts) -> None:
    """Add every usable file in a zip to `out`. A bad zip is an error; an unusable member is skipped and noted."""
    try: zf = zipfile.ZipFile(source)
    except (zipfile.BadZipFile, OSError) as e: raise documents.ExtractError(f"{zname}: not a readable zip file") from e
    skipped: list[str] = []; used = 0
    with zf:
        infos = [i for i in zf.infolist() if not i.is_dir()]
        if len(infos) > documents.MAX_ZIP_MEMBERS:
            raise documents.ExtractError(f"{zname}: {len(infos)} files inside; the limit is {documents.MAX_ZIP_MEMBERS} per zip")
        for k, i in enumerate(infos, 1):
            base = i.filename.rsplit("/", 1)[-1]
            if i.filename.startswith("__MACOSX/") or base.lower() in _JUNK or base.startswith(("~$", "._")): continue  # system and Office lock files
            if os.path.splitext(base)[1].lower() not in documents.SUPPORTED: skipped.append(f"{i.filename} (not a supported type)"); continue
            if i.flag_bits & 0x1: skipped.append(f"{i.filename} (password-protected)"); continue
            if i.file_size > documents.MAX_FILE: skipped.append(f"{i.filename} (over {documents.MAX_FILE // 2**20} MB)"); continue
            budget[0] += i.file_size
            if budget[0] > documents.MAX_UPLOAD:
                raise ApiError(400, f"{zname}: the documents together exceed {documents.MAX_UPLOAD // 2**20} MB; send fewer or smaller files")
            if progress: progress(f"Reading {i.filename} ({k} of {len(infos)} files in {zname})")
            try:
                out.append(_read_one(i.filename, zf.read(i), slot, None, subject, o)); used += 1
            except (documents.ExtractError, RuntimeError, zipfile.BadZipFile) as e:
                skipped.append(f"{i.filename} ({str(e).split(': ', 1)[-1][:80]})")
    if not used and not skipped: raise documents.ExtractError(f"{zname}: the zip holds no files")
    if not used: raise documents.ExtractError(f"{zname}: none of the {len(skipped)} files inside could be used (supported: {', '.join(documents.SUPPORTED)})")
    if skipped:
        shown = "; ".join(skipped[:8]) + (f"; and {len(skipped) - 8} more" if len(skipped) > 8 else "")
        out.notes.append(f"{zname}: read {used} file(s); skipped {len(skipped)}: {shown}")


def extract_documents(docs: list, *, max_slot: int | None = None, progress: Progress | None = None,
                      scope: str | None = None, who: Callable[[str], int] | None = None, as_text: bool = False) -> tuple[Extracted, list[str]]:
    """Reads the documents. Returns (extracted, problems); `extracted.notes` lists what was skipped inside zips. Slow for long
    PDFs, so it runs inside the job, which shows `progress`. Raises ApiError(400) when the documents together exceed the limit.
    max_slot: None for outside-in (slot is always 0); else the highest valid inside-out slot.
    scope / who / as_text: see Opts. Each result carries `subject` (0 = the company, 1.. = a peer)."""
    out = Extracted(); probs: list[str] = []; budget = [0]; o = Opts(scope, who, as_text)
    for n, d in enumerate(docs, 1):
        if not isinstance(d, dict): probs.append("each document must be an object"); continue
        staged: Path | None = None
        try:
            name = d.get("name") or "document"
            if progress: progress(f"Reading {name} (file {n} of {len(docs)})")
            if d.get("upload_id"):
                staged = _staged_path(d); size = staged.stat().st_size
            else:
                size = len(str(d.get("data_b64") or "")) * 3 // 4
            slot = 0
            if max_slot is not None:
                slot = int(d.get("slot") or 0)
                if not 0 <= slot <= max_slot: raise documents.ExtractError(f"{name}: slot must be 0-{max_slot}")
            subject = d["subject"] if isinstance(d.get("subject"), int) and not isinstance(d.get("subject"), bool) else None
            if is_zip(name):
                if staged is not None: _zip_documents(staged, name, slot, subject, out, budget, progress, o)
                else:
                    try: raw = base64.b64decode(d.get("data_b64") or "", validate=False)
                    except Exception as ex: raise documents.ExtractError(f"{name}: data_b64 is not valid base64") from ex
                    _zip_documents(io.BytesIO(raw), name, slot, subject, out, budget, progress, o)
                continue
            budget[0] += size
            if budget[0] > documents.MAX_UPLOAD:
                raise ApiError(400, f"{name}: the documents together exceed {documents.MAX_UPLOAD // 2**20} MB; send fewer or smaller files")
            if staged is not None: raw = staged.read_bytes()
            else:
                try: raw = base64.b64decode(d.get("data_b64") or "", validate=False)
                except Exception as ex: raise documents.ExtractError(f"{name}: data_b64 is not valid base64") from ex
            out.append(_read_one(name, raw, slot, d.get("mime"), subject, o))
        except (documents.ExtractError, ValueError) as e:
            probs.append(str(e))
        finally:
            if staged is not None: staged.unlink(missing_ok=True)
    if not probs and not as_text:
        if progress: progress("Checking which PDFs can be read as pages")
        try: documents.fit_pdfs(out)
        except documents.ExtractError as e: probs.append(str(e))
    if not probs and any(d.get("needs_ocr") for d in out):  # scans that cannot go as pages, and images: read them with Claude
        from app.services import ocr
        p, n = ocr.transcribe_pending(out, progress)
        probs.extend(p); out.notes.extend(n)
        for d in out:  # keep what was transcribed, so a retry does not pay for it again
            if d.get("transcribed") and d.get("_key") and not d.get("cached"): library.put(scope, d["_key"], d)
    for d in out:
        d.pop("_raw", None); d.pop("_image", None)
        if "_key" in d: d["sha"] = d.pop("_key")
    return out, probs
