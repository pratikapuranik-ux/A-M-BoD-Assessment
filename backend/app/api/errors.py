"""API error type, handlers (same JSON shape as server/app.py: {"error", "problems", job_id?}) and the JSON body reader."""
from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.log import get_logger
from app.services import jobs

log = get_logger(__name__)
MAX_JSON_BODY = 400 * 1024 * 1024


class ApiError(Exception):
    def __init__(self, status: int, error: str, problems: list | None = None, job_id: str | None = None):
        super().__init__(error); self.status = status; self.error = error; self.problems = problems or []; self.job_id = job_id


def submit(kind: str, work, *keys: str) -> jobs.Job:
    try: return jobs.submit(kind, work, keys)
    except jobs.Busy as e: raise ApiError(409, "a job is already running for this company; wait for it to finish", job_id=e.job.id)


async def read_body(request: Request) -> dict:
    if int(request.headers.get("content-length") or 0) > MAX_JSON_BODY:  # files do not travel in JSON bodies; only small inline files do
        raise ApiError(413, f"the request is too large (over {MAX_JSON_BODY // 2**20} MB); add documents through the upload step, one file at a time")
    try: b = await request.json()
    except Exception: raise ApiError(400, "request body must be JSON")
    if not isinstance(b, dict): raise ApiError(400, "request body must be a JSON object")
    return b


def register(app: FastAPI) -> None:
    @app.exception_handler(ApiError)
    async def _api_error(_r: Request, e: ApiError):
        return JSONResponse({"error": e.error, "problems": e.problems, **({"job_id": e.job_id} if e.job_id else {})}, status_code=e.status)

    @app.exception_handler(PermissionError)
    async def _locked(_r: Request, e: PermissionError):
        return JSONResponse({"error": "a file is in use by OneDrive or another program; try again in a moment", "problems": []}, status_code=503)

    @app.exception_handler(Exception)
    async def _unexpected(request: Request, e: Exception):
        import time, traceback
        text = "".join(traceback.format_exception(type(e), e, e.__traceback__))
        try:  # keep the trace where it can be read after the BACKEND window is closed
            from app.services import storage
            d = storage.root() / "logs"; d.mkdir(parents=True, exist_ok=True)
            with open(d / "errors.log", "a", encoding="utf-8") as fh: fh.write(f"{time.strftime('%Y-%m-%d %H:%M:%S')} {request.method} {request.url.path}\n{text}\n")
        except Exception:  # noqa: BLE001
            pass
        return JSONResponse({"error": f"unexpected server error ({type(e).__name__}: {str(e)[:160]}); the details are in backend/storage/logs/errors.log", "problems": []}, status_code=500)

    @app.exception_handler(StarletteHTTPException)
    async def _http_error(_r: Request, e: StarletteHTTPException):
        return JSONResponse({"error": str(e.detail), "problems": []}, status_code=e.status_code)

    @app.exception_handler(RequestValidationError)
    async def _validation_error(_r: Request, e: RequestValidationError):
        return JSONResponse({"error": "invalid request", "problems": [f"{'.'.join(map(str, x.get('loc', [])))}: {x.get('msg')}" for x in e.errors()]}, status_code=422)
