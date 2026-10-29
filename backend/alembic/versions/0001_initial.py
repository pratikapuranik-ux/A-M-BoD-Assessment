"""initial schema: companies, runs, survey, deliverables

Revision ID: 0001
Revises:
"""
from alembic import op
import sqlalchemy as sa

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def _cid(index=True):
    return sa.Column("company_id", sa.String(64), sa.ForeignKey("companies.id", ondelete="CASCADE"), nullable=False, index=index)


def upgrade() -> None:
    op.create_table(
        "companies",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("name", sa.String(300), nullable=False),
        sa.Column("short", sa.String(120), nullable=False),
        sa.Column("ticker", sa.String(40), nullable=False),
        sa.Column("period", sa.String(16), nullable=False),
        sa.Column("mode", sa.String(40), nullable=False),
        sa.Column("source", sa.String(20), nullable=False),
        sa.Column("created", sa.String(32), nullable=False),
        sa.Column("updated", sa.String(32), nullable=True),
        sa.Column("problems", sa.JSON(), nullable=True),
        sa.Column("survey_used", sa.Integer(), nullable=True),
    )
    op.create_table(
        "stage_runs",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        _cid(),
        sa.Column("stage", sa.String(20), nullable=False),
        sa.Column("period", sa.String(16), nullable=False),
        sa.Column("run", sa.JSON(), nullable=False),
        sa.Column("prev_run", sa.JSON(), nullable=True),
        sa.UniqueConstraint("company_id", "stage", name="uq_stage_runs_company_stage"),
    )
    op.create_table(
        "prior_runs",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        _cid(),
        sa.Column("period", sa.String(32), nullable=False),
        sa.Column("run", sa.JSON(), nullable=False),
        sa.UniqueConstraint("company_id", "period", name="uq_prior_runs_company_period"),
    )
    op.create_table(
        "survey_invites",
        sa.Column("token", sa.String(64), primary_key=True),
        _cid(),
        sa.Column("seq", sa.Integer(), nullable=False),
        sa.Column("email", sa.String(254), nullable=False),
        sa.Column("created", sa.String(16), nullable=False),
        sa.Column("responded", sa.Boolean(), nullable=False),
    )
    op.create_table(
        "survey_responses",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        _cid(),
        sa.Column("position", sa.Float(), nullable=False),
        sa.Column("answers", sa.JSON(), nullable=False),
        sa.Column("ratings", sa.JSON(), nullable=False),
    )
    op.create_table(
        "survey_hashes",
        sa.Column("company_id", sa.String(64), sa.ForeignKey("companies.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("hash", sa.String(64), primary_key=True),
    )
    op.create_table(
        "deliverables",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        _cid(),
        sa.Column("key", sa.String(20), nullable=False),
        sa.Column("filename", sa.String(300), nullable=False),
        sa.Column("size", sa.Integer(), nullable=False),
        sa.Column("created", sa.String(32), nullable=False),
        sa.UniqueConstraint("company_id", "key", name="uq_deliverables_company_key"),
    )


def downgrade() -> None:
    for t in ("deliverables", "survey_hashes", "survey_responses", "survey_invites", "prior_runs", "stage_runs", "companies"):
        op.drop_table(t)
