import io
from pathlib import Path
from uuid import uuid4

from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse
from PIL import Image, UnidentifiedImageError
from sqlalchemy.orm import Session, joinedload

from .audio import AudioError, save_and_validate_upload, stored_path
from .auth import current_user, get_db, require_member
from .models import EventDraft, MediaFile, SiteRecord, Task, TranscriptionJob, User
from .providers import ProviderError, get_asr_provider
from .schemas import (
    EventConfirmIn,
    EventConfirmOut,
    EventDraftOut,
    EventDraftPatch,
    MediaOut,
    MessageOut,
    RecordOut,
    TaskOut,
    TranscriptionJobOut,
    TranscriptPatch,
    VoiceEvidenceOut,
)
from .services import (
    confirm_event_draft,
    delete_job_files,
    generate_event_draft,
    parse_event_payload,
    run_transcription,
)

router = APIRouter(prefix="/api")
IMAGE_MIME = {"JPEG": "image/jpeg", "PNG": "image/png", "WEBP": "image/webp"}


def job_query(db: Session):
    return db.query(TranscriptionJob).options(joinedload(TranscriptionJob.original_audio))


def get_job(db: Session, job_id: str, user: User) -> TranscriptionJob:
    job = job_query(db).filter(TranscriptionJob.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="转写任务不存在")
    require_member(db, user.id, job.project_id)
    return job


def get_draft(db: Session, draft_id: str, user: User) -> EventDraft:
    draft = db.get(EventDraft, draft_id)
    if not draft:
        raise HTTPException(status_code=404, detail="Event 草稿不存在")
    require_member(db, user.id, draft.project_id)
    return draft


def require_job_owner(job: TranscriptionJob, user: User) -> None:
    if job.created_by != user.id:
        raise HTTPException(status_code=403, detail="只能修改本人创建的语音任务")


def draft_out(draft: EventDraft) -> EventDraftOut:
    return EventDraftOut(
        id=draft.id,
        transcription_job_id=draft.transcription_job_id,
        project_id=draft.project_id,
        status=draft.status,
        raw_payload=parse_event_payload(draft.raw_payload),
        system_resolved_payload=parse_event_payload(draft.system_resolved_payload),
        user_corrected_payload=parse_event_payload(draft.user_corrected_payload),
        schema_version=draft.schema_version,
        provider=draft.provider,
        model=draft.model,
        prompt_version=draft.prompt_version,
        safe_error_message=draft.safe_error_message,
        confirmed_record_id=draft.confirmed_record_id,
        created_at=draft.created_at,
        updated_at=draft.updated_at,
        confirmed_at=draft.confirmed_at,
    )


