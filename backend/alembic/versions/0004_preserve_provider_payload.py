"""Preserve provider output separately from deterministic system resolution."""

import sqlalchemy as sa

from alembic import op

revision = "0004_preserve_provider_payload"
down_revision = "0003_remove_media_job_fk_cycle"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("event_drafts", sa.Column("system_resolved_payload", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("event_drafts", "system_resolved_payload")
