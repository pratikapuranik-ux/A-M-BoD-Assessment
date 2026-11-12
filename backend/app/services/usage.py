"""Token ledger: one JSON line per model call in storage/logs/usage.jsonl (best effort: a run never depends on it).

`scope(job_id)` marks the calls of one background job; `Pool` carries that mark into the worker threads a job starts.
scripts/usage_summary.py totals the ledger per job and prices it."""
from __future__ import annotations

import contextvars
import json
import threading
import time
from concurrent.futures import ThreadPoolExecutor

_job: contextvars.ContextVar[str] = contextvars.ContextVar("usage_job", default="")
_lock = threading.Lock()


def scope(job_id: str) -> None:
    _job.set(job_id)


class Pool(ThreadPoolExecutor):
    """ThreadPoolExecutor whose tasks run in the context of the code that submitted them (keeps the job mark)."""
    def submit(self, fn, /, *args, **kwargs):
        return super().submit(contextvars.copy_context().run, fn, *args, **kwargs)  # map() goes through submit()


def _n(obj, name) -> int:
    v = getattr(obj, name, None)
    return v if isinstance(v, int) else 0


def record(step: str, model: str | None, usage) -> None:
    """Append the token counts of one model call. `usage` is the SDK usage object (or None)."""
    try:
        if usage is None: return
        from app.agents import settings as cfg
        from app.services import storage
        tool = getattr(usage, "server_tool_use", None)
        row = {"ts": time.strftime("%Y-%m-%d %H:%M:%S"), "job": _job.get(), "step": step, "model": model or cfg.MODEL,
               "runs": cfg.CONSISTENCY_RUNS, "input": _n(usage, "input_tokens"), "cache_read": _n(usage, "cache_read_input_tokens"),
               "cache_write": _n(usage, "cache_creation_input_tokens"), "output": _n(usage, "output_tokens"),
               "web_search": _n(tool, "web_search_requests"), "web_fetch": _n(tool, "web_fetch_requests")}
        d = storage.root() / "logs"; d.mkdir(parents=True, exist_ok=True)
        with _lock, open(d / "usage.jsonl", "a", encoding="utf-8") as fh: fh.write(json.dumps(row) + "\n")
    except Exception:  # noqa: BLE001
        pass
