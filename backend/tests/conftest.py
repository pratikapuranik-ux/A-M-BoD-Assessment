"""Test environment: a temp SQLite database and storage folder, never the project .env, never a live model call."""
import os
import shutil
import tempfile

import pytest

# Short temp path: Windows MAX_PATH. Set before any `app` module reads its settings.
TMP = tempfile.mkdtemp(prefix="nx_")
os.environ["NEXUS_SKIP_DOTENV"] = "1"
os.environ["NEXUS_DATABASE_URL"] = "sqlite:///" + os.path.join(TMP, "test.db").replace("\\", "/")
os.environ["NEXUS_STORAGE_DIR"] = os.path.join(TMP, "storage")
os.environ["BOARD_MIN_RESPONSES"] = "3"  # test the real guardrail, whatever .env says for demos
os.environ.pop("BOARD_PUBLIC_URL", None)
os.environ.pop("NEXUS_PUBLIC_URL", None)


@pytest.fixture(scope="session")
def client():
    from fastapi.testclient import TestClient

    from app.config import reset_settings
    reset_settings()
    from app.main import app
    with TestClient(app) as c:
        yield c


def pytest_sessionfinish(session, exitstatus):  # noqa: ARG001
    try:
        from app import db
        if db._engine is not None: db._engine.dispose()
    except Exception:  # noqa: BLE001
        pass
    shutil.rmtree(TMP, ignore_errors=True)
