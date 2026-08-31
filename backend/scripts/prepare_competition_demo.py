"""Create deterministic, clearly labelled competition demo data in the selected database."""

import json
from datetime import UTC, datetime, timedelta

from PIL import Image, ImageDraw
from sqlalchemy import select

from app.config import settings
from app.db import SessionLocal
from app.event_schemas import SiteEventPayload
from app.issue_service import sync_event_issues
from app.models import (
    EventExtractionJob,
    KnowledgeChunk,
    KnowledgeDocument,
    MediaFile,
    Project,
    ProjectLocation,
    RectificationSubmission,
    SiteEvent,
    SiteRecord,
    Task,
    TaskReview,
    User,
)

DEMO_PREFIX = "比赛模拟："
DEMO_KNOWLEDGE = """本材料仅供工地小秘功能演示，不是正式规范，不可替代项目批准文件或现行标准。
发现材料堆放影响通道时，应由专业人员核查现场通行条件，清理障碍并留存整改前后照片。"""


def create_demo_image(name: str, *, cleared: bool = False) -> tuple[str, int]:
    directory = settings.upload_dir / "demo"
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / name
    image = Image.new("RGB", (1200, 760), "#d9d2c4")
    draw = ImageDraw.Draw(image)
    draw.rectangle((0, 0, 1200, 150), fill="#171916")
    draw.rectangle((0, 650, 1200, 760), fill="#242522")
    draw.polygon([(120, 650), (360, 220), (840, 220), (1080, 650)], fill="#bbb29f")
    draw.line((600, 220, 600, 650), fill="#f6f3ed", width=12)
    if not cleared:
        for index in range(4):
            x = 180 + index * 92
            draw.rectangle((x, 480 - index * 12, x + 150, 630), fill="#9b5a3d", outline="#5d1d1a", width=5)
    draw.rectangle((30, 28, 300, 105), fill="#c9362a")
    draw.text((55, 52), "SIMULATED DEMO", fill="white")
    draw.text((870, 55), "SiteScribe", fill="#e6c77f")
    image.save(path, format="PNG")
    return f"uploads/demo/{name}", path.stat().st_size


def attach_image(db, *, project_id: int, user_id: int, record_id: int, name: str, cleared: bool = False, task_id: int | None = None, submission_id: str | None = None) -> MediaFile:
    stored_name = f"competition-{name}"
    item = db.scalar(select(MediaFile).where(MediaFile.stored_name == stored_name))
    if item:
        return item
    relative_path, size = create_demo_image(name, cleared=cleared)
    item = MediaFile(
        project_id=project_id,
        created_by=user_id,
        site_record_id=record_id if task_id is None else None,
        task_id=task_id,
        rectification_submission_id=submission_id,
        media_type="image",
        original_name=f"模拟演示-{name}",
        stored_name=stored_name,
        relative_path=relative_path,
        mime_type="image/png",
        size_bytes=size,
    )
    db.add(item)
    db.flush()
    return item


def ensure_event(db, *, record: SiteRecord, recorder: User, description: str, activity: str, issue_text: str) -> tuple[SiteEvent, object]:
    event_id = f"demo-event-{record.id}"
    event = db.get(SiteEvent, event_id)
    if event:
        return event, sync_event_issues(db, event)[0]
    job_id = f"demo-job-{record.id}"
    payload = SiteEventPayload.model_validate({
        "schema_version": "1.0", "event_type": "site_inspection",
        "construction": {"activity": activity, "crew": "钢筋班组", "worker_count": 12, "progress": 0.8},
        "issues": [{
            "description": issue_text, "category": "文明施工/安全", "risk_level": "pending_confirmation",
            "responsible_person": "王强", "due_at": None, "due_text": "今天18:00", "confidence": 0.94,
            "evidence": [{"evidence_type": "confirmed_transcript", "source_id": f"record:{record.id}:description", "quote": issue_text, "description": None, "media_file_id": None, "confidence": 1}],
            "needs_confirmation": True,
        }],
        "field_evidence": {"construction.activity": [{"evidence_type": "confirmed_transcript", "source_id": f"record:{record.id}:description", "quote": activity, "description": None, "media_file_id": None, "confidence": 1}]},
        "needs_confirmation_fields": [], "warnings": ["模拟演示数据，所有判断仍需人工确认"], "overall_confidence": 0.94,
    })
    payload_json = payload.model_dump_json()
    job = EventExtractionJob(
        id=job_id, project_id=record.project_id, record_id=record.id, requested_by=recorder.id,
        status="SUCCEEDED", provider="mock", model="competition-demo", schema_version="1.0",
        input_snapshot=json.dumps({"record_id": record.id, "description": description}, ensure_ascii=False),
        result_event_id=event_id, started_at=record.occurred_at, finished_at=record.occurred_at,
    )
    event = SiteEvent(
        id=event_id, project_id=record.project_id, source_record_id=record.id, extraction_job_id=job_id,
        status="CONFIRMED", schema_version="1.0", event_type="site_inspection", ai_output=payload_json,
        draft_data=payload_json, confirmed_data=payload_json, evidence_map=json.dumps(payload.field_evidence, ensure_ascii=False, default=str),
        overall_confidence=0.94, confirmed_by=recorder.id, confirmed_at=record.occurred_at,
    )
    db.add_all([job, event])
    db.flush()
    return event, sync_event_issues(db, event)[0]


