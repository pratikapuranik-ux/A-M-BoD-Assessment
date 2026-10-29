"""API error type, handlers (same JSON shape as server/app.py: {"error", "problems", job_id?}) and the JSON body reader."""
from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.log import get_logger
from app.services import documents, jobs

log = get_logger(__name__)


class ApiError(Exception):
    def __init__(self, status: int, error: str, problems: list | None = None, job_id: str | None = None):
        super().__init__(error); self.status = status; self.error = error; self.problems = problems or []; self.job_id = job_id


def submit(kind: str, work, *keys: str) -> jobs.Job:
    try: return jobs.submit(kind, work, keys)
    except jobs.Busy as e: raise ApiError(409, "a job is already running for this company; wait for it to finish", job_id=e.job.id)


async def read_body(request: Request) -> dict:
    if int(request.headers.get("content-length") or 0) > 140 * 1024 * 1024:
        raise ApiError(413, f"the upload is too large; at most {documents.MAX_FILE // 2**20} MB per file and {documents.MAX_UPLOAD // 2**20} MB in total")
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

    @app.exception_handler(StarletteHTTPException)
    async def _http_error(_r: Request, e: StarletteHTTPException):
        return JSONResponse({"error": str(e.detail), "problems": []}, status_code=e.status_code)

    @app.exception_handler(RequestValidationError)
    async def _validation_error(_r: Request, e: RequestValidationError):
        return JSONResponse({"error": "invalid request", "problems": [f"{'.'.join(map(str, x.get('loc', [])))}: {x.get('msg')}" for x in e.errors()]}, status_code=422)
