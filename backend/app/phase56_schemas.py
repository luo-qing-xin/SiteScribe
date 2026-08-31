from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class KnowledgeDocumentOut(ORMModel):
    id: str
    project_id: int
    uploaded_by: int
    title: str
    original_name: str
    mime_type: str
    size_bytes: int
    sha256: str
    status: str
    is_demo: bool
    error_message: str | None
    archived_by: int | None
    archived_at: datetime | None
    created_at: datetime
    chunk_count: int = 0
    notice: str | None = None


class Citation(BaseModel):
    chunk_id: int
    document_id: str
    document_title: str
    locator: str
    excerpt: str
    is_demo: bool = False


class RagResult(BaseModel):
    suspected_impact: str
    recommendations: list[str]
    confidence: float = Field(ge=0, le=1)
    warnings: list[str] = []
    citations: list[Citation]


class RagJobOut(ORMModel):
    id: str
    issue_id: str
    project_id: int
    status: str
    provider: str
    model: str
    query: str
    retrieved: list[dict[str, Any]]
    result: RagResult | None
    error_message: str | None
    retry_of_job_id: str | None
    created_at: datetime
    completed_at: datetime | None


class IssueOut(ORMModel):
    id: str
    project_id: int
    event_id: str
    record_id: int
    issue_index: int
    category: str
    description: str
    location: dict[str, Any]
    evidence: list[dict[str, Any]]
    occurred_at: datetime
    status: str
    ignored_reason: str | None
    task_id: int | None = None
    latest_rag_job: RagJobOut | None = None
    created_at: datetime


class IgnoreIssueIn(BaseModel):
    reason: str = Field(min_length=1, max_length=2000)


class ConfirmIssueIn(BaseModel):
    final_description: str = Field(min_length=1, max_length=5000)
    rectification_measure: str = Field(min_length=1, max_length=5000)
    assignee_id: int
    due_at: datetime
    rag_job_id: str

    @field_validator("due_at")
    @classmethod
    def require_timezone(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("截止时间必须包含时区")
        return value


class ReviewIn(BaseModel):
    decision: Literal["APPROVE", "REJECT"]
    reason: str | None = Field(None, max_length=2000)


class CancelIn(BaseModel):
    reason: str = Field(min_length=1, max_length=2000)


class RectificationSubmissionOut(BaseModel):
    id: str
    round_number: int
    submitted_by: int
    note: str
    created_at: datetime
    photos: list[dict[str, Any]]
    review: dict[str, Any] | None


class TaskDetailOut(BaseModel):
    id: int
    project_id: int
    source_record_id: int | None
    source_issue_id: str | None
    kind: str
    creator_id: int
    assignee_id: int
    title: str
    description: str
    due_at: datetime
    status: str
    created_at: datetime
    updated_at: datetime
    submissions: list[RectificationSubmissionOut]
    audits: list[dict[str, Any]]


class ReminderOut(BaseModel):
    yesterday_unclosed: list[int]
    overdue: list[int]
    waiting_review: list[int]

    @property
    def counts(self) -> dict[str, int]:
        return {
            "yesterday_unclosed": len(self.yesterday_unclosed),
            "overdue": len(self.overdue),
            "waiting_review": len(self.waiting_review),
        }
