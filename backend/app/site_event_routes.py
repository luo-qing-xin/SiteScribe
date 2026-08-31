import json

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from sqlalchemy.orm import Session, joinedload

from .auth import current_user, get_db, require_member
from .event_schemas import (
    AuthoritativeRecordEvidence,
    EventExtractionJobOut,
    EventRevisionOut,
    RecordEventOut,
    SiteEventOut,
    SiteEventPatch,
    SiteEventRejectIn,
)
from .models import EventExtractionJob, EventRevision, SiteEvent, SiteRecord, User
from .site_event_service import (
    confirm_site_event,
    confirmed_record_text,
    create_extraction_job,
    parse_payload,
    reject_site_event,
    revise_event,
    run_event_extraction,
)

router = APIRouter(prefix="/api", tags=["Event Extraction"])


def _record_for_user(db: Session, record_id: int, user: User) -> SiteRecord:
    record = (
        db.query(SiteRecord)
        .options(
            joinedload(SiteRecord.recorder),
            joinedload(SiteRecord.project),
            joinedload(SiteRecord.location),
            joinedload(SiteRecord.photos),
        )
        .filter(SiteRecord.id == record_id)
        .first()
    )
    if not record:
        raise HTTPException(status_code=404, detail="现场记录不存在")
    require_member(db, user.id, record.project_id)
    return record


