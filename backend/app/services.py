from datetime import UTC, datetime, time, timedelta
from pathlib import Path
from uuid import uuid4
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from fastapi import HTTPException
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from .audio import AudioError, normalize_audio, stored_path
from .db import SessionLocal
from .models import (
    EventDraft,
    MediaFile,
    Project,
    ProjectLocation,
    ProjectMember,
    SiteRecord,
    Task,
    TranscriptionJob,
    User,
)
from .providers import ProviderError, get_asr_provider, get_event_provider
from .schemas import EventConfirmIn, EventPayload, RecordCreate


def validate_location(db: Session, project_id: int, location_id: int) -> ProjectLocation:
    location = db.get(ProjectLocation, location_id)
    if not location or location.project_id != project_id:
        raise HTTPException(status_code=422, detail="所选位置不属于当前项目")
    return location


def create_site_record(
    db: Session,
    payload: RecordCreate | dict,
    recorder_id: int,
    *,
    source_type: str = "MANUAL",
    structured_event: str | None = None,
    event_schema_version: str | None = None,
    source_transcription_job_id: str | None = None,
) -> SiteRecord:
    data = payload.model_dump() if isinstance(payload, RecordCreate) else payload
    validate_location(db, data["project_id"], data["location_id"])
    item = SiteRecord(
        **data,
        recorder_id=recorder_id,
        source_type=source_type,
        structured_event=structured_event,
        event_schema_version=event_schema_version,
        source_transcription_job_id=source_transcription_job_id,
    )
    db.add(item)
    db.flush()
    return item


def create_task_item(db: Session, data: dict, creator_id: int) -> Task:
    membership = (
        db.query(ProjectMember)
        .filter_by(project_id=data["project_id"], user_id=data["assignee_id"])
        .first()
    )
    if not membership:
        raise HTTPException(status_code=422, detail="责任人必须是当前项目成员")
    item = Task(**data, creator_id=creator_id)
    db.add(item)
    db.flush()
    return item


def run_transcription(job_id: str) -> None:
    with SessionLocal() as db:
        job = db.get(TranscriptionJob, job_id)
        if not job or job.status not in {"QUEUED", "FAILED"}:
            return
        job.status = "PROCESSING"
        job.started_at = datetime.now(UTC)
        job.completed_at = None
        job.error_code = None
        job.safe_error_message = None
        db.commit()
        try:
            if not job.original_audio:
                raise AudioError("AUDIO_MISSING", "原始音频不存在")
            original_path = stored_path(job.original_audio.relative_path)
            if job.normalized_audio:
                normalized_path = stored_path(job.normalized_audio.relative_path)
            else:
                normalized_path = normalize_audio(original_path)
                media = MediaFile(
                    project_id=job.project_id,
                    created_by=job.created_by,
                    transcription_job_id=job.id,
                    media_type="audio_normalized",
                    original_name="normalized.wav",
                    stored_name=normalized_path.name,
                    relative_path=f"uploads/{normalized_path.name}",
                    mime_type="audio/wav",
                    size_bytes=normalized_path.stat().st_size,
                )
                db.add(media)
                db.flush()
                job.normalized_audio_media_id = media.id
                db.commit()
            provider = get_asr_provider()
            result = provider.transcribe(normalized_path)
            job = db.get(TranscriptionJob, job_id)
            if not job:
                return
            job.raw_transcript = result.transcript
            job.detected_language = result.detected_language
            job.provider = provider.name
            job.model = provider.model
            job.status = "SUCCEEDED"
            job.completed_at = datetime.now(UTC)
            db.commit()
        except (AudioError, ProviderError) as exc:
            db.rollback()
            job = db.get(TranscriptionJob, job_id)
            if job:
                job.status = "FAILED"
                job.error_code = exc.code
                job.safe_error_message = (
                    exc.message if isinstance(exc, AudioError) else exc.safe_message
                )
                job.completed_at = datetime.now(UTC)
                db.commit()
        except Exception:
            db.rollback()
            job = db.get(TranscriptionJob, job_id)
            if job:
                job.status = "FAILED"
                job.error_code = "ASR_INTERNAL_ERROR"
                job.safe_error_message = "转写处理失败，请稍后重试"
                job.completed_at = datetime.now(UTC)
                db.commit()


