import base64
import hashlib
import io
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

from fastapi import HTTPException
from PIL import Image, ImageOps, UnidentifiedImageError
from pydantic import ValidationError
from sqlalchemy.orm import Session, joinedload

from .config import settings
from .db import SessionLocal
from .event_schemas import EventEvidenceRef, SiteEventPayload
from .models import (
    EventExtractionJob,
    EventRevision,
    MediaFile,
    SiteEvent,
    SiteRecord,
    TranscriptionJob,
)
from .providers import ProviderError
from .site_event_extractor import PreparedImage, get_site_event_extractor

ACTIVE_JOB_STATUSES = {"QUEUED", "RUNNING"}


def _json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"), default=str)


def _record_query(db: Session):
    return db.query(SiteRecord).options(
        joinedload(SiteRecord.recorder),
        joinedload(SiteRecord.project),
        joinedload(SiteRecord.location),
        joinedload(SiteRecord.photos),
    )


def confirmed_record_text(
    db: Session, record: SiteRecord
) -> tuple[str | None, str | None, str | None]:
    if record.source_type == "VOICE_AI":
        job = (
            db.query(TranscriptionJob)
            .filter(TranscriptionJob.record_id == record.id)
            .order_by(TranscriptionJob.created_at.desc())
            .first()
        )
        if job and job.edited_transcript and job.edited_transcript.strip():
            return (
                job.edited_transcript.strip(),
                "edited_transcript",
                f"transcription-job:{job.id}:edited",
            )
    text = record.description.strip()
    if text:
        return text, "manual_description", f"record:{record.id}:description"
    return None, None, None


def build_input_snapshot(db: Session, record: SiteRecord) -> dict[str, Any]:
    text, source, source_id = confirmed_record_text(db, record)
    if not text or not source or not source_id:
        raise HTTPException(status_code=409, detail="没有人工确认文本，无法进行 AI 结构化")
    photo_ids = sorted(
        media.id
        for media in record.photos
        if media.project_id == record.project_id
        and media.site_record_id == record.id
        and media.media_type == "image"
    )
    return {
        "schema_version": "1.0",
        "confirmed_text": {
            "text": text,
            "source": source,
            "source_id": source_id,
            "version": record.updated_at.isoformat(),
            "sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(),
        },
        "photo_ids": photo_ids,
        "location": {
            "source_id": f"location:{record.location.id}",
            "id": record.location.id,
            "building": record.location.building,
            "floor": record.location.floor,
            "zone": record.location.zone,
        },
        "record_metadata": {
            "source_id": f"record:{record.id}",
            "record_id": record.id,
            "project_id": record.project_id,
            "recorder_id": record.recorder_id,
            "recorder_name": record.recorder.name,
            "recorder_role": record.recorder.role,
            "occurred_at": record.occurred_at.isoformat(),
        },
        "captured_at": datetime.now(UTC).isoformat(),
    }


def create_extraction_job(
    db: Session,
    record: SiteRecord,
    user_id: int,
    *,
    retry_of_job_id: str | None = None,
) -> tuple[EventExtractionJob, bool]:
    confirmed = (
        db.query(SiteEvent)
        .filter(SiteEvent.source_record_id == record.id, SiteEvent.status == "CONFIRMED")
        .first()
    )
    if confirmed:
        raise HTTPException(status_code=409, detail="该记录已有已确认 Event，不能静默重新抽取")
    active = (
        db.query(EventExtractionJob)
        .filter(
            EventExtractionJob.record_id == record.id,
            EventExtractionJob.status.in_(ACTIVE_JOB_STATUSES),
        )
        .order_by(EventExtractionJob.created_at.desc())
        .first()
    )
    if active:
        return active, False
    snapshot = build_input_snapshot(db, record)
    provider = get_site_event_extractor()
    job = EventExtractionJob(
        id=str(uuid4()),
        project_id=record.project_id,
        record_id=record.id,
        requested_by=user_id,
        status="QUEUED",
        provider=provider.name,
        model=provider.model,
        schema_version="1.0",
        input_snapshot=_json(snapshot),
        retry_of_job_id=retry_of_job_id,
    )
    db.add(job)
    db.commit()
    return job, True


def _safe_image_path(relative_path: str) -> Path:
    upload_root = settings.upload_dir.resolve()
    path = (settings.upload_dir.parent / relative_path).resolve()
    if path.parent != upload_root:
        raise ValueError("图片路径不在上传目录")
    return path


