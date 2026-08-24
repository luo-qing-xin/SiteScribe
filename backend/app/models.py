from datetime import UTC, datetime

from sqlalchemy import DateTime, Float, ForeignKey, String, Text, UniqueConstraint
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
    location_id: Mapped[int] = mapped_column(ForeignKey("project_locations.id", ondelete="RESTRICT"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)
    recorder: Mapped[User] = relationship()
    project: Mapped[Project] = relationship()
    location: Mapped[ProjectLocation] = relationship()
    photos: Mapped[list["MediaFile"]] = relationship(cascade="all, delete-orphan")


class MediaFile(Base):
    __tablename__ = "media_files"
    id: Mapped[int] = mapped_column(primary_key=True)
    site_record_id: Mapped[int] = mapped_column(ForeignKey("site_records.id", ondelete="CASCADE"))
    media_type: Mapped[str] = mapped_column(String(20), default="image")
    original_name: Mapped[str] = mapped_column(String(255))
    stored_name: Mapped[str] = mapped_column(String(100), unique=True)
    relative_path: Mapped[str] = mapped_column(String(255))
    mime_type: Mapped[str] = mapped_column(String(50))
    size_bytes: Mapped[int]
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    @property
    def content_url(self) -> str:
        return f"/api/photos/{self.id}/content"


class Task(Base):
    __tablename__ = "tasks"
    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id", ondelete="RESTRICT"))
    source_record_id: Mapped[int | None] = mapped_column(
        ForeignKey("site_records.id", ondelete="SET NULL")
    )
    creator_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    assignee_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    title: Mapped[str] = mapped_column(String(120))
    description: Mapped[str] = mapped_column(Text)
    due_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(String(20), default="待处理")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)
    creator: Mapped[User] = relationship(foreign_keys=[creator_id])
    assignee: Mapped[User] = relationship(foreign_keys=[assignee_id])
