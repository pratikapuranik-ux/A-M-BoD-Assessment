"""Tables. Companies are the legacy 'meta.json'; stage runs / prior runs hold run-file JSON; survey rows are anonymous.

Dialect-neutral: JSON columns, string primary keys, no server-side defaults that differ by backend.
"""
from __future__ import annotations

from typing import Any

from sqlalchemy import JSON, Boolean, Float, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class Company(Base):
    __tablename__ = "companies"
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    name: Mapped[str] = mapped_column(String(300), default="")
    short: Mapped[str] = mapped_column(String(120), default="")
    ticker: Mapped[str] = mapped_column(String(40), default="")
    period: Mapped[str] = mapped_column(String(16), default="")
    mode: Mapped[str] = mapped_column(String(40), default="")
    source: Mapped[str] = mapped_column(String(20), default="imported")
    created: Mapped[str] = mapped_column(String(32), default="")
    updated: Mapped[str | None] = mapped_column(String(32), nullable=True)
    problems: Mapped[list[Any] | None] = mapped_column(JSON, nullable=True)  # rule-check problems kept for review
    survey_used: Mapped[int | None] = mapped_column(Integer, nullable=True)  # responses the last inside-out run used


class StageRun(Base):
    """The current outside-in / inside-out run file of a company (run JSON incl. computed grades) and the one it replaced."""
    __tablename__ = "stage_runs"
    __table_args__ = (UniqueConstraint("company_id", "stage", name="uq_stage_runs_company_stage"),)
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    company_id: Mapped[str] = mapped_column(ForeignKey("companies.id", ondelete="CASCADE"), index=True)
    stage: Mapped[str] = mapped_column(String(20))  # outside_in | inside_out
    period: Mapped[str] = mapped_column(String(16), default="")
    run: Mapped[dict[str, Any]] = mapped_column(JSON)
    prev_run: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)


class PriorRun(Base):
    """An earlier quarter's run file, one per period."""
    __tablename__ = "prior_runs"
    __table_args__ = (UniqueConstraint("company_id", "period", name="uq_prior_runs_company_period"),)
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    company_id: Mapped[str] = mapped_column(ForeignKey("companies.id", ondelete="CASCADE"), index=True)
    period: Mapped[str] = mapped_column(String(32))  # sanitised period, as the legacy prior_<period>.json name
    run: Mapped[dict[str, Any]] = mapped_column(JSON)


class SurveyInvite(Base):
    __tablename__ = "survey_invites"
    token: Mapped[str] = mapped_column(String(64), primary_key=True)
    company_id: Mapped[str] = mapped_column(ForeignKey("companies.id", ondelete="CASCADE"), index=True)
    seq: Mapped[int] = mapped_column(Integer, default=0)  # invitation order
    email: Mapped[str] = mapped_column(String(254))
    created: Mapped[str] = mapped_column(String(16), default="")
    responded: Mapped[bool] = mapped_column(Boolean, default=False)


class SurveyResponse(Base):
    """One anonymous response: no token, email or time. `position` is random so row order cannot reveal who answered when."""
    __tablename__ = "survey_responses"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    company_id: Mapped[str] = mapped_column(ForeignKey("companies.id", ondelete="CASCADE"), index=True)
    position: Mapped[float] = mapped_column(Float)
    answers: Mapped[dict[str, Any]] = mapped_column(JSON)
    ratings: Mapped[dict[str, Any]] = mapped_column(JSON)


class SurveyHash(Base):
    """sha256 of each stored response, kept apart from the responses, to refuse duplicates."""
    __tablename__ = "survey_hashes"
    company_id: Mapped[str] = mapped_column(ForeignKey("companies.id", ondelete="CASCADE"), primary_key=True)
    hash: Mapped[str] = mapped_column(String(64), primary_key=True)


class Deliverable(Base):
    """A built file (docx / dashboard html / questionnaire) under NEXUS_STORAGE_DIR/<company id>/out/."""
    __tablename__ = "deliverables"
    __table_args__ = (UniqueConstraint("company_id", "key", name="uq_deliverables_company_key"),)
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    company_id: Mapped[str] = mapped_column(ForeignKey("companies.id", ondelete="CASCADE"), index=True)
    key: Mapped[str] = mapped_column(String(20))  # oi_docx | oi_html | io_docx | io_html | prior_docx | quest
    filename: Mapped[str] = mapped_column(String(300))
    size: Mapped[int] = mapped_column(Integer, default=0)
    created: Mapped[str] = mapped_column(String(32), default="")
