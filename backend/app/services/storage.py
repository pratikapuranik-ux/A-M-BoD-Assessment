"""Binary files on disk under NEXUS_STORAGE_DIR/<company id>/{out,uploads}/. Retries while OneDrive / a scanner holds a file."""
from __future__ import annotations

import os
import re
import shutil
import time
import uuid
from pathlib import Path

from app.config import get_settings
from app.log import get_logger

log = get_logger(__name__)
VALID_ID = re.compile(r"[a-z0-9][a-z0-9-]{0,63}")


class StoreError(RuntimeError):
    """Something on disk could not be changed; the message is fit to show the user."""


def valid_id(cid: str) -> bool:
    return bool(VALID_ID.fullmatch(cid or ""))


def root() -> Path:
    return get_settings().storage_dir


def company_dir(cid: str) -> Path:
    if not valid_id(cid):
        raise KeyError(cid)
    return root() / cid


def out_dir(cid: str) -> Path:
    return company_dir(cid) / "out"


def upload_dir(cid: str) -> Path:
    return company_dir(cid) / "uploads"


def ensure_out(cid: str) -> Path:
    d = out_dir(cid)
    d.mkdir(parents=True, exist_ok=True)
    return d


def retry(fn, *args, tries: int = 10, wait: float = 0.2):
    """fn(*args), retried while the file is briefly held by another program (Windows)."""
    for i in range(tries):
        try:
            return fn(*args)
        except FileNotFoundError:
            raise
        except OSError:
            if i == tries - 1:
                raise
            time.sleep(wait)


def tmp_path(directory: Path, suffix: str = "") -> Path:
    return directory / f"~{uuid.uuid4().hex[:10]}{suffix}"  # short: Windows MAX_PATH


def replace(src: Path | str, dst: Path | str) -> None:
    retry(os.replace, str(src), str(dst))


def remove(path: Path | str) -> None:
    try:
        retry(os.remove, str(path))
    except FileNotFoundError:
        pass


def _rmtree(d: str | Path) -> bool:
    """Remove a folder, retrying while it is held. True if it is gone."""
    for i in range(6):
        try:
            shutil.rmtree(d)
            return True
        except FileNotFoundError:
            return True
        except OSError:
            time.sleep(0.4 * (i + 1))
    shutil.rmtree(d, ignore_errors=True)
    return not os.path.exists(d)


def remove_company(cid: str) -> bool:
    d = company_dir(cid)
    ok = _rmtree(d)
    if not ok:
        log.warning("storage_not_fully_removed", path=str(d))
    return ok


def clear_leftovers(cid: str) -> None:
    """Leftovers of a deleted company are removed, else moved aside to <id>.deleted-<time> (never listed); never adopted."""
    d = company_dir(cid)
    if not d.is_dir() or _rmtree(d):
        return
    try:
        os.rename(d, f"{d}.deleted-{time.strftime('%Y%m%d-%H%M%S')}-{uuid.uuid4().hex[:4]}")
    except OSError as e:
        raise StoreError(f"the folder left by a deleted company '{cid}' is still in use (OneDrive or another program); close it and try again") from e


def deliverable_path(cid: str, filename: str) -> Path | None:
    p = out_dir(cid) / filename
    return p if p.is_file() else None
