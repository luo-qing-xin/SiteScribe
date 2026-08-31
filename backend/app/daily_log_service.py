import hashlib
import json
from datetime import UTC, date, datetime, time
from uuid import uuid4

from fastapi import HTTPException
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, joinedload

from .daily_log_schemas import (
    DailyLogAuditOut,
    DailyLogAutoContent,
    DailyLogEntry,
    DailyLogIssue,
    DailyLogLocation,
    DailyLogManualContent,
    DailyLogOut,
    DailyLogSourceOut,
    DailyLogVersionSummary,
)
from .event_schemas import SiteEventPayload
from .models import (
    DailyLogAudit,
    DailyLogDocument,
    DailyLogSource,
    DailyLogVersion,
    Project,
    SiteEvent,
    SiteRecord,
)
from .services import project_timezone


def _json(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=True)


def _day_bounds(project: Project, log_date: date) -> tuple[datetime, datetime]:
    zone = project_timezone(project)
    start = datetime.combine(log_date, time.min, zone).astimezone(UTC)
    end = datetime.combine(log_date, time.max, zone).astimezone(UTC)
    return start, end


def _confirmed_rows(
    db: Session, project: Project, log_date: date
) -> list[tuple[SiteEvent, SiteRecord]]:
    start, end = _day_bounds(project, log_date)
    return (
        db.query(SiteEvent, SiteRecord)
        .join(SiteRecord, SiteRecord.id == SiteEvent.source_record_id)
        .options(joinedload(SiteRecord.location), joinedload(SiteRecord.recorder))
        .filter(
            SiteEvent.project_id == project.id,
            SiteEvent.status == "CONFIRMED",
            SiteRecord.occurred_at >= start,
            SiteRecord.occurred_at <= end,
        )
        .order_by(SiteRecord.occurred_at, SiteEvent.id)
        .all()
    )


def _digest(rows: list[tuple[SiteEvent, SiteRecord]]) -> str:
    payload = [
        {
            "event_id": event.id,
            "confirmed_at": event.confirmed_at.isoformat() if event.confirmed_at else None,
            "confirmed_data": json.loads(event.confirmed_data or "{}"),
        }
        for event, _record in rows
    ]
    return hashlib.sha256(_json(payload).encode()).hexdigest()


def _build_content(
    rows: list[tuple[SiteEvent, SiteRecord]],
) -> tuple[DailyLogAutoContent, list[dict[str, object]]]:
    entries: list[DailyLogEntry] = []
    source_data: list[dict[str, object]] = []
    for event, record in rows:
        payload = SiteEventPayload.model_validate_json(event.confirmed_data or "{}")
        issues = [
            DailyLogIssue(
                key=f"{event.id}:{index}",
                description=issue.description,
                category=issue.category,
                responsible_person=issue.responsible_person,
                evidence=issue.evidence,
            )
            for index, issue in enumerate(payload.issues)
        ]
        entry = DailyLogEntry(
            event_id=event.id,
            record_id=record.id,
            occurred_at=record.occurred_at,
            category=record.category,
            recorder_name=record.recorder.name,
            recorder_role=record.recorder.role,
            location=DailyLogLocation(
                building=record.location.building,
                floor=record.location.floor,
                zone=record.location.zone,
            ),
            construction=payload.construction.model_dump(),
            issues=issues,
            field_evidence=payload.field_evidence,
        )
        entries.append(entry)
        evidence = {
            "field_evidence": {
                key: [item.model_dump(mode="json") for item in value]
                for key, value in payload.field_evidence.items()
            },
            "issues": {
                issue.key: [item.model_dump(mode="json") for item in issue.evidence]
                for issue in issues
            },
        }
        source_data.append(
            {
                "event": event,
                "record": record,
                "event_snapshot": entry.model_dump(mode="json"),
                "evidence_snapshot": evidence,
            }
        )
    return DailyLogAutoContent(entries=entries), source_data


def _manual_for_content(
    log_type: str,
    auto: DailyLogAutoContent,
    previous: DailyLogManualContent | None = None,
) -> DailyLogManualContent:
    manual = previous.model_copy(deep=True) if previous else DailyLogManualContent()
    if log_type != "SAFETY":
        manual.hazard_classifications = {}
        return manual
    previous_classes = manual.hazard_classifications
    keys = [issue.key for entry in auto.entries for issue in entry.issues]
    manual.hazard_classifications = {key: previous_classes.get(key, "UNCLASSIFIED") for key in keys}
    return manual


def _snapshot(version: DailyLogVersion) -> str:
    return _json(
        {
            "status": version.status,
            "auto_content": json.loads(version.auto_content),
            "manual_content": json.loads(version.manual_content),
            "source_digest": version.source_digest,
        }
    )