def prepare_job_images(
    db: Session, job: EventExtractionJob, snapshot: dict[str, Any]
) -> tuple[list[PreparedImage], list[str]]:
    images: list[PreparedImage] = []
    warnings: list[str] = []
    for media_id in snapshot.get("photo_ids", []):
        media = db.get(MediaFile, media_id)
        if (
            not media
            or media.project_id != job.project_id
            or media.site_record_id != job.record_id
            or media.media_type != "image"
        ):
            warnings.append(f"照片 {media_id} 不属于当前记录，已跳过")
            continue
        try:
            path = _safe_image_path(media.relative_path)
            with Image.open(path) as opened:
                image = ImageOps.exif_transpose(opened)
                image.thumbnail(
                    (
                        settings.event_extraction_image_max_dimension,
                        settings.event_extraction_image_max_dimension,
                    )
                )
                if image.mode not in {"RGB", "L"}:
                    image = image.convert("RGB")
                buffer = io.BytesIO()
                image.save(
                    buffer,
                    format="JPEG",
                    quality=settings.event_extraction_image_quality,
                    optimize=True,
                )
            encoded = base64.b64encode(buffer.getvalue()).decode("ascii")
            images.append(
                PreparedImage(
                    media_file_id=media.id,
                    mime_type="image/jpeg",
                    data_url=f"data:image/jpeg;base64,{encoded}",
                )
            )
        except (OSError, UnidentifiedImageError, ValueError):
            warnings.append(f"照片 {media_id} 处理失败，已跳过")
    if snapshot.get("photo_ids") and not images:
        warnings.append("全部照片处理失败，本次已降级为纯文本抽取")
    return images, warnings


def _validate_ref(
    ref: EventEvidenceRef, snapshot: dict[str, Any], valid_photo_ids: set[int]
) -> tuple[EventEvidenceRef | None, str | None]:
    confirmed = snapshot["confirmed_text"]
    if ref.evidence_type == "confirmed_transcript":
        if ref.source_id != confirmed["source_id"]:
            return None, f"文本证据 source_id {ref.source_id} 无效，已删除"
        if not ref.quote or ref.quote not in confirmed["text"]:
            return None, "文本证据 quote 不在人工确认文本中，已删除"
    elif ref.evidence_type == "photo":
        if ref.media_file_id not in valid_photo_ids:
            return None, f"图片证据 media_file_id {ref.media_file_id} 无效，已删除"
        expected = f"media:{ref.media_file_id}"
        if ref.source_id not in {str(ref.media_file_id), expected}:
            return None, f"图片证据 source_id {ref.source_id} 无效，已删除"
        ref.source_id = expected
    elif ref.evidence_type == "manual_location":
        if ref.source_id != snapshot["location"]["source_id"]:
            return None, f"位置证据 source_id {ref.source_id} 无效，已删除"
    elif ref.evidence_type == "record_metadata":
        if ref.source_id != snapshot["record_metadata"]["source_id"]:
            return None, f"记录元数据 source_id {ref.source_id} 无效，已删除"
    return ref, None


def _fact_paths(payload: SiteEventPayload) -> list[str]:
    paths: list[str] = []
    for field in ("activity", "crew", "worker_count", "progress"):
        if getattr(payload.construction, field) is not None:
            paths.append(f"construction.{field}")
    for index, issue in enumerate(payload.issues):
        paths.extend((f"issues.{index}.description", f"issues.{index}.category"))
        for field in ("responsible_person", "due_at", "due_text"):
            if getattr(issue, field) is not None:
                paths.append(f"issues.{index}.{field}")
    return paths


