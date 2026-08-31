"""Add record-level Event Extraction jobs, events, and revisions."""

import sqlalchemy as sa

from alembic import op

revision = "0006_site_event_extraction"
down_revision = "0005_voice_confirmation_idempotency"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "event_extraction_jobs",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("project_id", sa.Integer(), nullable=False),
        sa.Column("record_id", sa.Integer(), nullable=False),
        sa.Column("requested_by", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("provider", sa.String(length=50), nullable=False),
        sa.Column("model", sa.String(length=100), nullable=False),
        sa.Column("schema_version", sa.String(length=20), nullable=False),
        sa.Column("input_snapshot", sa.Text(), nullable=False),
        sa.Column("response_metadata", sa.Text(), nullable=True),
        sa.Column("result_event_id", sa.String(length=36), nullable=True),
        sa.Column("retry_of_job_id", sa.String(length=36), nullable=True),
        sa.Column("error_code", sa.String(length=50), nullable=True),
        sa.Column("error_message", sa.String(length=500), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["record_id"], ["site_records.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["requested_by"], ["users.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(
            ["retry_of_job_id"], ["event_extraction_jobs.id"], ondelete="SET NULL"
        ),
    )
    op.create_index("ix_event_extraction_jobs_project_id", "event_extraction_jobs", ["project_id"])
    op.create_index("ix_event_extraction_jobs_record_id", "event_extraction_jobs", ["record_id"])
    op.create_index("ix_event_extraction_jobs_status", "event_extraction_jobs", ["status"])
    op.create_index(
        "ix_event_extraction_jobs_result_event_id", "event_extraction_jobs", ["result_event_id"]
    )

    op.create_table(
        "site_events",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("project_id", sa.Integer(), nullable=False),
        sa.Column("source_record_id", sa.Integer(), nullable=False),
        sa.Column("extraction_job_id", sa.String(length=36), nullable=False, unique=True),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("schema_version", sa.String(length=20), nullable=False),
        sa.Column("event_type", sa.String(length=30), nullable=False),
        sa.Column("ai_output", sa.Text(), nullable=False),
        sa.Column("draft_data", sa.Text(), nullable=False),
        sa.Column("confirmed_data", sa.Text(), nullable=True),
        sa.Column("evidence_map", sa.Text(), nullable=False),
        sa.Column("overall_confidence", sa.Float(), nullable=False),
        sa.Column("confirmed_by", sa.Integer(), nullable=True),
        sa.Column("confirmed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("rejected_by", sa.Integer(), nullable=True),
        sa.Column("rejected_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("rejection_reason", sa.String(length=500), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["source_record_id"], ["site_records.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["extraction_job_id"], ["event_extraction_jobs.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(["confirmed_by"], ["users.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["rejected_by"], ["users.id"], ondelete="RESTRICT"),
    )
    op.create_index("ix_site_events_project_id", "site_events", ["project_id"])
    op.create_index("ix_site_events_source_record_id", "site_events", ["source_record_id"])
    op.create_index("ix_site_events_status", "site_events", ["status"])

    op.create_table(
        "event_revisions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("event_id", sa.String(length=36), nullable=False),
        sa.Column("project_id", sa.Integer(), nullable=False),
        sa.Column("actor_id", sa.Integer(), nullable=False),
        sa.Column("action", sa.String(length=30), nullable=False),
        sa.Column("before_data", sa.Text(), nullable=True),
        sa.Column("after_data", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["event_id"], ["site_events.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["actor_id"], ["users.id"], ondelete="RESTRICT"),
    )
    op.create_index("ix_event_revisions_event_id", "event_revisions", ["event_id"])
    op.create_index("ix_event_revisions_project_id", "event_revisions", ["project_id"])


def downgrade() -> None:
    op.drop_index("ix_event_revisions_project_id", table_name="event_revisions")
    op.drop_index("ix_event_revisions_event_id", table_name="event_revisions")
    op.drop_table("event_revisions")
    op.drop_index("ix_site_events_status", table_name="site_events")
    op.drop_index("ix_site_events_source_record_id", table_name="site_events")
    op.drop_index("ix_site_events_project_id", table_name="site_events")
    op.drop_table("site_events")
    op.drop_index("ix_event_extraction_jobs_result_event_id", table_name="event_extraction_jobs")
    op.drop_index("ix_event_extraction_jobs_status", table_name="event_extraction_jobs")
    op.drop_index("ix_event_extraction_jobs_record_id", table_name="event_extraction_jobs")
    op.drop_index("ix_event_extraction_jobs_project_id", table_name="event_extraction_jobs")
    op.drop_table("event_extraction_jobs")
