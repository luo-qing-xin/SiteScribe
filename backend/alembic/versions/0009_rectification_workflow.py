"""Add rectification task workflow and immutable evidence rounds."""

import sqlalchemy as sa

from alembic import op

revision = "0009_rectification_workflow"
down_revision = "0008_issue_knowledge_rag"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("tasks") as batch:
        batch.add_column(sa.Column("source_issue_id", sa.String(36), nullable=True))
        batch.add_column(sa.Column("kind", sa.String(20), nullable=False, server_default="GENERAL"))
        batch.create_foreign_key(
            "fk_tasks_source_issue", "issues", ["source_issue_id"], ["id"], ondelete="RESTRICT"
        )
        batch.create_unique_constraint("uq_tasks_source_issue_id", ["source_issue_id"])
        batch.create_index("ix_tasks_source_issue_id", ["source_issue_id"])
        batch.create_index("ix_tasks_kind", ["kind"])
        batch.create_index("ix_tasks_status", ["status"])
    op.execute("UPDATE tasks SET status='OPEN' WHERE status='待处理'")
    op.execute("UPDATE tasks SET status='IN_PROGRESS' WHERE status='处理中'")
    op.execute("UPDATE tasks SET status='DONE' WHERE status='已完成'")
    op.execute("UPDATE tasks SET status='CANCELLED' WHERE status='已取消'")

    op.create_table(
        "rectification_submissions",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("task_id", sa.Integer(), nullable=False),
        sa.Column("project_id", sa.Integer(), nullable=False),
        sa.Column("round_number", sa.Integer(), nullable=False),
        sa.Column("submitted_by", sa.Integer(), nullable=False),
        sa.Column("note", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["task_id"], ["tasks.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["submitted_by"], ["users.id"], ondelete="RESTRICT"),
        sa.UniqueConstraint("task_id", "round_number"),
    )
    op.create_index(
        "ix_rectification_submissions_task_id", "rectification_submissions", ["task_id"]
    )
    op.create_index(
        "ix_rectification_submissions_project_id", "rectification_submissions", ["project_id"]
    )

    op.create_table(
        "task_reviews",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("task_id", sa.Integer(), nullable=False),
        sa.Column("submission_id", sa.String(36), nullable=False, unique=True),
        sa.Column("project_id", sa.Integer(), nullable=False),
        sa.Column("reviewer_id", sa.Integer(), nullable=False),
        sa.Column("decision", sa.String(20), nullable=False),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["task_id"], ["tasks.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(
            ["submission_id"], ["rectification_submissions.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["reviewer_id"], ["users.id"], ondelete="RESTRICT"),
    )
    op.create_index("ix_task_reviews_task_id", "task_reviews", ["task_id"])
    op.create_index("ix_task_reviews_project_id", "task_reviews", ["project_id"])

    op.create_table(
        "task_audits",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("task_id", sa.Integer(), nullable=False),
        sa.Column("project_id", sa.Integer(), nullable=False),
        sa.Column("actor_id", sa.Integer(), nullable=False),
        sa.Column("action", sa.String(40), nullable=False),
        sa.Column("payload", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["task_id"], ["tasks.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["actor_id"], ["users.id"], ondelete="RESTRICT"),
    )
    op.create_index("ix_task_audits_task_id", "task_audits", ["task_id"])
    op.create_index("ix_task_audits_project_id", "task_audits", ["project_id"])

    with op.batch_alter_table("media_files") as batch:
        batch.add_column(sa.Column("task_id", sa.Integer(), nullable=True))
        batch.add_column(sa.Column("rectification_submission_id", sa.String(36), nullable=True))
        batch.create_foreign_key("fk_media_task", "tasks", ["task_id"], ["id"], ondelete="RESTRICT")
        batch.create_foreign_key(
            "fk_media_submission",
            "rectification_submissions",
            ["rectification_submission_id"],
            ["id"],
            ondelete="RESTRICT",
        )
        batch.create_index("ix_media_files_task_id", ["task_id"])
        batch.create_index(
            "ix_media_files_rectification_submission_id", ["rectification_submission_id"]
        )


def downgrade() -> None:
    with op.batch_alter_table("media_files") as batch:
        batch.drop_index("ix_media_files_rectification_submission_id")
        batch.drop_index("ix_media_files_task_id")
        batch.drop_constraint("fk_media_submission", type_="foreignkey")
        batch.drop_constraint("fk_media_task", type_="foreignkey")
        batch.drop_column("rectification_submission_id")
        batch.drop_column("task_id")
    for table, indexes in (
        ("task_audits", ["project_id", "task_id"]),
        ("task_reviews", ["project_id", "task_id"]),
        ("rectification_submissions", ["project_id", "task_id"]),
    ):
        for index in indexes:
            op.drop_index(f"ix_{table}_{index}", table_name=table)
        op.drop_table(table)
    with op.batch_alter_table("tasks") as batch:
        batch.drop_index("ix_tasks_status")
        batch.drop_index("ix_tasks_kind")
        batch.drop_index("ix_tasks_source_issue_id")
        batch.drop_constraint("uq_tasks_source_issue_id", type_="unique")
        batch.drop_constraint("fk_tasks_source_issue", type_="foreignkey")
        batch.drop_column("kind")
        batch.drop_column("source_issue_id")
