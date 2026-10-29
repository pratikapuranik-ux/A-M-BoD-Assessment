"""Document uploads (base64 JSON, as the front end sends them) -> extracted text/PDF payloads for the research agents."""
from __future__ import annotations

from app.api.errors import ApiError
from app.services import documents

MAX_OI_DOCS = 10  # documents supplied with an outside-in research request


def extract_documents(docs: list, *, max_slot: int | None = None) -> tuple[list[dict], list[str]]:
    """Returns (extracted, problems). Raises ApiError(400) when the documents together exceed the upload limit.
    max_slot: None for outside-in (slot is always 0); else the highest valid inside-out slot."""
    out: list[dict] = []; probs: list[str] = []; total = 0
    for d in docs:
        if not isinstance(d, dict): probs.append("each document must be an object"); continue
        total += len(str(d.get("data_b64") or "")) * 3 // 4
        if total > documents.MAX_UPLOAD:
            raise ApiError(400, f"{d.get('name') or 'document'}: the documents together exceed {documents.MAX_UPLOAD // 2**20} MB; send fewer or smaller files")
        try:
            slot = 0
            if max_slot is not None:
                slot = int(d.get("slot") or 0)
                if not 0 <= slot <= max_slot: raise documents.ExtractError(f"{d.get('name')}: slot must be 0-{max_slot}")
            out.append(documents.extract_b64(dict(d, slot=slot)))
        except (documents.ExtractError, ValueError) as e:
            probs.append(str(e))
    if not probs:
        try: documents.fit_pdfs(out)
        except documents.ExtractError as e: probs.append(str(e))
    return out, probs
