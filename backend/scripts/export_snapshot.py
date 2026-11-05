"""Data for the read-only HTML snapshot of one company: the API answers the screens read, plus Word and HTML files built fresh in memory.
Reads only; nothing stored is changed (the files on disk are not touched). Survey invites (emails, tokens) are left out.
Run from the backend folder:  python scripts/export_snapshot.py <company-id> out.json"""
from __future__ import annotations

import base64
import json
import sys
import tempfile
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from fastapi.testclient import TestClient  # noqa: E402

from app.domain import view as convert  # noqa: E402
from app.main import app  # noqa: E402
from app.services import deliverables as D  # noqa: E402
from app.services import repo  # noqa: E402

DOCX, HTML = "application/vnd.openxmlformats-officedocument.wordprocessingml.document", "text/html; charset=utf-8"


def main(cid: str, out: str) -> None:
    if not repo.exists(cid): raise SystemExit(f"company '{cid}' not found")
    with TestClient(app) as c:
        def get(p):
            r = c.get("/api" + p)
            return r.json() if r.status_code == 200 else None
        survey = get(f"/companies/{cid}/survey") or {}
        survey["invites"] = []  # no emails or tokens in a file that gets shared
        routes = {
            "/health": {"ok": True, "research": {"enabled": False, "reason": "Read-only snapshot: research is switched off."}},
            "/companies": [x for x in get("/companies") or [] if x["id"] == cid],
            f"/companies/{cid}/view": get(f"/companies/{cid}/view"),
            f"/companies/{cid}/survey": survey,
        }
        if (fw := get("/framework")) is not None: routes["/framework"] = fw
    meta = repo.load_meta(cid); oi = repo.read_run(cid, "outside_in"); io = repo.read_run(cid, "inside_out"); prior = repo.latest_prior(cid)
    names = D.file_names(meta.get("short") or meta.get("name", cid), oi, io, prior)
    steps = [("oi_docx", D.build_docx, oi, DOCX), ("oi_html", D.build_dashboard, oi, HTML)]
    if io: steps += [("io_docx", D.build_docx, io, DOCX), ("io_html", D.build_dashboard, io, HTML)]
    if prior: steps.append(("prior_docx", D.build_docx, prior, DOCX))
    steps.append(("quest", D.build_questionnaire, convert.company_of(oi)["name"], DOCX))
    files = {}
    with tempfile.TemporaryDirectory() as tmp:
        for key, fn, src, mime in steps:
            p = Path(tmp) / names[key]; fn(src, str(p))
            files[key] = {"type": mime, "name": names[key], "b64": base64.b64encode(p.read_bytes()).decode("ascii")}
    Path(out).write_text(json.dumps({"routes": routes, "files": files, "taken": date.today().isoformat()}), encoding="utf-8")
    print(f"wrote {out}: {len(routes)} routes, {len(files)} files ({', '.join(files)})")


if __name__ == "__main__":
    if len(sys.argv) != 3: raise SystemExit(__doc__)
    main(sys.argv[1], sys.argv[2])
