import hashlib
import io
import json
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from PIL import Image, UnidentifiedImageError
from sqlalchemy.orm import Session

from .auth import current_user, get_db, require_member
from .config import settings
from .knowledge_service import create_document, process_document
from .models import (
    Issue,
    IssueAudit,
    KnowledgeChunk,
    KnowledgeDocument,
    MediaFile,
    Project,
    ProjectMember,
    RagAnalysisJob,
    RectificationSubmission,
    Task,
    TaskAudit,
    TaskReview,
    User,
)
from .phase56_schemas import CancelIn, ConfirmIssueIn, IgnoreIssueIn, ReviewIn
from .rag_service import ensure_successful_job, get_job_result, run_analysis

router = APIRouter(prefix="/api", tags=["knowledge-rag-rectification"])
IMAGE_FORMATS = {
    "JPEG": (".jpg", "image/jpeg"),
    "PNG": (".png", "image/png"),
    "WEBP": (".webp", "image/webp"),
}
MAX_PHOTO_BYTES = 10 * 1024 * 1024
DEMO_TEXT = """# 非正式演示材料
本材料仅供工地小秘功能演示，不是正式规范，不可替代项目批准文件或现行标准。

# 临边防护演示条目
发现临边防护缺失时，应由专业人员核查现场条件，补充可靠防护并留存整改前后照片。

# 临时用电演示条目
发现电缆拖地、配电箱管理异常等现象时，应核查线路、防护和责任管理情况，整改后复查。

# 通道管理演示条目
发现材料堆放影响通道时，应核查通道宽度和现场堆放情况，清理障碍并留存整改照片。
"""


def _document_out(db: Session, item: KnowledgeDocument) -> dict:
    return {
        "id": item.id,
        "project_id": item.project_id,
        "uploaded_by": item.uploaded_by,
        "title": item.title,
        "original_name": item.original_name,
        "mime_type": item.mime_type,
        "size_bytes": item.size_bytes,
        "sha256": item.sha256,
        "status": item.status,
        "is_demo": item.is_demo,
        "error_message": item.error_message,
        "archived_by": item.archived_by,
        "archived_at": item.archived_at,
        "created_at": item.created_at,
        "chunk_count": db.query(KnowledgeChunk).filter_by(document_id=item.id).count(),
        "notice": "仅供功能演示，不是正式规范" if item.is_demo else None,
    }


def _job_out(job: RagAnalysisJob) -> dict:
    return {
        "id": job.id,
        "issue_id": job.issue_id,
        "project_id": job.project_id,
        "status": job.status,
        "provider": job.provider,
        "model": job.model,
        "query": job.query_snapshot,
        "retrieved": json.loads(job.retrieved_snapshot or "[]"),
        "result": get_job_result(job).model_dump(mode="json") if job.validated_result else None,
        "error_message": job.error_message,
        "retry_of_job_id": job.retry_of_job_id,
        "created_at": job.created_at,
        "completed_at": job.completed_at,
    }


def _issue_out(db: Session, item: Issue) -> dict:
    latest = (
        db.query(RagAnalysisJob)
        .filter_by(issue_id=item.id)
        .order_by(RagAnalysisJob.created_at.desc())
        .first()
    )
    task = db.query(Task).filter_by(source_issue_id=item.id).first()
    return {
        "id": item.id,
        "project_id": item.project_id,
        "event_id": item.event_id,
        "record_id": item.record_id,
        "issue_index": item.issue_index,
        "category": item.category,
        "description": item.description_snapshot,
        "location": json.loads(item.location_snapshot),
        "evidence": json.loads(item.evidence_snapshot),
        "occurred_at": item.occurred_at,
        "status": item.status,
        "ignored_reason": item.ignored_reason,
        "task_id": task.id if task else None,
        "latest_rag_job": _job_out(latest) if latest else None,
        "created_at": item.created_at,
    }


def _get_issue(db: Session, issue_id: str, user: User) -> Issue:
    issue = db.get(Issue, issue_id)
    if not issue:
        raise HTTPException(status_code=404, detail="问题不存在")
    require_member(db, user.id, issue.project_id)
    return issue


def _get_document(db: Session, document_id: str, user: User) -> KnowledgeDocument:
    item = db.get(KnowledgeDocument, document_id)
    if not item:
        raise HTTPException(status_code=404, detail="知识文档不存在")
    require_member(db, user.id, item.project_id)
    return item


