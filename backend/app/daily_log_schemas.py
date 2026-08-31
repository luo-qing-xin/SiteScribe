from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from .event_schemas import EventEvidenceRef

DailyLogType = Literal["CONSTRUCTION", "SAFETY"]
HazardClassification = Literal["UNCLASSIFIED", "GENERAL", "MAJOR", "NOT_HAZARD"]


class DailyLogCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    date: date
    log_type: DailyLogType


class DailyLogLocation(BaseModel):
    building: str
    floor: str
    zone: str


class DailyLogConstruction(BaseModel):
    activity: str | None = None
    crew: str | None = None
    worker_count: int | None = None
    progress: float | None = None


class DailyLogIssue(BaseModel):
    key: str
    description: str
    category: str
    responsible_person: str | None = None
    evidence: list[EventEvidenceRef] = Field(default_factory=list)


class DailyLogEntry(BaseModel):
    event_id: str
    record_id: int
    occurred_at: datetime
    category: str
    recorder_name: str
    recorder_role: str
    location: DailyLogLocation
    construction: DailyLogConstruction
    issues: list[DailyLogIssue] = Field(default_factory=list)
    field_evidence: dict[str, list[EventEvidenceRef]] = Field(default_factory=dict)


class DailyLogAutoContent(BaseModel):
    schema_version: Literal["1.0"] = "1.0"
    entries: list[DailyLogEntry] = Field(default_factory=list)


class DailyLogManualContent(BaseModel):
    model_config = ConfigDict(extra="forbid")

    weather: str = Field("", max_length=5000)
    machinery: str = Field("", max_length=5000)
    production_notes: str = Field("", max_length=5000)
    technical_quality_safety: str = Field("", max_length=5000)
    inspection_acceptance: str = Field("", max_length=5000)
    construction_other: str = Field("", max_length=5000)
    pre_shift_inspection: str = Field("", max_length=5000)
    pre_shift_education: str = Field("", max_length=5000)
    dangerous_projects: str = Field("", max_length=5000)
    high_risk_work: str = Field("", max_length=5000)
    incident_response: str = Field("", max_length=5000)
    personnel_duties: str = Field("", max_length=5000)
    other_safety_management: str = Field("", max_length=5000)
    hazard_classifications: dict[str, HazardClassification] = Field(default_factory=dict)


class DailyLogPatch(BaseModel):
    model_config = ConfigDict(extra="forbid")

    manual_content: DailyLogManualContent


class DailyLogSourceOut(BaseModel):
    event_id: str
    record_id: int
    evidence: dict[str, object]


class DailyLogAuditOut(BaseModel):
    id: int
    actor_id: int
    action: str
    created_at: datetime


class DailyLogOut(BaseModel):
    id: str
    document_id: int
    project_id: int
    project_name: str
    date: date
    log_type: DailyLogType
    version: int
    status: Literal["DRAFT", "CONFIRMED"]
    auto_content: DailyLogAutoContent
    manual_content: DailyLogManualContent
    stale: bool
    new_event_count: int
    sources: list[DailyLogSourceOut]
    audits: list[DailyLogAuditOut]
    created_by: int
    updated_by: int
    confirmed_by: int | None
    confirmed_at: datetime | None
    created_at: datetime
    updated_at: datetime


class DailyLogVersionSummary(BaseModel):
    id: str
    version: int
    status: Literal["DRAFT", "CONFIRMED"]
    source_count: int
    confirmed_at: datetime | None
    created_at: datetime


class DailyLogListOut(BaseModel):
    date: date
    logs: list[DailyLogOut]
