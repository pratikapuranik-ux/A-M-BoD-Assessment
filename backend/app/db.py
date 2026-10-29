"""SQLAlchemy engine and session factory. SQLite by default (WAL, foreign keys on); any SQLAlchemy URL via NEXUS_DATABASE_URL."""
from __future__ import annotations

from contextlib import contextmanager
from typing import Iterator

from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.config import get_settings


class Base(DeclarativeBase):
    pass


_engine: Engine | None = None
_factory: sessionmaker[Session] | None = None


def make_engine(url: str) -> Engine:
    kw: dict = {"future": True}
    if url.startswith("sqlite"):
        kw["connect_args"] = {"check_same_thread": False, "timeout": 30}
        if url in ("sqlite://", "sqlite:///:memory:") or ":memory:" in url:
            kw["poolclass"] = StaticPool
    eng = create_engine(url, **kw)
    if url.startswith("sqlite"):
        @event.listens_for(eng, "connect")
        def _pragmas(dbapi, _rec):  # noqa: ANN001
            cur = dbapi.cursor()
            cur.execute("PRAGMA foreign_keys=ON")
            if ":memory:" not in url:
                cur.execute("PRAGMA journal_mode=WAL")
            cur.close()
    return eng


def init_engine(url: str | None = None) -> Engine:
    """(Re)create the engine. Tests call this with a temp or in-memory URL."""
    global _engine, _factory
    if _engine is not None:
        _engine.dispose()
    _engine = make_engine(url or get_settings().database_url)
    _factory = sessionmaker(bind=_engine, expire_on_commit=False, future=True)
    return _engine


def get_engine() -> Engine:
    return _engine or init_engine()


def SessionLocal() -> Session:  # noqa: N802 - factory-style name
    if _factory is None:
        init_engine()
    assert _factory is not None
    return _factory()


@contextmanager
def session_scope() -> Iterator[Session]:
    s = SessionLocal()
    try:
        yield s
        s.commit()
    except BaseException:
        s.rollback()
        raise
    finally:
        s.close()


def create_all() -> None:
    """Create tables straight from the models (tests, quick starts). Production uses `alembic upgrade head`."""
    from app import models  # noqa: F401
    Base.metadata.create_all(get_engine())
