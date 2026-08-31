"""Add the Evidence First voice transcription and event draft pipeline."""

import sqlalchemy as sa

from alembic import op

revision = "0002_voice_ai_pipeline"
down_revision = "0001_initial"
branch_labels = None
depends_on = None


def upgrade() -> None:
    naming = {"fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s"}
    op.add_column(
        "projects",
        sa.Column("timezone", sa.String(length=64), nullable=False, server_default="Asia/Shanghai"),
    )
    op.add_column(
        "site_records",
        sa.Column("source_type", sa.String(length=20), nullable=False, server_default="MANUAL"),
    )
    op.add_column("site_records", sa.Column("structured_event", sa.Text(), nullable=True))
    op.add_column(
        "site_records", sa.Column("event_schema_version", sa.String(length=20), nullable=True)
    )

    with op.batch_alter_table("media_files", naming_convention=naming) as batch:
        batch.add_column(sa.Column("project_id", sa.Integer(), nullable=True))
        batch.add_column(sa.Column("created_by", sa.Integer(), nullable=True))
        batch.add_column(sa.Column("transcription_job_id", sa.String(length=36), nullable=True))
        batch.alter_column("site_record_id", existing_type=sa.Integer(), nullable=True)
    op.execute(
        """
        UPDATE media_files
        SET project_id = (SELECT project_id FROM site_records WHERE site_records.id = media_files.site_record_id),
            created_by = (SELECT recorder_id FROM site_records WHERE site_records.id = media_files.site_record_id)
        """
    )
    with op.batch_alter_table("media_files", naming_convention=naming) as batch:
        batch.alter_column("project_id", existing_type=sa.Integer(), nullable=False)
        batch.alter_column("created_by", existing_type=sa.Integer(), nullable=False)
        batch.create_foreign_key(
            "fk_media_files_project_id", "projects", ["project_id"], ["id"], ondelete="RESTRICT"
        )
        batch.create_foreign_key(
            "fk_media_files_created_by", "users", ["created_by"], ["id"], ondelete="RESTRICT"
        )
        batch.drop_constraint("fk_media_files_site_record_id_site_records", type_="foreignkey")
        batch.create_foreign_key(
            "fk_media_files_site_record_id",
            "site_records",
            ["site_record_id"],
            ["id"],
            ondelete="SET NULL",
        )

    op.create_table(
        "transcription_jobs",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("project_id", sa.Integer(), nullable=False),
        sa.Column("created_by", sa.Integer(), nullable=False),
        sa.Column("original_audio_media_id", sa.Integer(), nullable=True, unique=True),
        sa.Column("normalized_audio_media_id", sa.Integer(), nullable=True, unique=True),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("detected_language", sa.String(length=30), nullable=True),
        sa.Column("raw_transcript", sa.Text(), nullable=True),
        sa.Column("edited_transcript", sa.Text(), nullable=True),
        sa.Column("provider", sa.String(length=50), nullable=False),
        sa.Column("model", sa.String(length=100), nullable=False),
        sa.Column("error_code", sa.String(length=50), nullable=True),
        sa.Column("safe_error_message", sa.String(length=500), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("record_id", sa.Integer(), nullable=True, unique=True),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(
            ["original_audio_media_id"], ["media_files.id"], ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(
            ["normalized_audio_media_id"], ["media_files.id"], ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(["record_id"], ["site_records.id"], ondelete="SET NULL"),
    )
    op.create_index("ix_transcription_jobs_project_id", "transcription_jobs", ["project_id"])
    op.create_index("ix_transcription_jobs_status", "transcription_jobs", ["status"])

    with op.batch_alter_table("media_files", naming_convention=naming) as batch:
        batch.create_foreign_key(
            "fk_media_files_transcription_job_id",
            "transcription_jobs",
            ["transcription_job_id"],
            ["id"],
            ondelete="CASCADE",
        )
        batch.create_index("ix_media_files_transcription_job_id", ["transcription_job_id"])

    op.create_table(
        "event_drafts",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("transcription_job_id", sa.String(length=36), nullable=False),
        sa.Column("project_id", sa.Integer(), nullable=False),
        sa.Column("created_by", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("raw_payload", sa.Text(), nullable=True),
        sa.Column("user_corrected_payload", sa.Text(), nullable=True),
        sa.Column("schema_version", sa.String(length=20), nullable=False),
        sa.Column("provider", sa.String(length=50), nullable=False),
        sa.Column("model", sa.String(length=100), nullable=False),
        sa.Column("prompt_version", sa.String(length=30), nullable=False),
        sa.Column("safe_error_message", sa.String(length=500), nullable=True),
        sa.Column("confirmed_record_id", sa.Integer(), nullable=True, unique=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("confirmed_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["transcription_job_id"], ["transcription_jobs.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["confirmed_record_id"], ["site_records.id"], ondelete="SET NULL"),
    )
    op.create_index(
        "ix_event_drafts_transcription_job_id", "event_drafts", ["transcription_job_id"]
    )
    op.create_index("ix_event_drafts_project_id", "event_drafts", ["project_id"])
    op.create_index("ix_event_drafts_status", "event_drafts", ["status"])


def downgrade() -> None:
    naming = {"fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s"}
    op.drop_table("event_drafts")
    with op.batch_alter_table("media_files", naming_convention=naming) as batch:
        batch.drop_index("ix_media_files_transcription_job_id")
        batch.drop_constraint("fk_media_files_transcription_job_id", type_="foreignkey")
    op.drop_table("transcription_jobs")
    with op.batch_alter_table("media_files", naming_convention=naming) as batch:
        batch.drop_constraint("fk_media_files_site_record_id", type_="foreignkey")
        batch.create_foreign_key(
            "fk_media_files_site_record_id_site_records",
            "site_records",
            ["site_record_id"],
            ["id"],
            ondelete="CASCADE",
        )
        batch.alter_column("site_record_id", existing_type=sa.Integer(), nullable=False)
        batch.drop_constraint("fk_media_files_created_by", type_="foreignkey")
        batch.drop_constraint("fk_media_files_project_id", type_="foreignkey")
        batch.drop_column("transcription_job_id")
        batch.drop_column("created_by")
        batch.drop_column("project_id")
    op.drop_column("site_records", "event_schema_version")
    op.drop_column("site_records", "structured_event")
    op.drop_column("site_records", "source_type")
    op.drop_column("projects", "timezone")