@router.get("/projects/{project_id}/knowledge-documents")
def list_documents(
    project_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)
):
    require_member(db, user.id, project_id)
    return [
        _document_out(db, item)
        for item in db.query(KnowledgeDocument)
        .filter_by(project_id=project_id)
        .order_by(KnowledgeDocument.created_at.desc())
    ]


@router.post("/projects/{project_id}/knowledge-documents", status_code=201)
def upload_document(
    project_id: int,
    file: UploadFile | None = File(None),
    title: str | None = Form(None),
    seed_demo: bool = Form(False),
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    require_member(db, user.id, project_id)
    if seed_demo:
        data = DEMO_TEXT.encode()
        digest = hashlib.sha256(data).hexdigest()
        existing = (
            db.query(KnowledgeDocument).filter_by(project_id=project_id, sha256=digest).first()
        )
        if existing:
            return _document_out(db, existing)
        settings.knowledge_dir.mkdir(parents=True, exist_ok=True)
        stored_name = f"{uuid4().hex}.md"
        (settings.knowledge_dir / stored_name).write_bytes(data)
        item = KnowledgeDocument(
            id=str(uuid4()),
            project_id=project_id,
            uploaded_by=user.id,
            title="非正式演示安全材料",
            original_name="非正式演示安全材料.md",
            stored_name=stored_name,
            relative_path=f"knowledge/{stored_name}",
            mime_type="text/markdown",
            size_bytes=len(data),
            sha256=digest,
            status="PROCESSING",
            is_demo=True,
        )
        db.add(item)
        db.flush()
        process_document(db, item, data)
        db.commit()
        return _document_out(db, item)
    if not file:
        raise HTTPException(status_code=422, detail="请选择文件或创建演示材料")
    item, _created = create_document(db, project_id, user.id, file, title)
    return _document_out(db, item)


@router.get("/knowledge-documents/{document_id}")
def get_document(
    document_id: str, user: User = Depends(current_user), db: Session = Depends(get_db)
):
    return _document_out(db, _get_document(db, document_id, user))


@router.post("/knowledge-documents/{document_id}/retry")
def retry_document(
    document_id: str, user: User = Depends(current_user), db: Session = Depends(get_db)
):
    item = _get_document(db, document_id, user)
    if item.status != "FAILED":
        raise HTTPException(status_code=409, detail="只有解析失败的文档可以重试")
    try:
        process_document(db, item)
    except Exception as exc:
        item.status, item.error_message = "FAILED", str(exc)[:500]
    db.commit()
    return _document_out(db, item)


@router.post("/knowledge-documents/{document_id}/archive")
def archive_document(
    document_id: str, user: User = Depends(current_user), db: Session = Depends(get_db)
):
    item = _get_document(db, document_id, user)
    if item.uploaded_by != user.id and user.role != "安全员":
        raise HTTPException(status_code=403, detail="只有上传者或项目安全员可以归档")
    if item.status != "ARCHIVED":
        item.status, item.archived_by, item.archived_at = "ARCHIVED", user.id, datetime.now(UTC)
        db.commit()
    return _document_out(db, item)


@router.get("/projects/{project_id}/issues")
def list_issues(
    project_id: int,
    status: str | None = Query(None),
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    require_member(db, user.id, project_id)
    query = db.query(Issue).filter_by(project_id=project_id)
    if status:
        query = query.filter(Issue.status == status)
    return [_issue_out(db, item) for item in query.order_by(Issue.occurred_at.desc()).all()]


@router.get("/issues/{issue_id}")
def get_issue(issue_id: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    return _issue_out(db, _get_issue(db, issue_id, user))


@router.post("/issues/{issue_id}/rag-analyses", status_code=201)
def analyze_issue(issue_id: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    issue = _get_issue(db, issue_id, user)
    if issue.status in {"IGNORED", "TASK_CREATED"}:
        raise HTTPException(status_code=409, detail="已忽略或已建单的问题不能再次分析")
    return _job_out(run_analysis(db, issue, user.id))


@router.get("/rag-analysis-jobs/{job_id}")
def get_rag_job(job_id: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    job = db.get(RagAnalysisJob, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="RAG 分析任务不存在")
    require_member(db, user.id, job.project_id)
    return _job_out(job)


@router.post("/rag-analysis-jobs/{job_id}/retry", status_code=201)
def retry_rag_job(job_id: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    old = db.get(RagAnalysisJob, job_id)
    if not old:
        raise HTTPException(status_code=404, detail="RAG 分析任务不存在")
    require_member(db, user.id, old.project_id)
    if old.status not in {"FAILED", "NO_EVIDENCE"}:
        raise HTTPException(status_code=409, detail="只有失败或依据不足的分析可以重试")
    issue = db.get(Issue, old.issue_id)
    return _job_out(run_analysis(db, issue, user.id, old.id))


@router.post("/issues/{issue_id}/ignore")
def ignore_issue(
    issue_id: str,
    payload: IgnoreIssueIn,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    issue = _get_issue(db, issue_id, user)
    if db.query(Task).filter_by(source_issue_id=issue.id).first():
        raise HTTPException(status_code=409, detail="已建单问题不能忽略")
    issue.status, issue.ignored_reason, issue.ignored_by, issue.ignored_at = (
        "IGNORED",
        payload.reason,
        user.id,
        datetime.now(UTC),
    )
    db.add(
        IssueAudit(
            issue_id=issue.id,
            project_id=issue.project_id,
            actor_id=user.id,
            action="IGNORED",
            payload=payload.model_dump_json(),
        )
    )
    db.commit()
    return _issue_out(db, issue)


@router.post("/issues/{issue_id}/confirm-and-create-task", status_code=201)
def confirm_issue(
    issue_id: str,
    payload: ConfirmIssueIn,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    issue = _get_issue(db, issue_id, user)
    existing = db.query(Task).filter_by(source_issue_id=issue.id).first()
    if existing:
        return _task_detail(db, existing)
    job = ensure_successful_job(db, issue, payload.rag_job_id)
    if (
        not db.query(ProjectMember)
        .filter_by(project_id=issue.project_id, user_id=payload.assignee_id)
        .first()
    ):
        raise HTTPException(status_code=422, detail="责任人必须是当前项目成员")
    task = Task(
        project_id=issue.project_id,
        source_record_id=issue.record_id,
        source_issue_id=issue.id,
        kind="RECTIFICATION",
        creator_id=user.id,
        assignee_id=payload.assignee_id,
        title=payload.final_description[:120],
        description=payload.rectification_measure,
        due_at=payload.due_at.astimezone(UTC),
        status="OPEN",
    )
    db.add(task)
    db.flush()
    frozen = {
        "human": payload.model_dump(mode="json"),
        "ai": json.loads(job.raw_result or "{}"),
        "validated": json.loads(job.validated_result or "{}"),
        "retrieved": json.loads(job.retrieved_snapshot),
    }
    db.add(
        TaskAudit(
            task_id=task.id,
            project_id=task.project_id,
            actor_id=user.id,
            action="CREATED_FROM_ISSUE",
            payload=json.dumps(frozen, ensure_ascii=False, default=str),
        )
    )
    db.add(
        IssueAudit(
            issue_id=issue.id,
            project_id=issue.project_id,
            actor_id=user.id,
            action="CONFIRMED_AND_TASK_CREATED",
            payload=json.dumps(frozen, ensure_ascii=False, default=str),
        )
    )
    issue.status = "TASK_CREATED"
    db.commit()
    return _task_detail(db, task)


def _get_task(db: Session, task_id: int, user: User) -> Task:
    task = db.get(Task, task_id)
    if not task:
        raise HTTPException(status_code=404, detail="待办不存在")
    require_member(db, user.id, task.project_id)
    return task


def _task_detail(db: Session, task: Task) -> dict:
    submissions = (
        db.query(RectificationSubmission)
        .filter_by(task_id=task.id)
        .order_by(RectificationSubmission.round_number)
        .all()
    )
    submission_rows = []
    for item in submissions:
        photos = (
            db.query(MediaFile)
            .filter_by(rectification_submission_id=item.id)
            .order_by(MediaFile.id)
            .all()
        )
        review = db.query(TaskReview).filter_by(submission_id=item.id).first()
        submission_rows.append(
            {
                "id": item.id,
                "round_number": item.round_number,
                "submitted_by": item.submitted_by,
                "note": item.note,
                "created_at": item.created_at,
                "photos": [
                    {
                        "id": p.id,
                        "original_name": p.original_name,
                        "mime_type": p.mime_type,
                        "size_bytes": p.size_bytes,
                        "content_url": p.content_url,
                    }
                    for p in photos
                ],
                "review": {
                    "reviewer_id": review.reviewer_id,
                    "decision": review.decision,
                    "reason": review.reason,
                    "created_at": review.created_at,
                }
                if review
                else None,
            }
        )
    audits = db.query(TaskAudit).filter_by(task_id=task.id).order_by(TaskAudit.created_at).all()
    return {
        "id": task.id,
        "project_id": task.project_id,
        "source_record_id": task.source_record_id,
        "source_issue_id": task.source_issue_id,
        "kind": task.kind,
        "creator_id": task.creator_id,
        "assignee_id": task.assignee_id,
        "title": task.title,
        "description": task.description,
        "due_at": task.due_at,
        "status": task.status,
        "created_at": task.created_at,
        "updated_at": task.updated_at,
        "submissions": submission_rows,
        "audits": [
            {
                "action": a.action,
                "actor_id": a.actor_id,
                "payload": json.loads(a.payload) if a.payload else None,
                "created_at": a.created_at,
            }
            for a in audits
        ],
    }


@router.get("/tasks/{task_id}/workflow")
def task_workflow(task_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    return _task_detail(db, _get_task(db, task_id, user))


@router.post("/tasks/{task_id}/start")
def start_task(task_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    task = _get_task(db, task_id, user)
    if task.assignee_id != user.id:
        raise HTTPException(status_code=403, detail="只有责任人可以启动任务")
    if task.status not in {"OPEN", "待处理"}:
        raise HTTPException(status_code=409, detail="只有待处理任务可以启动")
    task.status = "IN_PROGRESS"
    db.add(
        TaskAudit(
            task_id=task.id,
            project_id=task.project_id,
            actor_id=user.id,
            action="STARTED",
            payload=None,
        )
    )
    db.commit()
    return _task_detail(db, task)


@router.post("/tasks/{task_id}/rectification-submissions", status_code=201)
def submit_rectification(
    task_id: int,
    note: str = Form(..., min_length=1, max_length=5000),
    files: list[UploadFile] = File(...),
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    task = _get_task(db, task_id, user)
    if task.kind != "RECTIFICATION":
        raise HTTPException(status_code=409, detail="普通待办不需要整改提交")
    if task.assignee_id != user.id:
        raise HTTPException(status_code=403, detail="只有责任人可以提交整改")
    if task.status != "IN_PROGRESS":
        raise HTTPException(status_code=409, detail="整改任务必须处于整改中")
    if not 1 <= len(files) <= 9:
        raise HTTPException(status_code=422, detail="每轮必须上传 1–9 张照片")
    validated = []
    for upload in files:
        data = upload.file.read(MAX_PHOTO_BYTES + 1)
        if len(data) > MAX_PHOTO_BYTES:
            raise HTTPException(status_code=413, detail="单张照片不能超过 10MB")
        try:
            with Image.open(io.BytesIO(data)) as image:
                image.verify()
                image_format = image.format
        except (UnidentifiedImageError, OSError) as exc:
            raise HTTPException(status_code=422, detail="仅支持真实 JPEG、PNG、WebP 图片") from exc
        if image_format not in IMAGE_FORMATS:
            raise HTTPException(status_code=422, detail="仅支持 JPEG、PNG、WebP 图片")
        validated.append((upload, data, *IMAGE_FORMATS[image_format]))
    round_number = db.query(RectificationSubmission).filter_by(task_id=task.id).count() + 1
    submission = RectificationSubmission(
        id=str(uuid4()),
        task_id=task.id,
        project_id=task.project_id,
        round_number=round_number,
        submitted_by=user.id,
        note=note.strip(),
    )
    db.add(submission)
    db.flush()
    written: list[Path] = []
    try:
        for upload, data, extension, mime in validated:
            stored_name = f"{uuid4().hex}{extension}"
            path = settings.upload_dir / stored_name
            path.write_bytes(data)
            written.append(path)
            db.add(
                MediaFile(
                    project_id=task.project_id,
                    created_by=user.id,
                    task_id=task.id,
                    rectification_submission_id=submission.id,
                    media_type="image",
                    original_name=Path(upload.filename or "photo").name[:255],
                    stored_name=stored_name,
                    relative_path=f"uploads/{stored_name}",
                    mime_type=mime,
                    size_bytes=len(data),
                )
            )
        task.status = "WAITING_REVIEW"
        db.add(
            TaskAudit(
                task_id=task.id,
                project_id=task.project_id,
                actor_id=user.id,
                action="RECTIFICATION_SUBMITTED",
                payload=json.dumps(
                    {"submission_id": submission.id, "round": round_number}, ensure_ascii=False
                ),
            )
        )
        db.commit()
    except Exception:
        db.rollback()
        for path in written:
            path.unlink(missing_ok=True)
        raise
    return _task_detail(db, task)


@router.post("/tasks/{task_id}/reviews")
def review_task(
    task_id: int,
    payload: ReviewIn,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    task = _get_task(db, task_id, user)
    if task.kind != "RECTIFICATION" or task.status != "WAITING_REVIEW":
        raise HTTPException(status_code=409, detail="任务当前不在待复核状态")
    if user.id == task.assignee_id:
        raise HTTPException(status_code=403, detail="责任人不能自我复核")
    if user.id != task.creator_id and user.role != "安全员":
        raise HTTPException(status_code=403, detail="只有任务创建人或项目安全员可以复核")
    if payload.decision == "REJECT" and not (payload.reason or "").strip():
        raise HTTPException(status_code=422, detail="退回必须填写原因")
    submission = (
        db.query(RectificationSubmission)
        .filter_by(task_id=task.id)
        .order_by(RectificationSubmission.round_number.desc())
        .first()
    )
    review = TaskReview(
        task_id=task.id,
        submission_id=submission.id,
        project_id=task.project_id,
        reviewer_id=user.id,
        decision=payload.decision,
        reason=(payload.reason or "").strip() or None,
    )
    db.add(review)
    task.status = "DONE" if payload.decision == "APPROVE" else "IN_PROGRESS"
    db.add(
        TaskAudit(
            task_id=task.id,
            project_id=task.project_id,
            actor_id=user.id,
            action="REVIEW_APPROVED" if payload.decision == "APPROVE" else "REVIEW_REJECTED",
            payload=payload.model_dump_json(),
        )
    )
    db.commit()
    return _task_detail(db, task)


@router.post("/tasks/{task_id}/complete")
def complete_task(task_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    task = _get_task(db, task_id, user)
    if task.kind != "GENERAL":
        raise HTTPException(status_code=409, detail="整改任务必须通过复核完成")
    if task.assignee_id != user.id:
        raise HTTPException(status_code=403, detail="只有责任人可以完成普通待办")
    if task.status in {"DONE", "CANCELLED", "已完成", "已取消"}:
        raise HTTPException(status_code=409, detail="任务已结束")
    task.status = "DONE"
    db.add(
        TaskAudit(
            task_id=task.id,
            project_id=task.project_id,
            actor_id=user.id,
            action="COMPLETED",
            payload=None,
        )
    )
    db.commit()
    return _task_detail(db, task)


@router.post("/tasks/{task_id}/cancel")
def cancel_task(
    task_id: int,
    payload: CancelIn,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    task = _get_task(db, task_id, user)
    if task.status in {"DONE", "CANCELLED", "已完成", "已取消"}:
        raise HTTPException(status_code=409, detail="任务已结束")
    if task.kind == "RECTIFICATION" and user.id != task.creator_id and user.role != "安全员":
        raise HTTPException(status_code=403, detail="整改任务只能由创建人或项目安全员取消")
    task.status = "CANCELLED"
    db.add(
        TaskAudit(
            task_id=task.id,
            project_id=task.project_id,
            actor_id=user.id,
            action="CANCELLED",
            payload=payload.model_dump_json(),
        )
    )
    db.commit()
    return _task_detail(db, task)


@router.get("/projects/{project_id}/task-reminders")
def task_reminders(
    project_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)
):
    require_member(db, user.id, project_id)
    project = db.get(Project, project_id)
    now = datetime.now(UTC)
    local_today = now.astimezone(ZoneInfo(project.timezone)).date()
    tasks = (
        db.query(Task)
        .filter(
            Task.project_id == project_id,
            Task.kind == "RECTIFICATION",
            Task.status.notin_(["DONE", "CANCELLED"]),
        )
        .all()
    )
    yesterday, overdue, waiting = [], [], []
    for task in tasks:
        issue = db.get(Issue, task.source_issue_id) if task.source_issue_id else None
        discovered_at = issue.occurred_at if issue else task.created_at
        discovered_local = (
            discovered_at.replace(tzinfo=UTC).astimezone(ZoneInfo(project.timezone)).date()
            if discovered_at.tzinfo is None
            else discovered_at.astimezone(ZoneInfo(project.timezone)).date()
        )
        if discovered_local < local_today:
            yesterday.append(task.id)
        due = (
            task.due_at.replace(tzinfo=UTC)
            if task.due_at.tzinfo is None
            else task.due_at.astimezone(UTC)
        )
        if due < now:
            overdue.append(task.id)
        if task.status == "WAITING_REVIEW":
            waiting.append(task.id)
    return {
        "yesterday_unclosed": yesterday,
        "overdue": overdue,
        "waiting_review": waiting,
        "counts": {
            "yesterday_unclosed": len(yesterday),
            "overdue": len(overdue),
            "waiting_review": len(waiting),
        },
    }
