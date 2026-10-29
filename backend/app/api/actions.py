"""Edit, add and delete the board actions of a company's current stage run (inside-out when it exists, else outside-in)."""
from __future__ import annotations

from fastapi import APIRouter, Request

from app.api.errors import ApiError, read_body
from app.services import repo

router = APIRouter()
MAX_ACTIONS = 5  # the view shows the first five


def _load(cid: str) -> tuple[str, dict]:
    if not repo.exists(cid): raise ApiError(404, f"company '{cid}' not found")
    for stage in ("inside_out", "outside_in"):
        if (run := repo.read_run(cid, stage)) is not None: return stage, run
    raise ApiError(404, "no assessment run for this company yet")


def _clean(b: dict, partial: bool) -> dict:
    out = {}
    for k, cap in (("heading", 300), ("description", 4000), ("target", 200)):
        if k in b:
            if not isinstance(b[k], str): raise ApiError(400, f"{k} must be text")
            out["target_by" if k == "target" else k] = b[k].strip()[:cap]
    if "measures" in b:
        m = b["measures"]
        if not isinstance(m, list) or not all(isinstance(x, str) for x in m): raise ApiError(400, "measures must be a list of text")
        out["measures"] = [x.strip()[:500] for x in m if x.strip()][:10]
    if not partial and not out.get("heading"): raise ApiError(400, "an action needs a heading")
    if partial and "heading" in out and not out["heading"]: raise ApiError(400, "heading cannot be empty")
    return out


def _idx(run: dict, n: int) -> int:
    acts = run.setdefault("actions", [])
    if not 1 <= n <= min(len(acts), MAX_ACTIONS): raise ApiError(404, f"no action {n}")
    return n - 1


@router.post("/api/companies/{cid}/actions")
async def add_action(cid: str, request: Request):
    stage, run = _load(cid); a = _clean(await read_body(request), False)
    acts = run.setdefault("actions", [])
    if len(acts) >= MAX_ACTIONS: raise ApiError(409, f"a board has at most {MAX_ACTIONS} actions; delete one first")
    acts.append({"measures": [], "description": "", "target_by": "", **a, "edited": True})
    repo.write_run(cid, stage, run)
    return {"ok": True, "stage": stage, "count": len(acts)}


@router.put("/api/companies/{cid}/actions/{n}")
async def edit_action(cid: str, n: int, request: Request):
    stage, run = _load(cid); a = _clean(await read_body(request), True); i = _idx(run, n)
    run["actions"][i] = {**run["actions"][i], **a, "edited": True}
    repo.write_run(cid, stage, run)
    return {"ok": True, "stage": stage, "count": len(run["actions"])}


@router.delete("/api/companies/{cid}/actions/{n}")
def delete_action(cid: str, n: int):
    stage, run = _load(cid); i = _idx(run, n)
    del run["actions"][i]
    repo.write_run(cid, stage, run)
    return {"ok": True, "stage": stage, "count": len(run["actions"])}
