from datetime import UTC, datetime
from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class RecordCategory(StrEnum):
    PROGRESS = "施工进度"
    SAFETY = "安全巡查"
    QUALITY = "质量检查"
    MATERIAL = "材料进场"
    WORK = "人员作业"
    OTHER = "其他"


class TaskStatus(StrEnum):
    OPEN = "OPEN"
    IN_PROGRESS = "IN_PROGRESS"
    WAITING_REVIEW = "WAITING_REVIEW"
    DONE = "DONE"
    CANCELLED = "CANCELLED"
    LEGACY_TODO = "待处理"
    LEGACY_DOING = "处理中"
    LEGACY_DONE = "已完成"
    LEGACY_CANCELLED = "已取消"


class GpsStatus(StrEnum):
    NOT_REQUESTED = "not_requested"
    SUCCESS = "success"
    UNSUPPORTED = "unsupported"
    DENIED = "denied"
    TIMEOUT = "timeout"
    FAILED = "failed"


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class UserOut(ORMModel):
    id: int
    username: str
    name: str
    role: str
    organization: str
    department: str | None
    crew: str | None


class LoginIn(BaseModel):
    username: str = Field(min_length=1, max_length=50)
    password: str = Field(min_length=1, max_length=100)


class ProjectOut(ORMModel):
    id: int
    name: str
    organization: str
    address: str
    status: str
    timezone: str


class LocationOut(ORMModel):
    id: int
    building: str
    floor: str
    zone: str


class PhotoOut(ORMModel):
    id: int
    original_name: str
    mime_type: str
    size_bytes: int
    created_at: datetime
    content_url: str


class MediaOut(PhotoOut):
    media_type: str


class RecordCreate(BaseModel):
    project_id: int
    category: RecordCategory
    description: str = Field(min_length=1, max_length=5000)
    occurred_at: datetime
    latitude: float | None = Field(None, ge=-90, le=90)
    longitude: float | None = Field(None, ge=-180, le=180)
    gps_accuracy: float | None = Field(None, ge=0)
    gps_captured_at: datetime | None = None
    gps_status: GpsStatus = GpsStatus.NOT_REQUESTED
    location_id: int

    @model_validator(mode="after")
    def validate_gps(self):
        values = (self.latitude, self.longitude, self.gps_accuracy, self.gps_captured_at)
        if self.gps_status == GpsStatus.SUCCESS and any(value is None for value in values):
            raise ValueError("定位成功时必须提供完整 GPS 信息")
        if self.gps_status != GpsStatus.SUCCESS and any(value is not None for value in values):
            raise ValueError("定位未成功时 GPS 坐标必须为空")
        return self


class RecordPatch(BaseModel):
    category: RecordCategory | None = None
    description: str | None = Field(None, min_length=1, max_length=5000)
    location_id: int | None = None


class RecordOut(ORMModel):
    id: int
    project_id: int
    category: str
    description: str
    occurred_at: datetime
    latitude: float | None
    longitude: float | None
    gps_accuracy: float | None
    gps_captured_at: datetime | None
    gps_status: str
    created_at: datetime
    updated_at: datetime
    recorder: UserOut
    project: ProjectOut
    location: LocationOut
    photos: list[PhotoOut] = []
    source_type: str
    structured_event: str | None
    event_schema_version: str | None


