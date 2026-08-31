"""Add evidence-first construction and safety daily logs."""

import sqlalchemy as sa

from alembic import op

revision = "0007_daily_logs"
down_revision = "0006_site_event_extraction"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "daily_log_documents",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("project_id", sa.Integer(), nullable=False),
        sa.Column("log_date", sa.Date(), nullable=False),
        sa.Column("log_type", sa.String(length=30), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="RESTRICT"),
        sa.UniqueConstraint("project_id", "log_date", "log_type"),
    )
    op.create_index("ix_daily_log_documents_project_id", "daily_log_documents", ["project_id"])
    op.create_index("ix_daily_log_documents_log_date", "daily_log_documents", ["log_date"])
    op.create_index("ix_daily_log_documents_log_type", "daily_log_documents", ["log_type"])

    op.create_table(
        "daily_log_versions",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("document_id", sa.Integer(), nullable=False),
        sa.Column("project_id", sa.Integer(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("auto_content", sa.Text(), nullable=False),
        sa.Column("manual_content", sa.Text(), nullable=False),
        sa.Column("source_digest", sa.String(length=64), nullable=False),
        sa.Column("created_by", sa.Integer(), nullable=False),
        sa.Column("updated_by", sa.Integer(), nullable=False),
        sa.Column("confirmed_by", sa.Integer(), nullable=True),
        sa.Column("confirmed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["document_id"], ["daily_log_documents.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["updated_by"], ["users.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["confirmed_by"], ["users.id"], ondelete="RESTRICT"),
        sa.UniqueConstraint("document_id", "version"),
    )
    op.create_index("ix_daily_log_versions_document_id", "daily_log_versions", ["document_id"])
    op.create_index("ix_daily_log_versions_project_id", "daily_log_versions", ["project_id"])
    op.create_index("ix_daily_log_versions_status", "daily_log_versions", ["status"])

    op.create_table(
        "daily_log_sources",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("version_id", sa.String(length=36), nullable=False),
        sa.Column("project_id", sa.Integer(), nullable=False),
        sa.Column("event_id", sa.String(length=36), nullable=False),
        sa.Column("record_id", sa.Integer(), nullable=False),
        sa.Column("event_snapshot", sa.Text(), nullable=False),
        sa.Column("evidence_snapshot", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["version_id"], ["daily_log_versions.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["event_id"], ["site_events.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["record_id"], ["site_records.id"], ondelete="RESTRICT"),
        sa.UniqueConstraint("version_id", "event_id"),
    )
    op.create_index("ix_daily_log_sources_version_id", "daily_log_sources", ["version_id"])
    op.create_index("ix_daily_log_sources_project_id", "daily_log_sources", ["project_id"])
    op.create_index("ix_daily_log_sources_event_id", "daily_log_sources", ["event_id"])
    op.create_index("ix_daily_log_sources_record_id", "daily_log_sources", ["record_id"])

    op.create_table(
        "daily_log_audits",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("version_id", sa.String(length=36), nullable=False),
        sa.Column("project_id", sa.Integer(), nullable=False),
        sa.Column("actor_id", sa.Integer(), nullable=False),
        sa.Column("action", sa.String(length=30), nullable=False),
        sa.Column("before_data", sa.Text(), nullable=True),
        sa.Column("after_data", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["version_id"], ["daily_log_versions.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["actor_id"], ["users.id"], ondelete="RESTRICT"),
    )
    op.create_index("ix_daily_log_audits_version_id", "daily_log_audits", ["version_id"])
    op.create_index("ix_daily_log_audits_project_id", "daily_log_audits", ["project_id"])


def downgrade() -> None:
    op.drop_index("ix_daily_log_audits_project_id", table_name="daily_log_audits")
    op.drop_index("ix_daily_log_audits_version_id", table_name="daily_log_audits")
    op.drop_table("daily_log_audits")
    op.drop_index("ix_daily_log_sources_record_id", table_name="daily_log_sources")
    op.drop_index("ix_daily_log_sources_event_id", table_name="daily_log_sources")
    op.drop_index("ix_daily_log_sources_project_id", table_name="daily_log_sources")
    op.drop_index("ix_daily_log_sources_version_id", table_name="daily_log_sources")
    op.drop_table("daily_log_sources")
    op.drop_index("ix_daily_log_versions_status", table_name="daily_log_versions")
    op.drop_index("ix_daily_log_versions_project_id", table_name="daily_log_versions")
    op.drop_index("ix_daily_log_versions_document_id", table_name="daily_log_versions")
    op.drop_table("daily_log_versions")
    op.drop_index("ix_daily_log_documents_log_type", table_name="daily_log_documents")
    op.drop_index("ix_daily_log_documents_log_date", table_name="daily_log_documents")
    op.drop_index("ix_daily_log_documents_project_id", table_name="daily_log_documents")
    op.drop_table("daily_log_documents")
