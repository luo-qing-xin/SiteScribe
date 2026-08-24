from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, model_validator


class RecordCategory(StrEnum):
    PROGRESS = "施工进度"
    SAFETY = "安全巡查"
    QUALITY = "质量检查"
    MATERIAL = "材料进场"
    WORK = "人员作业"
    OTHER = "其他"


class TaskStatus(StrEnum):
    TODO = "待处理"
    DOING = "处理中"
    DONE = "已完成"
    CANCELLED = "已取消"


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


class TaskCreate(BaseModel):
    project_id: int
    source_record_id: int | None = None
    assignee_id: int
    title: str = Field(min_length=1, max_length=120)
    description: str = Field(min_length=1, max_length=5000)
    due_at: datetime
    status: TaskStatus = TaskStatus.TODO


class TaskPatch(BaseModel):
    assignee_id: int | None = None
    title: str | None = Field(None, min_length=1, max_length=120)
    description: str | None = Field(None, min_length=1, max_length=5000)
    due_at: datetime | None = None
    status: TaskStatus | None = None


class TaskOut(ORMModel):
    id: int
    project_id: int
    source_record_id: int | None
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
    recent_records: list[RecordOut]
    upcoming_tasks: list[TaskOut]


class MessageOut(BaseModel):
    message: str

