"""Settings from the environment (and the project .env, which is never printed). Values already set in the shell win."""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent
PROJECT_ROOT = BACKEND_DIR.parent


def _load_env(path: Path) -> None:
    if not path.is_file():
        return
    for line in path.read_text(encoding="utf-8-sig").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        k = k.strip().removeprefix("export ").strip()
        v = v.strip().strip('"').strip("'")
        if k and v and k not in os.environ:
            os.environ[k] = v


@dataclass
class Settings:
    database_url: str
    storage_dir: Path
    min_responses: int
    public_url: str
    frontend_dist: Path
    log_level: str
    log_json: bool
    cors_origins: list[str] = field(default_factory=list)


def load_settings() -> Settings:
    if not os.environ.get("BOARD_SKIP_DOTENV"):
        _load_env(Path(os.environ.get("BOARD_ENV_FILE") or PROJECT_ROOT / ".env"))
    db = os.environ.get("BOARD_DATABASE_URL") or "sqlite:///./bod_assessment.db"
    cors = [o.strip() for o in (os.environ.get("BOARD_CORS_ORIGINS") or "http://localhost:5173,http://127.0.0.1:5173").split(",") if o.strip()]
    return Settings(
        database_url=db,
        storage_dir=Path(os.environ.get("BOARD_STORAGE_DIR") or "./storage").resolve(),
        min_responses=max(1, int(os.environ.get("BOARD_MIN_RESPONSES") or 3)),
        public_url=(os.environ.get("BOARD_PUBLIC_URL") or "").strip().rstrip("/"),
        frontend_dist=Path(os.environ.get("BOARD_FRONTEND_DIST") or PROJECT_ROOT / "frontend" / "dist"),
        log_level=(os.environ.get("BOARD_LOG_LEVEL") or "INFO").upper(),
        log_json=(os.environ.get("BOARD_LOG_JSON") or "").lower() in ("1", "true", "yes"),
        cors_origins=cors,
    )


@lru_cache
def get_settings() -> Settings:
    return load_settings()


def reset_settings() -> None:
    """Drop the cached settings (tests change the environment between runs)."""
    get_settings.cache_clear()
