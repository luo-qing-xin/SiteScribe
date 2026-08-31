import json
from datetime import UTC, datetime
from uuid import uuid4

from sqlalchemy.orm import Session

from .event_schemas import SiteEventPayload
from .models import Issue, ProjectLocation, SiteEvent, SiteRecord

RAG_CATEGORIES = {"安全", "文明施工/安全"}


def sync_event_issues(db: Session, event: SiteEvent) -> list[Issue]:
    """Freeze eligible confirmed Event issues without altering original Event content."""
    if event.status != "CONFIRMED" or not event.confirmed_data:
        return []
    payload = SiteEventPayload.model_validate_json(event.confirmed_data)
    record = db.get(SiteRecord, event.source_record_id)
    location = db.get(ProjectLocation, record.location_id) if record else None
    location_snapshot = json.dumps(
        {
            "building": location.building if location else None,
            "floor": location.floor if location else None,
            "zone": location.zone if location else None,
        },
        ensure_ascii=False,
    )
    created: list[Issue] = []
    for index, source_issue in enumerate(payload.issues):
        if source_issue.category not in RAG_CATEGORIES:
            continue
        existing = db.query(Issue).filter_by(event_id=event.id, issue_index=index).first()
        if existing:
            created.append(existing)
            continue
        item = Issue(
            id=str(uuid4()),
            project_id=event.project_id,
            event_id=event.id,
            record_id=event.source_record_id,
            issue_index=index,
            category=source_issue.category,
            description_snapshot=source_issue.description,
            location_snapshot=location_snapshot,
            evidence_snapshot=json.dumps(
                [e.model_dump(mode="json") for e in source_issue.evidence], ensure_ascii=False
            ),
            event_snapshot=event.confirmed_data,
            occurred_at=record.occurred_at if record else event.confirmed_at or datetime.now(UTC),
            status="PENDING_ANALYSIS",
        )
        db.add(item)
        created.append(item)
    db.flush()
    return created
