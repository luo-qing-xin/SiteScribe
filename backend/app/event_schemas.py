from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

EvidenceType = Literal["confirmed_transcript", "photo", "manual_location", "record_metadata"]


class EventEvidenceRef(BaseModel):
    model_config = ConfigDict(extra="forbid")

    evidence_type: EvidenceType
    source_id: str = Field(min_length=1, max_length=100)
    quote: str | None = Field(None, max_length=2000)
    description: str | None = Field(None, max_length=1000)
    media_file_id: int | None = Field(None, ge=1)
    confidence: float = Field(ge=0, le=1)

    @model_validator(mode="after")
    def validate_reference(self):
        if not self.quote and not self.description:
            raise ValueError("证据引用必须包含 quote 或 description")
        if self.evidence_type == "photo" and self.media_file_id is None:
            raise ValueError("图片证据必须包含 media_file_id")
        if self.evidence_type != "photo" and self.media_file_id is not None:
            raise ValueError("非图片证据不能包含 media_file_id")
        return self


class SiteConstruction(BaseModel):
    model_config = ConfigDict(extra="forbid")

    activity: str | None = Field(None, max_length=500)
    crew: str | None = Field(None, max_length=200)
    worker_count: int | None = Field(None, ge=0)
    progress: float | None = Field(None, ge=0, le=1)


class SiteEventIssue(BaseModel):
    model_config = ConfigDict(extra="forbid")

    description: str = Field(min_length=1, max_length=2000)
    category: Literal["文明施工/安全", "安全", "质量", "文明施工", "其他"]
    risk_level: Literal["pending_confirmation"] = "pending_confirmation"
    responsible_person: str | None = Field(None, max_length=200)
    due_at: datetime | None = None
    due_text: str | None = Field(None, max_length=200)
    confidence: float = Field(ge=0, le=1)
    evidence: list[EventEvidenceRef] = Field(default_factory=list, max_length=50)
    needs_confirmation: bool = True


class SiteEventPayload(BaseModel):
    """Canonical Event v1 business schema used for provider and API validation."""

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["1.0"] = "1.0"
    event_type: Literal["site_inspection"] = "site_inspection"
    construction: SiteConstruction = Field(default_factory=SiteConstruction)
    issues: list[SiteEventIssue] = Field(default_factory=list, max_length=50)
    field_evidence: dict[str, list[EventEvidenceRef]] = Field(default_factory=dict)
    needs_confirmation_fields: list[str] = Field(default_factory=list, max_length=200)
    warnings: list[str] = Field(default_factory=list, max_length=200)
    overall_confidence: float = Field(ge=0, le=1)


class EventExtractionJobOut(BaseModel):
    id: str
    project_id: int
    record_id: int
    status: Literal["QUEUED", "RUNNING", "SUCCEEDED", "FAILED"]
    stage: str
    provider: str
    model: str
    schema_version: str
    result_event_id: str | None
    retry_of_job_id: str | None
    error_code: str | None
    error_message: str | None
    created_at: datetime
    started_at: datetime | None
    finished_at: datetime | None


class EventRevisionOut(BaseModel):
    id: int
    actor_id: int
    action: str
    before_data: SiteEventPayload | None
    after_data: SiteEventPayload | None
    created_at: datetime


class SiteEventOut(BaseModel):
    id: str
    project_id: int
    source_record_id: int
    extraction_job_id: str
    status: Literal["DRAFT", "CONFIRMED", "REJECTED"]
    schema_version: str
    event_type: str
    ai_output: SiteEventPayload
    draft_data: SiteEventPayload
    confirmed_data: SiteEventPayload | None
    evidence_map: dict[str, list[EventEvidenceRef]]
    overall_confidence: float
    confirmed_by: int | None
    confirmed_at: datetime | None
    rejected_by: int | None
    rejected_at: datetime | None
    rejection_reason: str | None
    created_at: datetime
    updated_at: datetime
    revisions: list[EventRevisionOut] = []


class AuthoritativeRecordEvidence(BaseModel):
    project_id: int
    project_name: str
    record_id: int
    recorder_id: int
    recorder_name: str
    recorder_role: str
    occurred_at: datetime
    location_id: int
    building: str
    floor: str
    zone: str
    photo_ids: list[int]


class RecordEventOut(BaseModel):
    record_id: int
    confirmed_text: str | None
    confirmed_text_source: Literal["edited_transcript", "manual_description"] | None
    can_extract: bool
    unavailable_reason: str | None
    authoritative: AuthoritativeRecordEvidence
    latest_job: EventExtractionJobOut | None
    event: SiteEventOut | None


class SiteEventPatch(BaseModel):
    model_config = ConfigDict(extra="forbid")

    payload: SiteEventPayload


class SiteEventRejectIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    reason: str | None = Field(None, max_length=500)