class TaskCreate(BaseModel):
    project_id: int
    source_record_id: int | None = None
    assignee_id: int
    title: str = Field(min_length=1, max_length=120)
    description: str = Field(min_length=1, max_length=5000)
    due_at: datetime
    status: TaskStatus = TaskStatus.OPEN

    @field_validator("due_at")
    @classmethod
    def normalize_due_at(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("截止时间必须包含时区")
        return value.astimezone(UTC)


class TaskPatch(BaseModel):
    assignee_id: int | None = None
    title: str | None = Field(None, min_length=1, max_length=120)
    description: str | None = Field(None, min_length=1, max_length=5000)
    due_at: datetime | None = None
    status: TaskStatus | None = None

    @field_validator("due_at")
    @classmethod
    def normalize_optional_due_at(cls, value: datetime | None) -> datetime | None:
        if value is None:
            return None
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("截止时间必须包含时区")
        return value.astimezone(UTC)


class TaskOut(ORMModel):
    id: int
    project_id: int
    source_record_id: int | None
    source_issue_id: str | None = None
    kind: str = "GENERAL"
    title: str
    description: str
    due_at: datetime
    status: str
    created_at: datetime
    updated_at: datetime
    creator: UserOut
    assignee: UserOut


class DashboardOut(BaseModel):
    today_records: int
    pending_tasks: int
    completed_tasks: int
    confirmed_events: int
    pending_issues: int
    waiting_review_rectifications: int
    closed_rectifications_today: int
    recent_records: list[RecordOut]
    upcoming_tasks: list[TaskOut]


class MessageOut(BaseModel):
    message: str


class TranscriptPatch(BaseModel):
    model_config = ConfigDict(extra="forbid")
    edited_transcript: str = Field(min_length=1, max_length=20_000)


class EvidenceRef(BaseModel):
    model_config = ConfigDict(extra="forbid")
    source_type: Literal["raw_transcript", "edited_transcript", "audio"]
    quote: str | None = Field(None, max_length=1000)


class ConstructionEvent(BaseModel):
    model_config = ConfigDict(extra="forbid")
    activity: str | None = Field(None, max_length=500)
    progress_percent: float | None = Field(None, ge=0, le=100)
    crew: str | None = Field(None, max_length=200)
    worker_count: int | None = Field(None, ge=0)


class EventIssue(BaseModel):
    model_config = ConfigDict(extra="forbid")
    description: str = Field(min_length=1, max_length=2000)
    category: Literal["safety", "quality", "civilized_construction", "other"]
    responsible_person_text: str | None = Field(None, max_length=200)
    candidate_project_member_id: int | None = None
    deadline_text: str | None = Field(None, max_length=200)
    proposed_deadline: datetime | None = None
    evidence_quote: str = Field(min_length=1, max_length=2000)
    needs_confirmation: bool = True


class EventPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")
    schema_version: Literal["1.0"] = "1.0"
    event_type: Literal[
        "construction_progress", "safety_inspection", "quality_inspection", "general"
    ] = "general"
    construction: ConstructionEvent = Field(default_factory=ConstructionEvent)
    issues: list[EventIssue] = Field(default_factory=list, max_length=50)
    notes: str | None = Field(None, max_length=5000)
    missing_fields: list[str] = Field(default_factory=list, max_length=100)
    warnings: list[str] = Field(default_factory=list, max_length=100)
    field_evidence: dict[str, list[EvidenceRef]] = Field(default_factory=dict)


class TranscriptionJobOut(ORMModel):
    id: str
    project_id: int
    original_audio_media_id: int | None
    normalized_audio_media_id: int | None
    status: str
    detected_language: str | None
    raw_transcript: str | None
    edited_transcript: str | None
    provider: str
    model: str
    error_code: str | None
    safe_error_message: str | None
    created_at: datetime
    started_at: datetime | None
    completed_at: datetime | None
    record_id: int | None
    original_audio: MediaOut | None = None


class EventDraftOut(BaseModel):
    id: str
    transcription_job_id: str
    project_id: int
    status: str
    raw_payload: EventPayload | None
    system_resolved_payload: EventPayload | None
    user_corrected_payload: EventPayload | None
    schema_version: str
    provider: str
    model: str
    prompt_version: str
    safe_error_message: str | None
    confirmed_record_id: int | None
    created_at: datetime
    updated_at: datetime
    confirmed_at: datetime | None


class EventDraftPatch(BaseModel):
    payload: EventPayload


class ConfirmIssue(BaseModel):
    issue_index: int = Field(ge=0)
    create_task: bool = False
    assignee_id: int | None = None
    due_at: datetime | None = None
    title: str | None = Field(None, min_length=1, max_length=120)


class VoiceRecordData(BaseModel):
    category: RecordCategory
    description: str = Field(min_length=1, max_length=5000)
    occurred_at: datetime
    latitude: float | None = Field(None, ge=-90, le=90)
    longitude: float | None = Field(None, ge=-180, le=180)
    gps_accuracy: float | None = Field(None, ge=0)
    gps_captured_at: datetime | None = None
    gps_status: GpsStatus = GpsStatus.NOT_REQUESTED
    location_id: int

    @model_validator(mode="after")
    def validate_gps(self):
        values = (self.latitude, self.longitude, self.gps_accuracy, self.gps_captured_at)
        if self.gps_status == GpsStatus.SUCCESS and any(value is None for value in values):
            raise ValueError("定位成功时必须提供完整 GPS 信息")
        if self.gps_status != GpsStatus.SUCCESS and any(value is not None for value in values):
            raise ValueError("定位未成功时 GPS 坐标必须为空")
        return self


class EventConfirmIn(BaseModel):
    payload: EventPayload
    record: VoiceRecordData
    issues: list[ConfirmIssue] = Field(default_factory=list)


class EventConfirmOut(BaseModel):
    record: RecordOut
    tasks: list[TaskOut]


class VoiceEvidenceOut(BaseModel):
    job: TranscriptionJobOut
    draft: EventDraftOut | None
