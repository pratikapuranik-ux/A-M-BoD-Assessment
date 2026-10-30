"""Pydantic models for the JSON the API returns (and documents the request bodies). Shapes match server/app.py and js/api.js.
Request bodies are read as raw JSON in the routes so error messages stay identical to the prototype."""
from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict


class ResearchStatus(BaseModel):
    enabled: bool
    reason: str = ""


class HealthOut(BaseModel):
    ok: bool
    research: ResearchStatus


class ErrorOut(BaseModel):
    error: str
    problems: list[Any] = []
    job_id: str | None = None


class JobOut(BaseModel):
    id: str
    kind: str
    status: str
    progress: int
    message: str
    log: list[str]
    result: Any = None
    error: str | None = None
    problems: list[Any] = []


class JobRef(BaseModel):
    job_id: str


class ImportOut(BaseModel):
    id: str
    job_id: str


class DeleteOut(BaseModel):
    ok: bool
    id: str


class OkOut(BaseModel):
    ok: bool


class InviteOut(BaseModel):
    token: str
    email: str
    created: str
    responded: bool
    link: str


class ResponseItemOut(BaseModel):
    id: int
    name: str


class SurveyStatusOut(BaseModel):
    invites: list[InviteOut]
    items: list[ResponseItemOut] = []
    responses: int
    count: int
    min: int
    can_generate: bool
    reason: str | None = None
    local: bool


class PeerIn(BaseModel):
    name: str
    ticker: str = ""


class DocumentIn(BaseModel):
    name: str
    data_b64: str
    slot: int = 0
    mime: str | None = None


class ResearchIn(BaseModel):
    model_config = ConfigDict(extra="allow")
    company: str
    ticker: str = ""
    peers: list[PeerIn]
    period: str
    mode: str = "director_request"
    documents: list[DocumentIn] = []


class InsideOutIn(BaseModel):
    mode: str | None = None
    documents: list[DocumentIn] = []


class ImportIn(BaseModel):
    outside_in: dict[str, Any]
    inside_out: dict[str, Any] | None = None
    priors: list[dict[str, Any]] = []
    replace: bool = False


class InvitesIn(BaseModel):
    emails: list[str]


class ResponseIn(BaseModel):
    answers: dict[str, str] = {}
    ratings: dict[str, int] = {}
