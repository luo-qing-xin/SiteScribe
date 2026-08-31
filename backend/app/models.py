from datetime import UTC, date, datetime

from sqlalchemy import Date, DateTime, Float, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .db import Base


def utcnow() -> datetime:
    return datetime.now(UTC)


class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(String(50), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    name: Mapped[str] = mapped_column(String(50))
    role: Mapped[str] = mapped_column(String(30))
    organization: Mapped[str] = mapped_column(String(100))
    department: Mapped[str | None] = mapped_column(String(50))
    crew: Mapped[str | None] = mapped_column(String(50))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Project(Base):
    __tablename__ = "projects"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100), unique=True)
    organization: Mapped[str] = mapped_column(String(100))
    address: Mapped[str] = mapped_column(String(200))
    status: Mapped[str] = mapped_column(String(30))
    timezone: Mapped[str] = mapped_column(String(64), default="Asia/Shanghai")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class ProjectMember(Base):
    __tablename__ = "project_members"
    __table_args__ = (UniqueConstraint("project_id", "user_id"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id", ondelete="RESTRICT"))
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    user: Mapped[User] = relationship()


class ProjectLocation(Base):
    __tablename__ = "project_locations"
    __table_args__ = (UniqueConstraint("project_id", "building", "floor", "zone"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"))
    building: Mapped[str] = mapped_column(String(30))
    floor: Mapped[str] = mapped_column(String(30))
    zone: Mapped[str] = mapped_column(String(30))


class SiteRecord(Base):
    __tablename__ = "site_records"
    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id", ondelete="RESTRICT"))
    recorder_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    category: Mapped[str] = mapped_column(String(30))
    description: Mapped[str] = mapped_column(Text)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    latitude: Mapped[float | None] = mapped_column(Float)
    longitude: Mapped[float | None] = mapped_column(Float)
    gps_accuracy: Mapped[float | None] = mapped_column(Float)
    gps_captured_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    gps_status: Mapped[str] = mapped_column(String(30), default="not_requested")
    location_id: Mapped[int] = mapped_column(
        ForeignKey("project_locations.id", ondelete="RESTRICT")
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )
    source_type: Mapped[str] = mapped_column(String(20), default="MANUAL")
    structured_event: Mapped[str | None] = mapped_column(Text)
    event_schema_version: Mapped[str | None] = mapped_column(String(20))
    source_transcription_job_id: Mapped[str | None] = mapped_column(
        String(36), unique=True, index=True
    )
    recorder: Mapped[User] = relationship()
    project: Mapped[Project] = relationship()
    location: Mapped[ProjectLocation] = relationship()
    photos: Mapped[list["MediaFile"]] = relationship(
        primaryjoin="and_(SiteRecord.id == MediaFile.site_record_id, MediaFile.media_type == 'image')",
        viewonly=True,
    )


class MediaFile(Base):
    __tablename__ = "media_files"
    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id", ondelete="RESTRICT"))
    created_by: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    site_record_id: Mapped[int | None] = mapped_column(
        ForeignKey("site_records.id", ondelete="SET NULL")
    )
    transcription_job_id: Mapped[str | None] = mapped_column(String(36), index=True)
    task_id: Mapped[int | None] = mapped_column(
        ForeignKey("tasks.id", ondelete="RESTRICT"), index=True
    )
    rectification_submission_id: Mapped[str | None] = mapped_column(
        ForeignKey("rectification_submissions.id", ondelete="RESTRICT"), index=True
    )
    media_type: Mapped[str] = mapped_column(String(20), default="image")
    original_name: Mapped[str] = mapped_column(String(255))
    stored_name: Mapped[str] = mapped_column(String(100), unique=True)
    relative_path: Mapped[str] = mapped_column(String(255))
    mime_type: Mapped[str] = mapped_column(String(50))
    size_bytes: Mapped[int]
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    @property
    def content_url(self) -> str:
        return f"/api/media/{self.id}/content"


class TranscriptionJob(Base):
    __tablename__ = "transcription_jobs"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    project_id: Mapped[int] = mapped_column(
        ForeignKey("projects.id", ondelete="RESTRICT"), index=True
    )
    created_by: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    original_audio_media_id: Mapped[int | None] = mapped_column(
        ForeignKey("media_files.id", ondelete="SET NULL"), unique=True
    )
    normalized_audio_media_id: Mapped[int | None] = mapped_column(
        ForeignKey("media_files.id", ondelete="SET NULL"), unique=True
    )
    status: Mapped[str] = mapped_column(String(20), default="QUEUED", index=True)
    detected_language: Mapped[str | None] = mapped_column(String(30))
    raw_transcript: Mapped[str | None] = mapped_column(Text)
    edited_transcript: Mapped[str | None] = mapped_column(Text)
    provider: Mapped[str] = mapped_column(String(50))
    model: Mapped[str] = mapped_column(String(100))
    error_code: Mapped[str | None] = mapped_column(String(50))
    safe_error_message: Mapped[str | None] = mapped_column(String(500))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    record_id: Mapped[int | None] = mapped_column(
        ForeignKey("site_records.id", ondelete="SET NULL"), unique=True
    )
    creator: Mapped[User] = relationship(foreign_keys=[created_by])
    original_audio: Mapped[MediaFile | None] = relationship(
        foreign_keys=[original_audio_media_id], post_update=True
    )
    normalized_audio: Mapped[MediaFile | None] = relationship(
        foreign_keys=[normalized_audio_media_id], post_update=True
    )


class EventDraft(Base):
    __tablename__ = "event_drafts"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    transcription_job_id: Mapped[str] = mapped_column(
        ForeignKey("transcription_jobs.id", ondelete="CASCADE"), index=True
    )
    project_id: Mapped[int] = mapped_column(
        ForeignKey("projects.id", ondelete="RESTRICT"), index=True
    )
    created_by: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    status: Mapped[str] = mapped_column(String(20), default="GENERATING", index=True)
    raw_payload: Mapped[str | None] = mapped_column(Text)
    system_resolved_payload: Mapped[str | None] = mapped_column(Text)
    user_corrected_payload: Mapped[str | None] = mapped_column(Text)
    schema_version: Mapped[str] = mapped_column(String(20), default="1.0")
    provider: Mapped[str] = mapped_column(String(50))
    model: Mapped[str] = mapped_column(String(100))
    prompt_version: Mapped[str] = mapped_column(String(30), default="1.0")
    safe_error_message: Mapped[str | None] = mapped_column(String(500))
    confirmed_record_id: Mapped[int | None] = mapped_column(
        ForeignKey("site_records.id", ondelete="SET NULL"), unique=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class EventExtractionJob(Base):
    __tablename__ = "event_extraction_jobs"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    project_id: Mapped[int] = mapped_column(
        ForeignKey("projects.id", ondelete="RESTRICT"), index=True
    )
    record_id: Mapped[int] = mapped_column(
        ForeignKey("site_records.id", ondelete="CASCADE"), index=True
    )
    requested_by: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    status: Mapped[str] = mapped_column(String(20), default="QUEUED", index=True)
    provider: Mapped[str] = mapped_column(String(50))
    model: Mapped[str] = mapped_column(String(100))
    schema_version: Mapped[str] = mapped_column(String(20), default="1.0")
    input_snapshot: Mapped[str] = mapped_column(Text)
    response_metadata: Mapped[str | None] = mapped_column(Text)
    result_event_id: Mapped[str | None] = mapped_column(String(36), index=True)
    retry_of_job_id: Mapped[str | None] = mapped_column(
        ForeignKey("event_extraction_jobs.id", ondelete="SET NULL")
    )
    error_code: Mapped[str | None] = mapped_column(String(50))
    error_message: Mapped[str | None] = mapped_column(String(500))
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )


class SiteEvent(Base):
    __tablename__ = "site_events"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    project_id: Mapped[int] = mapped_column(
        ForeignKey("projects.id", ondelete="RESTRICT"), index=True
    )
    source_record_id: Mapped[int] = mapped_column(
        ForeignKey("site_records.id", ondelete="CASCADE"), index=True
    )
    extraction_job_id: Mapped[str] = mapped_column(
        ForeignKey("event_extraction_jobs.id", ondelete="RESTRICT"), unique=True
    )
    status: Mapped[str] = mapped_column(String(20), default="DRAFT", index=True)
    schema_version: Mapped[str] = mapped_column(String(20), default="1.0")
    event_type: Mapped[str] = mapped_column(String(30), default="site_inspection")
    ai_output: Mapped[str] = mapped_column(Text)
    draft_data: Mapped[str] = mapped_column(Text)
    confirmed_data: Mapped[str | None] = mapped_column(Text)
    evidence_map: Mapped[str] = mapped_column(Text)
    overall_confidence: Mapped[float] = mapped_column(Float)
    confirmed_by: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    rejected_by: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    rejected_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    rejection_reason: Mapped[str | None] = mapped_column(String(500))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )


class EventRevision(Base):
    __tablename__ = "event_revisions"
    id: Mapped[int] = mapped_column(primary_key=True)
    event_id: Mapped[str] = mapped_column(
        ForeignKey("site_events.id", ondelete="CASCADE"), index=True
    )
    project_id: Mapped[int] = mapped_column(
        ForeignKey("projects.id", ondelete="RESTRICT"), index=True
    )
    actor_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    action: Mapped[str] = mapped_column(String(30))
    before_data: Mapped[str | None] = mapped_column(Text)
    after_data: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class DailyLogDocument(Base):
    __tablename__ = "daily_log_documents"
    __table_args__ = (UniqueConstraint("project_id", "log_date", "log_type"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int] = mapped_column(
        ForeignKey("projects.id", ondelete="RESTRICT"), index=True
    )
    log_date: Mapped[date] = mapped_column(Date, index=True)
    log_type: Mapped[str] = mapped_column(String(30), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class DailyLogVersion(Base):
    __tablename__ = "daily_log_versions"
    __table_args__ = (UniqueConstraint("document_id", "version"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    document_id: Mapped[int] = mapped_column(
        ForeignKey("daily_log_documents.id", ondelete="CASCADE"), index=True
    )
    project_id: Mapped[int] = mapped_column(
        ForeignKey("projects.id", ondelete="RESTRICT"), index=True
    )
    version: Mapped[int]
    status: Mapped[str] = mapped_column(String(20), default="DRAFT", index=True)
    auto_content: Mapped[str] = mapped_column(Text)
    manual_content: Mapped[str] = mapped_column(Text)
    source_digest: Mapped[str] = mapped_column(String(64))
    created_by: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    updated_by: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    confirmed_by: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )


class DailyLogSource(Base):
    __tablename__ = "daily_log_sources"
    __table_args__ = (UniqueConstraint("version_id", "event_id"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    version_id: Mapped[str] = mapped_column(
        ForeignKey("daily_log_versions.id", ondelete="CASCADE"), index=True
    )
    project_id: Mapped[int] = mapped_column(
        ForeignKey("projects.id", ondelete="RESTRICT"), index=True
    )
    event_id: Mapped[str] = mapped_column(
        ForeignKey("site_events.id", ondelete="RESTRICT"), index=True
    )
    record_id: Mapped[int] = mapped_column(
        ForeignKey("site_records.id", ondelete="RESTRICT"), index=True
    )
    event_snapshot: Mapped[str] = mapped_column(Text)
    evidence_snapshot: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class DailyLogAudit(Base):
    __tablename__ = "daily_log_audits"
    id: Mapped[int] = mapped_column(primary_key=True)
    version_id: Mapped[str] = mapped_column(
        ForeignKey("daily_log_versions.id", ondelete="CASCADE"), index=True
    )
    project_id: Mapped[int] = mapped_column(
        ForeignKey("projects.id", ondelete="RESTRICT"), index=True
    )
    actor_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    action: Mapped[str] = mapped_column(String(30))
    before_data: Mapped[str | None] = mapped_column(Text)
    after_data: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Task(Base):
    __tablename__ = "tasks"
    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id", ondelete="RESTRICT"))
    source_record_id: Mapped[int | None] = mapped_column(
        ForeignKey("site_records.id", ondelete="SET NULL")
    )
    source_issue_id: Mapped[str | None] = mapped_column(
        ForeignKey("issues.id", ondelete="RESTRICT"), unique=True, index=True
    )
    kind: Mapped[str] = mapped_column(String(20), default="GENERAL", index=True)
    creator_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    assignee_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    title: Mapped[str] = mapped_column(String(120))
    description: Mapped[str] = mapped_column(Text)
    due_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(String(20), default="OPEN", index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )
    creator: Mapped[User] = relationship(foreign_keys=[creator_id])
    assignee: Mapped[User] = relationship(foreign_keys=[assignee_id])


class Issue(Base):
    __tablename__ = "issues"
    __table_args__ = (UniqueConstraint("event_id", "issue_index"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    project_id: Mapped[int] = mapped_column(
        ForeignKey("projects.id", ondelete="RESTRICT"), index=True
    )
    event_id: Mapped[str] = mapped_column(
        ForeignKey("site_events.id", ondelete="RESTRICT"), index=True
    )
    record_id: Mapped[int] = mapped_column(
        ForeignKey("site_records.id", ondelete="RESTRICT"), index=True
    )
    issue_index: Mapped[int]
    category: Mapped[str] = mapped_column(String(30), index=True)
    description_snapshot: Mapped[str] = mapped_column(Text)
    location_snapshot: Mapped[str] = mapped_column(Text)
    evidence_snapshot: Mapped[str] = mapped_column(Text)
    event_snapshot: Mapped[str] = mapped_column(Text)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    status: Mapped[str] = mapped_column(String(30), default="PENDING_ANALYSIS", index=True)
    ignored_reason: Mapped[str | None] = mapped_column(Text)
    ignored_by: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    ignored_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )


class KnowledgeDocument(Base):
    __tablename__ = "knowledge_documents"
    __table_args__ = (UniqueConstraint("project_id", "sha256"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    project_id: Mapped[int] = mapped_column(
        ForeignKey("projects.id", ondelete="RESTRICT"), index=True
    )
    uploaded_by: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    title: Mapped[str] = mapped_column(String(255))
    original_name: Mapped[str] = mapped_column(String(255))
    stored_name: Mapped[str] = mapped_column(String(100), unique=True)
    relative_path: Mapped[str] = mapped_column(String(255))
    mime_type: Mapped[str] = mapped_column(String(100))
    size_bytes: Mapped[int]
    sha256: Mapped[str] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(String(20), default="PROCESSING", index=True)
    is_demo: Mapped[bool] = mapped_column(default=False)
    error_message: Mapped[str | None] = mapped_column(String(500))
    archived_by: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )


class KnowledgeChunk(Base):
    __tablename__ = "knowledge_chunks"
    __table_args__ = (UniqueConstraint("document_id", "chunk_index"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    document_id: Mapped[str] = mapped_column(
        ForeignKey("knowledge_documents.id", ondelete="CASCADE"), index=True
    )
    project_id: Mapped[int] = mapped_column(
        ForeignKey("projects.id", ondelete="RESTRICT"), index=True
    )
    chunk_index: Mapped[int]
    heading: Mapped[str | None] = mapped_column(String(500))
    locator: Mapped[str] = mapped_column(String(500))
    content: Mapped[str] = mapped_column(Text)
    normalized_content: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class RagAnalysisJob(Base):
    __tablename__ = "rag_analysis_jobs"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    issue_id: Mapped[str] = mapped_column(ForeignKey("issues.id", ondelete="RESTRICT"), index=True)
    project_id: Mapped[int] = mapped_column(
        ForeignKey("projects.id", ondelete="RESTRICT"), index=True
    )
    requested_by: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    status: Mapped[str] = mapped_column(String(20), default="RUNNING", index=True)
    provider: Mapped[str] = mapped_column(String(50))
    model: Mapped[str] = mapped_column(String(100))
    query_snapshot: Mapped[str] = mapped_column(Text)
    retrieved_snapshot: Mapped[str] = mapped_column(Text)
    raw_result: Mapped[str | None] = mapped_column(Text)
    validated_result: Mapped[str | None] = mapped_column(Text)
    error_message: Mapped[str | None] = mapped_column(String(500))
    retry_of_job_id: Mapped[str | None] = mapped_column(
        ForeignKey("rag_analysis_jobs.id", ondelete="SET NULL")
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class IssueAudit(Base):
    __tablename__ = "issue_audits"
    id: Mapped[int] = mapped_column(primary_key=True)
    issue_id: Mapped[str] = mapped_column(ForeignKey("issues.id", ondelete="RESTRICT"), index=True)
    project_id: Mapped[int] = mapped_column(
        ForeignKey("projects.id", ondelete="RESTRICT"), index=True
    )
    actor_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    action: Mapped[str] = mapped_column(String(40))
    payload: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class RectificationSubmission(Base):
    __tablename__ = "rectification_submissions"
    __table_args__ = (UniqueConstraint("task_id", "round_number"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    task_id: Mapped[int] = mapped_column(ForeignKey("tasks.id", ondelete="RESTRICT"), index=True)
    project_id: Mapped[int] = mapped_column(
        ForeignKey("projects.id", ondelete="RESTRICT"), index=True
    )
    round_number: Mapped[int]
    submitted_by: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    note: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class TaskReview(Base):
    __tablename__ = "task_reviews"
    id: Mapped[int] = mapped_column(primary_key=True)
    task_id: Mapped[int] = mapped_column(ForeignKey("tasks.id", ondelete="RESTRICT"), index=True)
    submission_id: Mapped[str] = mapped_column(
        ForeignKey("rectification_submissions.id", ondelete="RESTRICT"), unique=True
    )
    project_id: Mapped[int] = mapped_column(
        ForeignKey("projects.id", ondelete="RESTRICT"), index=True
    )
    reviewer_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    decision: Mapped[str] = mapped_column(String(20))
    reason: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class TaskAudit(Base):
    __tablename__ = "task_audits"
    id: Mapped[int] = mapped_column(primary_key=True)
    task_id: Mapped[int] = mapped_column(ForeignKey("tasks.id", ondelete="RESTRICT"), index=True)
    project_id: Mapped[int] = mapped_column(
        ForeignKey("projects.id", ondelete="RESTRICT"), index=True
    )
    actor_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    action: Mapped[str] = mapped_column(String(40))
    payload: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
