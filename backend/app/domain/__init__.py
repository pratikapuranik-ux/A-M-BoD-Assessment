"""Pure-logic domain layer: skill reference data, grading engine, view builder. No web or DB imports."""
from .engine import grade, load_history  # noqa: F401
from .view import base_view, company_id, company_of, peers_of, short_name, slug, to_view  # noqa: F401