def _job_for_user(db: Session, job_id: str, user: User) -> EventExtractionJob:
    job = db.get(EventExtractionJob, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Event 抽取任务不存在")
    require_member(db, user.id, job.project_id)
    return job


def _event_for_user(db: Session, event_id: str, user: User) -> SiteEvent:
    event = db.get(SiteEvent, event_id)
    if not event:
        raise HTTPException(status_code=404, detail="Event 不存在")
    require_member(db, user.id, event.project_id)
    return event


def job_out(job: EventExtractionJob) -> EventExtractionJobOut:
    stages = {
        "QUEUED": "等待分析",
        "RUNNING": "正在分析文本与照片",
        "SUCCEEDED": "结构化完成",
        "FAILED": "分析失败",
    }
    return EventExtractionJobOut(
        id=job.id,
        project_id=job.project_id,
        record_id=job.record_id,
        status=job.status,
        stage=stages.get(job.status, job.status),
        provider=job.provider,
        model=job.model,
        schema_version=job.schema_version,
        result_event_id=job.result_event_id,
        retry_of_job_id=job.retry_of_job_id,
        error_code=job.error_code,
        error_message=job.error_message,
        created_at=job.created_at,
        started_at=job.started_at,
        finished_at=job.finished_at,
    )


def event_out(db: Session, event: SiteEvent) -> SiteEventOut:
    revisions = (
        db.query(EventRevision)
        .filter(EventRevision.event_id == event.id)
        .order_by(EventRevision.created_at, EventRevision.id)
        .all()
    )
    ai_output = parse_payload(event.ai_output)
    draft_data = parse_payload(event.draft_data)
    if not ai_output or not draft_data:
        raise HTTPException(status_code=500, detail="Event 数据损坏")
    return SiteEventOut(
        id=event.id,
        project_id=event.project_id,
        source_record_id=event.source_record_id,
        extraction_job_id=event.extraction_job_id,
        status=event.status,
        schema_version=event.schema_version,
        event_type=event.event_type,
        ai_output=ai_output,
        draft_data=draft_data,
        confirmed_data=parse_payload(event.confirmed_data),
        evidence_map=json.loads(event.evidence_map),
        overall_confidence=event.overall_confidence,
        confirmed_by=event.confirmed_by,
        confirmed_at=event.confirmed_at,
        rejected_by=event.rejected_by,
        rejected_at=event.rejected_at,
        rejection_reason=event.rejection_reason,
        created_at=event.created_at,
        updated_at=event.updated_at,
        revisions=[
            EventRevisionOut(
                id=revision.id,
                actor_id=revision.actor_id,
                action=revision.action,
                before_data=parse_payload(revision.before_data),
                after_data=parse_payload(revision.after_data),
                created_at=revision.created_at,
            )
            for revision in revisions
        ],
    )


@router.post(
    "/records/{record_id}/event-extractions",
    response_model=EventExtractionJobOut,
    status_code=202,
    summary="为现场记录创建 Event 抽取任务",
)
def create_record_event_extraction(
    record_id: int,
    background: BackgroundTasks,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    record = _record_for_user(db, record_id, user)
    job, created = create_extraction_job(db, record, user.id)
    response = job_out(job)
    if created:
        background.add_task(run_event_extraction, job.id)
    return response


@router.get(
    "/event-extraction-jobs/{job_id}",
    response_model=EventExtractionJobOut,
    summary="查询 Event 抽取任务",
)
def read_event_extraction_job(
    job_id: str, user: User = Depends(current_user), db: Session = Depends(get_db)
):
    return job_out(_job_for_user(db, job_id, user))


@router.post(
    "/event-extraction-jobs/{job_id}/retry",
    response_model=EventExtractionJobOut,
    status_code=202,
    summary="重试失败的 Event 抽取任务",
)
def retry_event_extraction_job(
    job_id: str,
    background: BackgroundTasks,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    previous = _job_for_user(db, job_id, user)
    if previous.status != "FAILED":
        raise HTTPException(status_code=409, detail="只有失败的 Event 抽取任务可以重试")
    record = _record_for_user(db, previous.record_id, user)
    job, created = create_extraction_job(db, record, user.id, retry_of_job_id=previous.id)
    response = job_out(job)
    if created:
        background.add_task(run_event_extraction, job.id)
    return response


@router.get(
    "/records/{record_id}/event",
    response_model=RecordEventOut,
    summary="获取记录的 Event、任务状态与权威证据",
)
def read_record_event(
    record_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)
):
    record = _record_for_user(db, record_id, user)
    text, source, _source_id = confirmed_record_text(db, record)
    job = (
        db.query(EventExtractionJob)
        .filter(EventExtractionJob.record_id == record.id)
        .order_by(EventExtractionJob.created_at.desc())
        .first()
    )
    event = (
        db.query(SiteEvent)
        .filter(SiteEvent.source_record_id == record.id)
        .order_by(SiteEvent.created_at.desc())
        .first()
    )
    can_extract = bool(text) and not (event and event.status == "CONFIRMED")
    unavailable_reason = None
    if not text:
        unavailable_reason = "没有人工确认文本"
    elif event and event.status == "CONFIRMED":
        unavailable_reason = "该记录已有已确认 Event"
    return RecordEventOut(
        record_id=record.id,
        confirmed_text=text,
        confirmed_text_source=source,
        can_extract=can_extract,
        unavailable_reason=unavailable_reason,
        authoritative=AuthoritativeRecordEvidence(
            project_id=record.project_id,
            project_name=record.project.name,
            record_id=record.id,
            recorder_id=record.recorder_id,
            recorder_name=record.recorder.name,
            recorder_role=record.recorder.role,
            occurred_at=record.occurred_at,
            location_id=record.location.id,
            building=record.location.building,
            floor=record.location.floor,
            zone=record.location.zone,
            photo_ids=[photo.id for photo in record.photos],
        ),
        latest_job=job_out(job) if job else None,
        event=event_out(db, event) if event else None,
    )


@router.patch(
    "/events/{event_id}",
    response_model=SiteEventOut,
    summary="编辑 Event 草稿并保留审计记录",
)
def patch_site_event(
    event_id: str,
    payload: SiteEventPatch,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    event = _event_for_user(db, event_id, user)
    revise_event(db, event, payload.payload, user.id)
    return event_out(db, event)


@router.post(
    "/events/{event_id}/confirm",
    response_model=SiteEventOut,
    summary="人工确认 Event（不会创建待办或文档）",
)
def confirm_event(event_id: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    event = _event_for_user(db, event_id, user)
    confirm_site_event(db, event, user.id)
    return event_out(db, event)


@router.post(
    "/events/{event_id}/reject",
    response_model=SiteEventOut,
    summary="人工拒绝 Event 并保留 AI 原始输出",
)
def reject_event(
    event_id: str,
    payload: SiteEventRejectIn,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    event = _event_for_user(db, event_id, user)
    reject_site_event(db, event, user.id, payload.reason)
    return event_out(db, event)
