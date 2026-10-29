"""In-process background jobs: research and inside-out runs on one pool, imports and rebuilds on another so they never wait."""
from __future__ import annotations

import threading
import time
import traceback
import uuid
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Callable, Iterable

_pool = ThreadPoolExecutor(max_workers=3, thread_name_prefix="job")
_build_pool = ThreadPoolExecutor(max_workers=2, thread_name_prefix="build")
BUILD_KINDS = {"build", "import"}
_jobs: dict[str, "Job"] = {}
_active: dict[str, "Job"] = {}  # company id (or pending id of a research run) -> its live job
_lock = threading.Lock()


class JobError(Exception):
    """Raise inside a job to fail it with a clean message (and optional rule-check problems / partial result)."""
    def __init__(self, message: str, problems: list | None = None, result: Any = None):
        super().__init__(message); self.problems = problems or []; self.result = result


class Busy(Exception):
    """A live job already holds one of the keys."""
    def __init__(self, job: "Job"):
        super().__init__(job.id); self.job = job


class Job:
    def __init__(self, kind: str):
        self.id = uuid.uuid4().hex[:12]; self.kind = kind; self.status = "queued"; self.progress = 0
        self.message = "Queued"; self.log: list[str] = []; self.result: Any = None; self.error: str | None = None
        self.problems: list = []; self.created = time.time(); self.updated = self.created

    def live(self) -> bool:
        return self.status in ("queued", "running")

    def update(self, pct: int | None = None, msg: str | None = None) -> None:
        with _lock:
            if pct is not None: self.progress = max(0, min(100, int(pct)))
            if msg: self.message = msg; self.log.append(f"{time.strftime('%H:%M:%S')} {msg}")
            self.updated = time.time()

    def to_dict(self) -> dict:
        with _lock:
            return {"id": self.id, "kind": self.kind, "status": self.status, "progress": self.progress, "message": self.message,
                    "log": list(self.log), "result": self.result, "error": self.error, "problems": list(self.problems)}


def active(key: str) -> Job | None:
    with _lock:
        j = _active.get(key)
        return j if j and j.live() else None


def hold(key: str, job: Job) -> None:
    """Also mark `key` as held by `job` (e.g. the id a research run was stored under); raises Busy if another live job has it."""
    with _lock:
        j = _active.get(key)
        if j and j is not job and j.live(): raise Busy(j)
        _active[key] = job


def submit(kind: str, fn: Callable[[Job], Any], keys: Iterable[str] = ()) -> Job:
    """Run fn(job) in the background; its return value becomes job.result. Raises Busy if a live job holds one of keys."""
    job = Job(kind); keys = list(keys)
    with _lock:
        if busy := next((j for k in keys if (j := _active.get(k)) and j.live()), None): raise Busy(busy)
        _jobs[job.id] = job
        for k in keys: _active[k] = job

    def run():
        job.status = "running"; job.update(1, "Started")
        try:
            res = fn(job)
            with _lock: job.result = res; job.status = "done"; job.progress = 100
            job.update(None, "Done")
        except JobError as e:
            with _lock: job.status = "error"; job.error = str(e); job.problems = e.problems; job.result = e.result
            job.update(None, f"Failed: {e}")
        except Exception as e:  # noqa: BLE001 - surface anything as a job error
            with _lock: job.status = "error"; job.error = f"{type(e).__name__}: {e}"
            job.log.append(traceback.format_exc(limit=4)); job.update(None, f"Failed: {job.error}")
        finally:
            with _lock:
                for k in [k for k, j in _active.items() if j is job]: _active.pop(k)

    (_build_pool if kind in BUILD_KINDS else _pool).submit(run)
    return job


def get(job_id: str) -> Job | None:
    return _jobs.get(job_id)


def wait(job_id: str, timeout: float = 600) -> Job:
    end = time.time() + timeout
    while time.time() < end:
        j = _jobs[job_id]
        if j.status in ("done", "error"): return j
        time.sleep(0.1)
    raise TimeoutError(job_id)
