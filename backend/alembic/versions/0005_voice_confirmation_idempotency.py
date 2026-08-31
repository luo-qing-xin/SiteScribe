"""Add a database-level idempotency key for voice confirmation."""

import sqlalchemy as sa

from alembic import op

revision = "0005_voice_confirmation_idempotency"
down_revision = "0004_preserve_provider_payload"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "site_records",
        sa.Column("source_transcription_job_id", sa.String(length=36), nullable=True),
    )
    op.create_index(
        "ix_site_records_source_transcription_job_id",
        "site_records",
        ["source_transcription_job_id"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index("ix_site_records_source_transcription_job_id", table_name="site_records")
    op.drop_column("site_records", "source_transcription_job_id")
