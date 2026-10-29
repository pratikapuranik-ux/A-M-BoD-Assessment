"""FastAPI app factory: `uvicorn app.main:app` (run from backend/). Serves the API under /api and frontend/dist if built."""
from __future__ import annotations

import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from app import db
from app.api import assessments, errors, reference, survey
from app.api.errors import ApiError
from app.config import get_settings
from app.log import configure_logging, get_logger


def create_app() -> FastAPI:
    st = get_settings()
    configure_logging(st.log_level, st.log_json)
    log = get_logger("nexus")

    @asynccontextmanager
    async def lifespan(_app: FastAPI):
        st.storage_dir.mkdir(parents=True, exist_ok=True)
        db.init_engine()
        if os.environ.get("NEXUS_AUTO_CREATE_TABLES", "1") != "0":
            db.create_all()  # no-op when `alembic upgrade head` has already built the schema
        log.info("startup", database=st.database_url.split("///")[0], storage=str(st.storage_dir))
        yield

    app = FastAPI(title="NEXUS Board Assessment", lifespan=lifespan)
    app.add_middleware(CORSMiddleware, allow_origins=st.cors_origins, allow_methods=["*"], allow_headers=["*"])
    errors.register(app)
    app.include_router(reference.router)
    app.include_router(survey.router)
    app.include_router(assessments.router)

    @app.api_route("/api/{rest:path}", methods=["GET", "POST", "PUT", "DELETE", "PATCH"])
    def api_404(rest: str):
        raise ApiError(404, f"no API route /api/{rest}")

    dist: Path = st.frontend_dist
    if (dist / "index.html").is_file():
        if (dist / "assets").is_dir():
            app.mount("/assets", StaticFiles(directory=str(dist / "assets")), name="assets")

        @app.get("/{path:path}", include_in_schema=False)
        def spa(path: str):
            f = (dist / path).resolve()
            if path and f.is_file() and dist.resolve() in f.parents:
                return FileResponse(str(f))
            return FileResponse(str(dist / "index.html"), headers={"Cache-Control": "no-cache"})
    else:
        @app.get("/", include_in_schema=False)
        def index():
            return JSONResponse({"app": "NEXUS Board Assessment API", "frontend": "not built (run `npm run build` in frontend/); API docs at /docs", "health": "/api/health"})
    return app


app = create_app()
