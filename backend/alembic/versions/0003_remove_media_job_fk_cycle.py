"""Remove the media-to-job FK cycle; ownership is enforced by services."""

from alembic import op

revision = "0003_remove_media_job_fk_cycle"
down_revision = "0002_voice_ai_pipeline"
branch_labels = None
depends_on = None


def upgrade() -> None:
    naming = {"fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s"}
    with op.batch_alter_table("media_files", naming_convention=naming) as batch:
        batch.drop_constraint("fk_media_files_transcription_job_id", type_="foreignkey")


def downgrade() -> None:
    naming = {"fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s"}
    with op.batch_alter_table("media_files", naming_convention=naming) as batch:
        batch.create_foreign_key(
            "fk_media_files_transcription_job_id",
            "transcription_jobs",
            ["transcription_job_id"],
            ["id"],
            ondelete="CASCADE",
        )