def _audit(
    db: Session,
    version: DailyLogVersion,
    actor_id: int,
    action: str,
    before: str | None,
) -> None:
    db.add(
        DailyLogAudit(
            version_id=version.id,
            project_id=version.project_id,
            actor_id=actor_id,
            action=action,
            before_data=before,
            after_data=_snapshot(version),
        )
    )


def _replace_sources(
    db: Session, version: DailyLogVersion, sources: list[dict[str, object]]
) -> None:
    db.query(DailyLogSource).filter(DailyLogSource.version_id == version.id).delete()
    for source in sources:
        event = source["event"]
        record = source["record"]
        assert isinstance(event, SiteEvent) and isinstance(record, SiteRecord)
        db.add(
            DailyLogSource(
                version_id=version.id,
                project_id=version.project_id,
                event_id=event.id,
                record_id=record.id,
                event_snapshot=_json(source["event_snapshot"]),
                evidence_snapshot=_json(source["evidence_snapshot"]),
            )
        )


def create_daily_log(
    db: Session, project: Project, log_date: date, log_type: str, actor_id: int
) -> DailyLogVersion:
    document = (
        db.query(DailyLogDocument)
        .filter_by(project_id=project.id, log_date=log_date, log_type=log_type)
        .first()
    )
    if document:
        existing = (
            db.query(DailyLogVersion)
            .filter_by(document_id=document.id)
            .order_by(DailyLogVersion.version.desc())
            .first()
        )
        if existing:
            return existing
    else:
        document = DailyLogDocument(project_id=project.id, log_date=log_date, log_type=log_type)
        db.add(document)
        try:
            db.flush()
        except IntegrityError:
            db.rollback()
            document = (
                db.query(DailyLogDocument)
                .filter_by(project_id=project.id, log_date=log_date, log_type=log_type)
                .one()
            )
            existing = (
                db.query(DailyLogVersion)
                .filter_by(document_id=document.id)
                .order_by(DailyLogVersion.version.desc())
                .first()
            )
            if existing:
                return existing
    rows = _confirmed_rows(db, project, log_date)
    auto, sources = _build_content(rows)
    manual = _manual_for_content(log_type, auto)
    version = DailyLogVersion(
        id=str(uuid4()),
        document_id=document.id,
        project_id=project.id,
        version=1,
        status="DRAFT",
        auto_content=auto.model_dump_json(),
        manual_content=manual.model_dump_json(),
        source_digest=_digest(rows),
        created_by=actor_id,
        updated_by=actor_id,
    )
    db.add(version)
    db.flush()
    _replace_sources(db, version, sources)
    _audit(db, version, actor_id, "CREATED", None)
    db.commit()
    return version


def refresh_daily_log(db: Session, version: DailyLogVersion, actor_id: int) -> DailyLogVersion:
    document = db.get(DailyLogDocument, version.document_id)
    project = db.get(Project, version.project_id)
    if not document or not project:
        raise HTTPException(status_code=409, detail="日志所属项目不存在")
    rows = _confirmed_rows(db, project, document.log_date)
    auto, sources = _build_content(rows)
    previous_manual = DailyLogManualContent.model_validate_json(version.manual_content)
    manual = _manual_for_content(document.log_type, auto, previous_manual)
    if version.status == "CONFIRMED":
        latest = (
            db.query(DailyLogVersion)
            .filter_by(document_id=document.id)
            .order_by(DailyLogVersion.version.desc())
            .first()
        )
        if latest and latest.id != version.id:
            return latest
        next_number = version.version + 1
        refreshed = DailyLogVersion(
            id=str(uuid4()),
            document_id=document.id,
            project_id=version.project_id,
            version=next_number,
            status="DRAFT",
            auto_content=auto.model_dump_json(),
            manual_content=manual.model_dump_json(),
            source_digest=_digest(rows),
            created_by=actor_id,
            updated_by=actor_id,
        )
        db.add(refreshed)
        db.flush()
        _replace_sources(db, refreshed, sources)
        _audit(db, refreshed, actor_id, "REFRESHED_FROM_CONFIRMED", None)
        db.commit()
        return refreshed
    before = _snapshot(version)
    version.auto_content = auto.model_dump_json()
    version.manual_content = manual.model_dump_json()
    version.source_digest = _digest(rows)
    version.updated_by = actor_id
    _replace_sources(db, version, sources)
    _audit(db, version, actor_id, "REFRESHED", before)
    db.commit()
    return version