def validate_event_evidence(
    payload: SiteEventPayload,
    snapshot: dict[str, Any],
    valid_photo_ids: set[int],
    preprocessing_warnings: list[str] | None = None,
) -> SiteEventPayload:
    validated = SiteEventPayload.model_validate(payload.model_dump())
    warnings = list(validated.warnings) + list(preprocessing_warnings or [])
    clean_map: dict[str, list[EventEvidenceRef]] = {}
    for path, references in validated.field_evidence.items():
        clean_refs: list[EventEvidenceRef] = []
        for reference in references:
            clean, warning = _validate_ref(reference, snapshot, valid_photo_ids)
            if clean:
                clean_refs.append(clean)
            if warning:
                warnings.append(warning)
        if clean_refs:
            clean_map[path] = clean_refs

    for index, issue in enumerate(validated.issues):
        clean_issue_refs: list[EventEvidenceRef] = []
        for reference in issue.evidence:
            clean, warning = _validate_ref(reference, snapshot, valid_photo_ids)
            if clean:
                clean_issue_refs.append(clean)
            if warning:
                warnings.append(warning)
        issue.evidence = clean_issue_refs
        description_path = f"issues.{index}.description"
        if description_path not in clean_map and clean_issue_refs:
            clean_map[description_path] = clean_issue_refs
        if issue.due_at is not None:
            issue.due_at = None
            warnings.append("模型返回的截止时间已移除；相对时间必须由人工确认")

    missing = set(validated.needs_confirmation_fields)
    for path in _fact_paths(validated):
        if not clean_map.get(path):
            missing.add(path)
            warnings.append(f"字段 {path} 缺少有效证据，需人工确认")
    validated.field_evidence = clean_map
    validated.needs_confirmation_fields = sorted(missing)
    validated.warnings = list(dict.fromkeys(warnings))[:200]
    for issue in validated.issues:
        issue.needs_confirmation = True
    return validated


def run_event_extraction(job_id: str) -> None:
    with SessionLocal() as db:
        job = db.get(EventExtractionJob, job_id)
        if not job or job.status != "QUEUED":
            return
        job.status = "RUNNING"
        job.started_at = datetime.now(UTC)
        job.finished_at = None
        job.error_code = None
        job.error_message = None
        db.commit()
        try:
            snapshot = json.loads(job.input_snapshot)
            images, image_warnings = prepare_job_images(db, job, snapshot)
            provider = get_site_event_extractor()
            result = provider.extract(snapshot, images)
            valid_photo_ids = {
                row.id
                for row in db.query(MediaFile)
                .filter(
                    MediaFile.site_record_id == job.record_id,
                    MediaFile.project_id == job.project_id,
                    MediaFile.media_type == "image",
                )
                .all()
            }
            payload = validate_event_evidence(
                result.payload, snapshot, valid_photo_ids, image_warnings
            )
            if (
                db.query(SiteEvent)
                .filter(
                    SiteEvent.source_record_id == job.record_id,
                    SiteEvent.status == "CONFIRMED",
                )
                .first()
            ):
                raise ProviderError(
                    "EVENT_ALREADY_CONFIRMED", "该记录已有已确认 Event，本次结果未保存"
                )
            event = SiteEvent(
                id=str(uuid4()),
                project_id=job.project_id,
                source_record_id=job.record_id,
                extraction_job_id=job.id,
                status="DRAFT",
                schema_version=payload.schema_version,
                event_type=payload.event_type,
                ai_output=result.payload.model_dump_json(),
                draft_data=payload.model_dump_json(),
                evidence_map=_json(
                    {
                        path: [ref.model_dump(mode="json") for ref in refs]
                        for path, refs in payload.field_evidence.items()
                    }
                ),
                overall_confidence=payload.overall_confidence,
            )
            db.add(event)
            db.flush()
            db.add(
                EventRevision(
                    event_id=event.id,
                    project_id=event.project_id,
                    actor_id=job.requested_by,
                    action="AI_CREATED",
                    before_data=None,
                    after_data=event.draft_data,
                )
            )
            job.status = "SUCCEEDED"
            job.result_event_id = event.id
            job.response_metadata = _json(
                {
                    **result.response_metadata,
                    "processed_image_ids": [image.media_file_id for image in images],
                    "warnings": image_warnings,
                }
            )
            job.finished_at = datetime.now(UTC)
            db.commit()
        except ProviderError as exc:
            db.rollback()
            _fail_job(db, job_id, exc.code, exc.safe_message)
        except (ValidationError, json.JSONDecodeError):
            db.rollback()
            _fail_job(db, job_id, "EVENT_SCHEMA_MISMATCH", "Event 抽取结果不符合 Schema")
        except Exception:
            db.rollback()
            _fail_job(db, job_id, "EVENT_INTERNAL_ERROR", "Event 抽取失败，请稍后重试")