def recover_interrupted_jobs(db: Session) -> int:
    jobs = (
        db.query(TranscriptionJob)
        .filter(TranscriptionJob.status.in_(["PROCESSING", "QUEUED"]))
        .all()
    )
    now = datetime.now(UTC)
    for job in jobs:
        job.status = "FAILED"
        job.error_code = "PROCESS_INTERRUPTED"
        job.safe_error_message = "服务重启中断了转写，请点击重试"
        job.completed_at = now
    drafts = db.query(EventDraft).filter(EventDraft.status == "GENERATING").all()
    for draft in drafts:
        draft.status = "FAILED"
        draft.safe_error_message = "服务重启中断了草稿生成，请重新提取"
    db.commit()
    return len(jobs)


def project_timezone(project: Project) -> ZoneInfo:
    try:
        return ZoneInfo(project.timezone)
    except ZoneInfoNotFoundError as exc:
        raise HTTPException(status_code=422, detail="项目时区配置无效") from exc


def relative_deadline(
    text_value: str | None, created_at: datetime, project: Project
) -> datetime | None:
    if not text_value:
        return None
    timezone = project_timezone(project)
    if created_at.tzinfo is None:
        created_at = created_at.replace(tzinfo=UTC)
    local_created = created_at.astimezone(timezone)
    day = local_created.date()
    if "明天" in text_value:
        day += timedelta(days=1)
    elif "后天" in text_value:
        day += timedelta(days=2)
    elif "今天" not in text_value and not any(
        x in text_value for x in ("下午", "上午", "中午", "今晚")
    ):
        return None
    hour = 18
    if "上午" in text_value:
        hour = 10
    elif "中午" in text_value:
        hour = 12
    elif "下午" in text_value:
        hour = 15
    elif "今晚" in text_value or "晚上" in text_value:
        hour = 20
    return datetime.combine(day, time(hour), timezone).astimezone(UTC)


def _match_members_and_deadlines(
    db: Session, job: TranscriptionJob, payload: EventPayload
) -> EventPayload:
    project = db.get(Project, job.project_id)
    if not project:
        raise ProviderError("PROJECT_MISSING", "项目不存在")
    members = (
        db.query(User).join(ProjectMember).filter(ProjectMember.project_id == job.project_id).all()
    )
    for issue in payload.issues:
        issue.candidate_project_member_id = None
        if issue.responsible_person_text:
            matches = [
                member for member in members if member.name == issue.responsible_person_text.strip()
            ]
            if len(matches) == 1:
                issue.candidate_project_member_id = matches[0].id
            else:
                payload.warnings.append(
                    f"责任人“{issue.responsible_person_text}”无法唯一匹配，请人工选择"
                )
        issue.proposed_deadline = relative_deadline(issue.deadline_text, job.created_at, project)
        issue.needs_confirmation = True
    return payload


def generate_event_draft(db: Session, job: TranscriptionJob) -> EventDraft:
    if job.status != "SUCCEEDED" or not job.raw_transcript:
        raise HTTPException(status_code=409, detail="转写成功后才能生成 Event 草稿")
    provider = get_event_provider()
    draft = EventDraft(
        id=str(uuid4()),
        transcription_job_id=job.id,
        project_id=job.project_id,
        created_by=job.created_by,
        status="GENERATING",
        schema_version="1.0",
        provider=provider.name,
        model=provider.model,
        prompt_version="1.0",
    )
    db.add(draft)
    db.commit()
    try:
        source = job.edited_transcript or job.raw_transcript
        provider_payload = provider.extract(source)
        draft.raw_payload = provider_payload.model_dump_json()
        payload = _match_members_and_deadlines(
            db, job, EventPayload.model_validate(provider_payload.model_dump())
        )
        actual_source = "edited_transcript" if job.edited_transcript else "raw_transcript"
        for refs in payload.field_evidence.values():
            for ref in refs:
                if ref.source_type != "audio":
                    ref.source_type = actual_source
        draft.system_resolved_payload = payload.model_dump_json()
        draft.status = "READY"
    except ProviderError as exc:
        draft.status = "FAILED"
        draft.safe_error_message = exc.safe_message
    except Exception:
        draft.status = "FAILED"
        draft.safe_error_message = "Event 草稿生成失败，请重试"
    db.commit()
    return draft


