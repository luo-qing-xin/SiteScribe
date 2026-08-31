"""Add evidence-first issues and project knowledge RAG."""

import json
from datetime import UTC, datetime
from uuid import uuid4

import sqlalchemy as sa

from alembic import op

revision = "0008_issue_knowledge_rag"
down_revision = "0007_daily_logs"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "issues",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("project_id", sa.Integer(), nullable=False),
        sa.Column("event_id", sa.String(36), nullable=False),
        sa.Column("record_id", sa.Integer(), nullable=False),
        sa.Column("issue_index", sa.Integer(), nullable=False),
        sa.Column("category", sa.String(30), nullable=False),
        sa.Column("description_snapshot", sa.Text(), nullable=False),
        sa.Column("location_snapshot", sa.Text(), nullable=False),
        sa.Column("evidence_snapshot", sa.Text(), nullable=False),
        sa.Column("event_snapshot", sa.Text(), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("status", sa.String(30), nullable=False),
        sa.Column("ignored_reason", sa.Text(), nullable=True),
        sa.Column("ignored_by", sa.Integer(), nullable=True),
        sa.Column("ignored_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["event_id"], ["site_events.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["record_id"], ["site_records.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["ignored_by"], ["users.id"], ondelete="RESTRICT"),
        sa.UniqueConstraint("event_id", "issue_index"),
    )
    for name in ("project_id", "event_id", "record_id", "category", "occurred_at", "status"):
        op.create_index(f"ix_issues_{name}", "issues", [name])

    op.create_table(
        "knowledge_documents",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("project_id", sa.Integer(), nullable=False),
        sa.Column("uploaded_by", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("original_name", sa.String(255), nullable=False),
        sa.Column("stored_name", sa.String(100), nullable=False, unique=True),
        sa.Column("relative_path", sa.String(255), nullable=False),
        sa.Column("mime_type", sa.String(100), nullable=False),
        sa.Column("size_bytes", sa.Integer(), nullable=False),
        sa.Column("sha256", sa.String(64), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("is_demo", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("error_message", sa.String(500), nullable=True),
        sa.Column("archived_by", sa.Integer(), nullable=True),
        sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["uploaded_by"], ["users.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["archived_by"], ["users.id"], ondelete="RESTRICT"),
        sa.UniqueConstraint("project_id", "sha256"),
    )
    op.create_index("ix_knowledge_documents_project_id", "knowledge_documents", ["project_id"])
    op.create_index("ix_knowledge_documents_status", "knowledge_documents", ["status"])

    op.create_table(
        "knowledge_chunks",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("document_id", sa.String(36), nullable=False),
        sa.Column("project_id", sa.Integer(), nullable=False),
        sa.Column("chunk_index", sa.Integer(), nullable=False),
        sa.Column("heading", sa.String(500), nullable=True),
        sa.Column("locator", sa.String(500), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("normalized_content", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["document_id"], ["knowledge_documents.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="RESTRICT"),
        sa.UniqueConstraint("document_id", "chunk_index"),
    )
    op.create_index("ix_knowledge_chunks_document_id", "knowledge_chunks", ["document_id"])
    op.create_index("ix_knowledge_chunks_project_id", "knowledge_chunks", ["project_id"])

    op.create_table(
        "rag_analysis_jobs",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("issue_id", sa.String(36), nullable=False),
        sa.Column("project_id", sa.Integer(), nullable=False),
        sa.Column("requested_by", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("provider", sa.String(50), nullable=False),
        sa.Column("model", sa.String(100), nullable=False),
        sa.Column("query_snapshot", sa.Text(), nullable=False),
        sa.Column("retrieved_snapshot", sa.Text(), nullable=False),
        sa.Column("raw_result", sa.Text(), nullable=True),
        sa.Column("validated_result", sa.Text(), nullable=True),
        sa.Column("error_message", sa.String(500), nullable=True),
        sa.Column("retry_of_job_id", sa.String(36), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["issue_id"], ["issues.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["requested_by"], ["users.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["retry_of_job_id"], ["rag_analysis_jobs.id"], ondelete="SET NULL"),
    )
    for name in ("issue_id", "project_id", "status"):
        op.create_index(f"ix_rag_analysis_jobs_{name}", "rag_analysis_jobs", [name])

    op.create_table(
        "issue_audits",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("issue_id", sa.String(36), nullable=False),
        sa.Column("project_id", sa.Integer(), nullable=False),
        sa.Column("actor_id", sa.Integer(), nullable=False),
        sa.Column("action", sa.String(40), nullable=False),
        sa.Column("payload", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["issue_id"], ["issues.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["actor_id"], ["users.id"], ondelete="RESTRICT"),
    )
    op.create_index("ix_issue_audits_issue_id", "issue_audits", ["issue_id"])
    op.create_index("ix_issue_audits_project_id", "issue_audits", ["project_id"])
    _backfill_issues()


def _backfill_issues() -> None:
    bind = op.get_bind()
    rows = bind.execute(
        sa.text("""
        SELECT e.id, e.project_id, e.source_record_id, e.confirmed_data, e.evidence_map,
               r.occurred_at, l.building, l.floor, l.zone
        FROM site_events e JOIN site_records r ON r.id=e.source_record_id
        JOIN project_locations l ON l.id=r.location_id WHERE e.status='CONFIRMED'
    """)
    ).mappings()
    now = datetime.now(UTC)
    for row in rows:
        try:
            payload = json.loads(row["confirmed_data"] or "{}")
        except json.JSONDecodeError:
            continue
        for index, issue in enumerate(payload.get("issues", [])):
            if issue.get("category") not in {"安全", "文明施工/安全"}:
                continue
            bind.execute(
                sa.text("""
                INSERT INTO issues
                (id, project_id, event_id, record_id, issue_index, category,
                 description_snapshot, location_snapshot, evidence_snapshot, event_snapshot,
                 occurred_at, status, created_at, updated_at)
                VALUES (:id,:project_id,:event_id,:record_id,:issue_index,:category,
                 :description,:location,:evidence,:event_snapshot,:occurred_at,
                 'PENDING_ANALYSIS',:created_at,:updated_at)
            """),
                {
                    "id": str(uuid4()),
                    "project_id": row["project_id"],
                    "event_id": row["id"],
                    "record_id": row["source_record_id"],
                    "issue_index": index,
                    "category": issue["category"],
                    "description": issue.get("description", ""),
                    "location": json.dumps(
                        {"building": row["building"], "floor": row["floor"], "zone": row["zone"]},
                        ensure_ascii=False,
                    ),
                    "evidence": json.dumps(issue.get("evidence", []), ensure_ascii=False),
                    "event_snapshot": row["confirmed_data"],
                    "occurred_at": row["occurred_at"],
                    "created_at": now,
                    "updated_at": now,
                },
            )


def downgrade() -> None:
    for table, indexes in (
        ("issue_audits", ["project_id", "issue_id"]),
        ("rag_analysis_jobs", ["status", "project_id", "issue_id"]),
        ("knowledge_chunks", ["project_id", "document_id"]),
        ("knowledge_documents", ["status", "project_id"]),
        ("issues", ["status", "occurred_at", "category", "record_id", "event_id", "project_id"]),
    ):
        for index in indexes:
            op.drop_index(f"ix_{table}_{index}", table_name=table)
        op.drop_table(table)