def _fail_job(db: Session, job_id: str, code: str, message: str) -> None:
    job = db.get(EventExtractionJob, job_id)
    if not job:
        return
    job.status = "FAILED"
    job.error_code = code[:50]
    job.error_message = message[:500]
    job.finished_at = datetime.now(UTC)
    db.commit()


def recover_interrupted_event_jobs(db: Session) -> int:
    jobs = (
        db.query(EventExtractionJob)
        .filter(EventExtractionJob.status.in_(["QUEUED", "RUNNING"]))
        .all()
    )
    now = datetime.now(UTC)
    for job in jobs:
        job.status = "FAILED"
        job.error_code = "PROCESS_INTERRUPTED"
        job.error_message = "服务重启中断了 Event 抽取，请点击重试"
        job.finished_at = now
    db.commit()
    return len(jobs)


def parse_payload(value: str | None) -> SiteEventPayload | None:
    return SiteEventPayload.model_validate_json(value) if value else None


def revise_event(
    db: Session, event: SiteEvent, payload: SiteEventPayload, actor_id: int
) -> SiteEvent:
    if event.status != "DRAFT":
        raise HTTPException(status_code=409, detail="只有待确认 Event 草稿可以编辑")
    job = db.get(EventExtractionJob, event.extraction_job_id)
    if not job:
        raise HTTPException(status_code=409, detail="Event 抽取任务不存在")
    snapshot = json.loads(job.input_snapshot)
    valid_photo_ids = {
        row.id
        for row in db.query(MediaFile)
        .filter(
            MediaFile.site_record_id == event.source_record_id,
            MediaFile.project_id == event.project_id,
            MediaFile.media_type == "image",
        )
        .all()
    }
    clean = validate_event_evidence(payload, snapshot, valid_photo_ids)
    original = parse_payload(event.ai_output)
    if original:
        for path in _fact_paths(clean):
            if _path_value(clean, path) != _path_value(original, path):
                clean.needs_confirmation_fields = sorted(
                    set(clean.needs_confirmation_fields) | {path}
                )
    before = event.draft_data
    event.draft_data = clean.model_dump_json()
    event.evidence_map = _json(
        {
            path: [ref.model_dump(mode="json") for ref in refs]
            for path, refs in clean.field_evidence.items()
        }
    )
    event.overall_confidence = clean.overall_confidence
    db.add(
        EventRevision(
            event_id=event.id,
            project_id=event.project_id,
            actor_id=actor_id,
            action="EDITED",
            before_data=before,
            after_data=event.draft_data,
        )
    )
    db.commit()
    return event


def _path_value(payload: SiteEventPayload, path: str):
    parts = path.split(".")
    value: Any = payload
    for part in parts:
        if isinstance(value, list):
            value = value[int(part)]
        else:
            value = getattr(value, part)
    return value


def confirm_site_event(db: Session, event: SiteEvent, actor_id: int) -> SiteEvent:
    if event.status == "CONFIRMED":
        return event
    if event.status != "DRAFT":
        raise HTTPException(status_code=409, detail="只有待确认 Event 草稿可以确认")
    final = SiteEventPayload.model_validate_json(event.draft_data)
    before = event.draft_data
    event.confirmed_data = final.model_dump_json()
    event.status = "CONFIRMED"
    event.confirmed_by = actor_id
    event.confirmed_at = datetime.now(UTC)
    db.add(
        EventRevision(
            event_id=event.id,
            project_id=event.project_id,
            actor_id=actor_id,
            action="CONFIRMED",
            before_data=before,
            after_data=event.confirmed_data,
        )
    )
    from .issue_service import sync_event_issues

    sync_event_issues(db, event)
    db.commit()
    return event


def reject_site_event(
    db: Session, event: SiteEvent, actor_id: int, reason: str | None
) -> SiteEvent:
    if event.status == "REJECTED":
        return event
    if event.status != "DRAFT":
        raise HTTPException(status_code=409, detail="只有待确认 Event 草稿可以拒绝")
    before = event.draft_data
    event.status = "REJECTED"
    event.rejected_by = actor_id
    event.rejected_at = datetime.now(UTC)
    event.rejection_reason = reason
    db.add(
        EventRevision(
            event_id=event.id,
            project_id=event.project_id,
            actor_id=actor_id,
            action="REJECTED",
            before_data=before,
            after_data=before,
        )
    )
    db.commit()
    return event