def parse_event_payload(value: str | None) -> EventPayload | None:
    return EventPayload.model_validate_json(value) if value else None


def confirm_event_draft(
    db: Session, draft: EventDraft, job: TranscriptionJob, request: EventConfirmIn, user_id: int
) -> tuple[SiteRecord, list[Task]]:
    if draft.confirmed_record_id:
        record = db.get(SiteRecord, draft.confirmed_record_id)
        if not record:
            raise HTTPException(status_code=409, detail="已确认记录不存在")
        tasks = db.query(Task).filter(Task.source_record_id == record.id).all()
        return record, tasks
    if draft.status != "READY":
        raise HTTPException(status_code=409, detail="当前草稿状态不能确认")
    if job.status != "SUCCEEDED" or not job.raw_transcript:
        raise HTTPException(status_code=409, detail="转写任务尚未成功")
    selected: set[int] = set()
    candidate_ids = {
        issue.candidate_project_member_id
        for issue in request.payload.issues
        if issue.candidate_project_member_id is not None
    }
    if candidate_ids:
        valid_candidates = {
            row.user_id
            for row in db.query(ProjectMember)
            .filter(
                ProjectMember.project_id == job.project_id,
                ProjectMember.user_id.in_(candidate_ids),
            )
            .all()
        }
        if valid_candidates != candidate_ids:
            raise HTTPException(status_code=422, detail="问题候选责任人必须是当前项目成员")
    for choice in request.issues:
        if choice.issue_index >= len(request.payload.issues):
            raise HTTPException(status_code=422, detail="待办问题序号无效")
        if choice.issue_index in selected:
            raise HTTPException(status_code=422, detail="同一问题不能重复创建待办")
        selected.add(choice.issue_index)
        if choice.create_task and (not choice.assignee_id or not choice.due_at or not choice.title):
            raise HTTPException(
                status_code=422, detail="勾选创建待办后必须填写标题、责任人和截止时间"
            )
    record_data = request.record.model_dump()
    record_data["project_id"] = job.project_id
    confirmed_json = request.payload.model_dump_json()
    try:
        record = create_site_record(
            db,
            record_data,
            user_id,
            source_type="VOICE_AI",
            structured_event=confirmed_json,
            event_schema_version=request.payload.schema_version,
            source_transcription_job_id=job.id,
        )
        media = db.query(MediaFile).filter(MediaFile.transcription_job_id == job.id).all()
        for item in media:
            item.site_record_id = record.id
        tasks: list[Task] = []
        for choice in request.issues:
            if not choice.create_task:
                continue
            issue = request.payload.issues[choice.issue_index]
            tasks.append(
                create_task_item(
                    db,
                    {
                        "project_id": job.project_id,
                        "source_record_id": record.id,
                        "assignee_id": choice.assignee_id,
                        "title": choice.title,
                        "description": issue.description,
                        "due_at": choice.due_at,
                        "status": "OPEN",
                    },
                    user_id,
                )
            )
        draft.user_corrected_payload = confirmed_json
        draft.status = "CONFIRMED"
        draft.confirmed_record_id = record.id
        draft.confirmed_at = datetime.now(UTC)
        job.record_id = record.id
        db.commit()
        return record, tasks
    except IntegrityError:
        db.rollback()
        existing = (
            db.query(SiteRecord).filter(SiteRecord.source_transcription_job_id == job.id).first()
        )
        if existing:
            tasks = db.query(Task).filter(Task.source_record_id == existing.id).all()
            return existing, tasks
        raise
    except Exception:
        db.rollback()
        raise


def delete_job_files(db: Session, job: TranscriptionJob) -> list[Path]:
    if job.record_id:
        raise HTTPException(status_code=409, detail="已生成正式记录的任务不能删除")
    media = db.query(MediaFile).filter(MediaFile.transcription_job_id == job.id).all()
    paths = [stored_path(item.relative_path) for item in media]
    for item in media:
        db.delete(item)
    db.delete(job)
    db.commit()
    return paths