@router.post("/transcription-jobs", response_model=TranscriptionJobOut, status_code=202)
def create_transcription_job(
    background: BackgroundTasks,
    project_id: int = Form(...),
    audio: UploadFile = File(...),
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    require_member(db, user.id, project_id)
    path = None
    try:
        path, info, size = save_and_validate_upload(audio)
        provider = get_asr_provider()
        job = TranscriptionJob(
            id=str(uuid4()),
            project_id=project_id,
            created_by=user.id,
            status="QUEUED",
            provider=provider.name,
            model=provider.model,
        )
        db.add(job)
        db.flush()
        media = MediaFile(
            project_id=project_id,
            created_by=user.id,
            transcription_job_id=job.id,
            media_type="audio_original",
            original_name=Path(audio.filename or "recording").name[:255],
            stored_name=path.name,
            relative_path=f"uploads/{path.name}",
            mime_type=info.mime_type,
            size_bytes=size,
        )
        db.add(media)
        db.flush()
        job.original_audio_media_id = media.id
        db.commit()
        background.add_task(run_transcription, job.id)
        return job_query(db).filter(TranscriptionJob.id == job.id).one()
    except AudioError as exc:
        if path:
            path.unlink(missing_ok=True)
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc
    except ProviderError as exc:
        if path:
            path.unlink(missing_ok=True)
        db.rollback()
        raise HTTPException(status_code=503, detail=exc.safe_message) from exc
    except Exception:
        if path:
            path.unlink(missing_ok=True)
        db.rollback()
        raise


@router.get("/transcription-jobs/{job_id}", response_model=TranscriptionJobOut)
def read_transcription_job(
    job_id: str, user: User = Depends(current_user), db: Session = Depends(get_db)
):
    return get_job(db, job_id, user)


@router.post("/transcription-jobs/{job_id}/retry", response_model=TranscriptionJobOut)
def retry_transcription_job(
    job_id: str,
    background: BackgroundTasks,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    job = get_job(db, job_id, user)
    require_job_owner(job, user)
    if job.status not in {"FAILED"}:
        raise HTTPException(status_code=409, detail="只有失败的任务可以重试")
    job.status = "QUEUED"
    job.error_code = None
    job.safe_error_message = None
    db.commit()
    background.add_task(run_transcription, job.id)
    return job


@router.patch("/transcription-jobs/{job_id}/transcript", response_model=TranscriptionJobOut)
def update_transcript(
    job_id: str,
    payload: TranscriptPatch,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    job = get_job(db, job_id, user)
    require_job_owner(job, user)
    if job.status != "SUCCEEDED" or not job.raw_transcript:
        raise HTTPException(status_code=409, detail="转写成功后才能保存修订文本")
    job.edited_transcript = payload.edited_transcript
    db.commit()
    return job


@router.post("/transcription-jobs/{job_id}/photos", response_model=list[MediaOut], status_code=201)
def upload_pending_photos(
    job_id: str,
    files: list[UploadFile] = File(...),
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    job = get_job(db, job_id, user)
    require_job_owner(job, user)
    existing = (
        db.query(MediaFile)
        .filter(MediaFile.transcription_job_id == job.id, MediaFile.media_type == "image")
        .count()
    )
    if not files or existing + len(files) > 9:
        raise HTTPException(status_code=422, detail="每条记录最多上传 9 张照片")
    validated = []
    for upload in files:
        data = upload.file.read(10 * 1024 * 1024 + 1)
        if len(data) > 10 * 1024 * 1024:
            raise HTTPException(status_code=413, detail="单张照片不能超过 10MB")
        try:
            with Image.open(io.BytesIO(data)) as image:
                image.verify()
                image_format = image.format
        except (UnidentifiedImageError, OSError) as exc:
            raise HTTPException(
                status_code=422, detail="仅支持有效的 JPEG、PNG、WebP 图片"
            ) from exc
        if image_format not in IMAGE_MIME:
            raise HTTPException(status_code=422, detail="仅支持有效的 JPEG、PNG、WebP 图片")
        validated.append((upload, data, image_format))
    created = []
    paths = []
    try:
        for upload, data, image_format in validated:
            suffix = {"JPEG": ".jpg", "PNG": ".png", "WEBP": ".webp"}[image_format]
            stored_name = f"{uuid4().hex}{suffix}"
            path = stored_path(f"uploads/{stored_name}")
            path.write_bytes(data)
            paths.append(path)
            media = MediaFile(
                project_id=job.project_id,
                created_by=user.id,
                transcription_job_id=job.id,
                media_type="image",
                original_name=Path(upload.filename or "photo").name[:255],
                stored_name=stored_name,
                relative_path=f"uploads/{stored_name}",
                mime_type=IMAGE_MIME[image_format],
                size_bytes=len(data),
            )
            db.add(media)
            created.append(media)
        db.commit()
        return created
    except Exception:
        db.rollback()
        for path in paths:
            path.unlink(missing_ok=True)
        raise


@router.delete("/transcription-jobs/{job_id}", response_model=MessageOut)
def delete_transcription_job(
    job_id: str, user: User = Depends(current_user), db: Session = Depends(get_db)
):
    job = get_job(db, job_id, user)
    require_job_owner(job, user)
    paths = delete_job_files(db, job)
    for path in paths:
        path.unlink(missing_ok=True)
    return MessageOut(message="转写任务及派生文件已删除")


@router.post("/transcription-jobs/{job_id}/event-drafts", response_model=EventDraftOut)
def create_event_draft(
    job_id: str, user: User = Depends(current_user), db: Session = Depends(get_db)
):
    job = get_job(db, job_id, user)
    require_job_owner(job, user)
    return draft_out(generate_event_draft(db, job))


@router.get("/event-drafts/{draft_id}", response_model=EventDraftOut)
def read_event_draft(
    draft_id: str, user: User = Depends(current_user), db: Session = Depends(get_db)
):
    return draft_out(get_draft(db, draft_id, user))


@router.patch("/event-drafts/{draft_id}", response_model=EventDraftOut)
def update_event_draft(
    draft_id: str,
    payload: EventDraftPatch,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    draft = get_draft(db, draft_id, user)
    if draft.created_by != user.id:
        raise HTTPException(status_code=403, detail="只能修改本人创建的 Event 草稿")
    if draft.status not in {"READY", "FAILED"}:
        raise HTTPException(status_code=409, detail="当前草稿状态不能修改")
    draft.user_corrected_payload = payload.payload.model_dump_json()
    draft.status = "READY"
    draft.safe_error_message = None
    db.commit()
    return draft_out(draft)


@router.post("/event-drafts/{draft_id}/confirm", response_model=EventConfirmOut)
def confirm_draft(
    draft_id: str,
    payload: EventConfirmIn,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    draft = get_draft(db, draft_id, user)
    job = get_job(db, draft.transcription_job_id, user)
    if job.project_id != draft.project_id or draft.created_by != job.created_by:
        raise HTTPException(status_code=409, detail="草稿与转写任务不一致")
    if job.created_by != user.id:
        raise HTTPException(status_code=403, detail="只能确认本人创建的语音任务")
    record, tasks = confirm_event_draft(db, draft, job, payload, user.id)
    record = (
        db.query(SiteRecord)
        .options(
            joinedload(SiteRecord.recorder),
            joinedload(SiteRecord.project),
            joinedload(SiteRecord.location),
            joinedload(SiteRecord.photos),
        )
        .filter(SiteRecord.id == record.id)
        .one()
    )
    tasks = (
        db.query(Task)
        .options(joinedload(Task.creator), joinedload(Task.assignee))
        .filter(Task.source_record_id == record.id)
        .all()
    )
    return EventConfirmOut(
        record=RecordOut.model_validate(record),
        tasks=[TaskOut.model_validate(task) for task in tasks],
    )


@router.get("/media/{media_id}/content")
def media_content(media_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    media = db.get(MediaFile, media_id)
    if not media:
        raise HTTPException(status_code=404, detail="媒体不存在")
    require_member(db, user.id, media.project_id)
    path = stored_path(media.relative_path)
    if not path.is_file():
        raise HTTPException(status_code=404, detail="媒体文件不存在")
    return FileResponse(path, media_type=media.mime_type, filename=media.stored_name)


@router.get("/records/{record_id}/voice-evidence", response_model=VoiceEvidenceOut)
def voice_evidence(
    record_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)
):
    record = db.get(SiteRecord, record_id)
    if not record or record.source_type != "VOICE_AI":
        raise HTTPException(status_code=404, detail="语音证据不存在")
    require_member(db, user.id, record.project_id)
    job = job_query(db).filter(TranscriptionJob.record_id == record.id).first()
    if not job:
        raise HTTPException(status_code=404, detail="语音证据不存在")
    draft = (
        db.query(EventDraft)
        .filter(
            EventDraft.transcription_job_id == job.id, EventDraft.confirmed_record_id == record.id
        )
        .order_by(EventDraft.created_at.desc())
        .first()
    )
    return VoiceEvidenceOut(
        job=TranscriptionJobOut.model_validate(job), draft=draft_out(draft) if draft else None
    )
