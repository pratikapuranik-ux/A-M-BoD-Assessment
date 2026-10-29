"""Reference routes: health and the framework."""
from __future__ import annotations

from fastapi import APIRouter

from app.domain import view as convert
from app.schemas import HealthOut
from app.services import runs

router = APIRouter()


@router.get("/api/health", response_model=HealthOut)
def health():
    return {"ok": True, "research": runs.research_status()}


@router.get("/api/framework")
def framework():
    return convert.framework()
