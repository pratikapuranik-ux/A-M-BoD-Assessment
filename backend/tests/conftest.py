"""Test environment: a temp SQLite database and storage folder, never the project .env, never a live model call."""
import os
import shutil
import tempfile

import pytest

# Short temp path: Windows MAX_PATH. Set before any `app` module reads its settings.
TMP = tempfile.mkdtemp(prefix="nx_")
os.environ["BOARD_SKIP_DOTENV"] = "1"
os.environ["BOARD_DATABASE_URL"] = "sqlite:///" + os.path.join(TMP, "test.db").replace("\\", "/")
os.environ["BOARD_STORAGE_DIR"] = os.path.join(TMP, "storage")
os.environ["BOARD_PIPELINE"] = "single"  # the scripted fake-client tests describe one conversation per subject; tests/test_tasks.py turns the task pipeline on
os.environ["BOARD_ANCHOR_RECHECK"] = "off"  # the scripted fake clients know no recheck call; tests/test_recheck.py turns it on
os.environ["BOARD_TASK_CACHE"] = "off"  # tests that exercise the task cache turn it on
os.environ["BOARD_MIN_RESPONSES"] = "3"  # test the real guardrail, whatever .env says for demos
os.environ.pop("BOARD_PUBLIC_URL", None)
os.environ.pop("BOARD_PUBLIC_URL", None)


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