def ensure_knowledge(db, project: Project, recorder: User) -> None:
    if db.get(KnowledgeDocument, "competition-demo-knowledge"):
        return
    directory = settings.knowledge_dir
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / "competition-demo-material.md"
    path.write_text(DEMO_KNOWLEDGE, encoding="utf-8")
    document = KnowledgeDocument(
        id="competition-demo-knowledge", project_id=project.id, uploaded_by=recorder.id,
        title="非正式演示通道管理材料", original_name="非正式演示通道管理材料.md",
        stored_name=path.name, relative_path=f"knowledge/{path.name}", mime_type="text/markdown",
        size_bytes=path.stat().st_size, sha256="competition-demo-knowledge".ljust(64, "0"), status="ACTIVE", is_demo=True,
    )
    db.add(document)
    db.flush()
    db.add(KnowledgeChunk(document_id=document.id, project_id=project.id, chunk_index=0, heading="通道管理演示条目", locator="第 1-2 行", content=DEMO_KNOWLEDGE, normalized_content="材料堆放影响通道清理障碍整改照片"))


def main() -> None:
    now = datetime.now(UTC)
    with SessionLocal() as db:
        project = db.scalar(select(Project).where(Project.name == "海悦花园项目"))
        recorder = db.scalar(select(User).where(User.username == "zhangwei"))
        assignee = db.scalar(select(User).where(User.username == "wangqiang"))
        if not project or not recorder or not assignee:
            raise RuntimeError("请先运行基础 seed")
        project.status = "模拟演示 · 施工中"
        location = db.scalar(select(ProjectLocation).where(ProjectLocation.project_id == project.id, ProjectLocation.building == "3号楼", ProjectLocation.floor == "6层", ProjectLocation.zone == "西侧"))
        if not location:
            raise RuntimeError("演示位置不存在")
        ensure_knowledge(db, project, recorder)
        stages = [
            ("待专业确认", "西侧材料堆放影响通道", "PENDING"),
            ("整改已提交，等待安全员复核", "通道材料已完成清理并上传照片", "WAITING_REVIEW"),
            ("通道整改完成并经安全员复核", "材料堆放问题已完成闭环", "DONE"),
        ]
        for index, (summary, issue_text, stage) in enumerate(stages):
            description = f"{DEMO_PREFIX}3号楼六层钢筋绑扎完成80%，现场12名钢筋工。{issue_text}。"
            record = db.scalar(select(SiteRecord).where(SiteRecord.description == description))
            if not record:
                record = SiteRecord(project_id=project.id, recorder_id=recorder.id, category="安全巡查", description=description, occurred_at=now - timedelta(minutes=15 + index * 18), gps_status="success", latitude=23.1291, longitude=113.2644, gps_accuracy=9, gps_captured_at=now - timedelta(minutes=15 + index * 18), location_id=location.id)
                db.add(record)
                db.flush()
            attach_image(db, project_id=project.id, user_id=recorder.id, record_id=record.id, name=f"corridor-before-{index}.png")
            _, issue = ensure_event(db, record=record, recorder=recorder, description=description, activity="钢筋绑扎", issue_text=issue_text)
            if stage == "PENDING":
                continue
            issue.status = "TASK_CREATED"
            task = db.scalar(select(Task).where(Task.source_issue_id == issue.id))
            if not task:
                task = Task(project_id=project.id, source_record_id=record.id, source_issue_id=issue.id, kind="RECTIFICATION", creator_id=recorder.id, assignee_id=assignee.id, title=f"3号楼6层西侧通道整改 · {summary}", description="清理通道材料并上传整改照片，由安全员独立复核。", due_at=now + timedelta(hours=4), status=stage)
                db.add(task)
                db.flush()
            submission_id = f"demo-submission-{task.id}"
            submission = db.get(RectificationSubmission, submission_id)
            if not submission:
                submission = RectificationSubmission(id=submission_id, task_id=task.id, project_id=project.id, round_number=1, submitted_by=assignee.id, note="已将材料转移至指定堆放区，现场通道恢复畅通。", created_at=now - timedelta(minutes=8))
                db.add(submission)
                db.flush()
                attach_image(db, project_id=project.id, user_id=assignee.id, record_id=record.id, name=f"corridor-cleared-{index}.png", cleared=True, task_id=task.id, submission_id=submission.id)
            if stage == "DONE" and not db.scalar(select(TaskReview).where(TaskReview.submission_id == submission.id)):
                db.add(TaskReview(task_id=task.id, submission_id=submission.id, project_id=project.id, reviewer_id=recorder.id, decision="APPROVE", reason="现场照片与整改说明一致，确认闭环。", created_at=now - timedelta(minutes=3)))
                task.updated_at = now - timedelta(minutes=3)
        db.commit()
    print("Competition demo ready: isolated, synthetic data is clearly labelled.")


if __name__ == "__main__":
    main()