def patch_daily_log(
    db: Session,
    version: DailyLogVersion,
    manual: DailyLogManualContent,
    actor_id: int,
) -> DailyLogVersion:
    if version.status != "DRAFT":
        raise HTTPException(status_code=409, detail="已确认日志不可修改")
    document = db.get(DailyLogDocument, version.document_id)
    if not document:
        raise HTTPException(status_code=409, detail="日志文档不存在")
    auto = DailyLogAutoContent.model_validate_json(version.auto_content)
    valid_keys = {issue.key for entry in auto.entries for issue in entry.issues}
    if document.log_type == "SAFETY":
        unknown = set(manual.hazard_classifications) - valid_keys
        if unknown:
            raise HTTPException(status_code=422, detail="安全问题归类包含无效来源")
        manual = _manual_for_content(document.log_type, auto, manual)
    else:
        manual.hazard_classifications = {}
    before = _snapshot(version)
    version.manual_content = manual.model_dump_json()
    version.updated_by = actor_id
    _audit(db, version, actor_id, "EDITED", before)
    db.commit()
    return version


def confirm_daily_log(db: Session, version: DailyLogVersion, actor_id: int) -> DailyLogVersion:
    if version.status == "CONFIRMED":
        return version
    document = db.get(DailyLogDocument, version.document_id)
    project = db.get(Project, version.project_id)
    if not document or not project:
        raise HTTPException(status_code=409, detail="日志文档不存在")
    if _digest(_confirmed_rows(db, project, document.log_date)) != version.source_digest:
        raise HTTPException(status_code=409, detail="日志存在新的已确认 Event，请先刷新")
    manual = DailyLogManualContent.model_validate_json(version.manual_content)
    if document.log_type == "SAFETY" and any(
        value == "UNCLASSIFIED" for value in manual.hazard_classifications.values()
    ):
        raise HTTPException(status_code=422, detail="请先完成所有安全问题的专业归类")
    before = _snapshot(version)
    version.status = "CONFIRMED"
    version.confirmed_by = actor_id
    version.confirmed_at = datetime.now(UTC)
    version.updated_by = actor_id
    _audit(db, version, actor_id, "CONFIRMED", before)
    db.commit()
    return version


def daily_log_out(db: Session, version: DailyLogVersion) -> DailyLogOut:
    document = db.get(DailyLogDocument, version.document_id)
    project = db.get(Project, version.project_id)
    if not document or not project:
        raise HTTPException(status_code=500, detail="日志数据损坏")
    rows = _confirmed_rows(db, project, document.log_date)
    current_ids = {event.id for event, _record in rows}
    sources = (
        db.query(DailyLogSource).filter_by(version_id=version.id).order_by(DailyLogSource.id).all()
    )
    source_ids = {source.event_id for source in sources}
    audits = (
        db.query(DailyLogAudit)
        .filter_by(version_id=version.id)
        .order_by(DailyLogAudit.created_at, DailyLogAudit.id)
        .all()
    )
    return DailyLogOut(
        id=version.id,
        document_id=document.id,
        project_id=version.project_id,
        project_name=project.name,
        date=document.log_date,
        log_type=document.log_type,
        version=version.version,
        status=version.status,
        auto_content=DailyLogAutoContent.model_validate_json(version.auto_content),
        manual_content=DailyLogManualContent.model_validate_json(version.manual_content),
        stale=_digest(rows) != version.source_digest,
        new_event_count=len(current_ids - source_ids),
        sources=[
            DailyLogSourceOut(
                event_id=source.event_id,
                record_id=source.record_id,
                evidence=json.loads(source.evidence_snapshot),
            )
            for source in sources
        ],
        audits=[
            DailyLogAuditOut(
                id=audit.id,
                actor_id=audit.actor_id,
                action=audit.action,
                created_at=audit.created_at,
            )
            for audit in audits
        ],
        created_by=version.created_by,
        updated_by=version.updated_by,
        confirmed_by=version.confirmed_by,
        confirmed_at=version.confirmed_at,
        created_at=version.created_at,
        updated_at=version.updated_at,
    )


def version_summaries(db: Session, document_id: int) -> list[DailyLogVersionSummary]:
    versions = (
        db.query(DailyLogVersion)
        .filter_by(document_id=document_id)
        .order_by(DailyLogVersion.version.desc())
        .all()
    )
    counts = {
        version.id: db.query(DailyLogSource).filter_by(version_id=version.id).count()
        for version in versions
    }
    return [
        DailyLogVersionSummary(
            id=version.id,
            version=version.version,
            status=version.status,
            source_count=counts[version.id],
            confirmed_at=version.confirmed_at,
            created_at=version.created_at,
        )
        for version in versions
    ]
