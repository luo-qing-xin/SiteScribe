from datetime import UTC, datetime

from app.event_schemas import (
    EventEvidenceRef,
    SiteConstruction,
    SiteEventIssue,
    SiteEventPayload,
)
from app.models import (
    DailyLogSource,
    DailyLogVersion,
    EventExtractionJob,
    Project,
    SiteEvent,
    SiteRecord,
)


def add_confirmed_event(
    db,
    project,
    location,
    member,
    *,
    occurred_at: datetime,
    activity: str = "钢筋绑扎",
    worker_count: int | None = 12,
    with_issue: bool = True,
):
    record = SiteRecord(
        project_id=project.id,
        recorder_id=member.id,
        category="安全巡查",
        description=f"{activity}现场记录",
        occurred_at=occurred_at,
        gps_status="not_requested",
        location_id=location.id,
    )
    db.add(record)
    db.flush()
    evidence = EventEvidenceRef(
        evidence_type="confirmed_transcript",
        source_id=f"record:{record.id}:description",
        quote=record.description,
        confidence=1,
    )
    issues = []
    if with_issue:
        issues.append(
            SiteEventIssue(
                description="材料占用通道",
                category="文明施工/安全",
                responsible_person="李班长",
                confidence=0.9,
                evidence=[evidence],
            )
        )
    payload = SiteEventPayload(
        construction=SiteConstruction(activity=activity, worker_count=worker_count, progress=0.8),
        issues=issues,
        field_evidence={"construction.activity": [evidence]},
        overall_confidence=0.9,
    )
    job = EventExtractionJob(
        id=f"job-{record.id}",
        project_id=project.id,
        record_id=record.id,
        requested_by=member.id,
        status="SUCCEEDED",
        provider="test",
        model="test",
        schema_version="1.0",
        input_snapshot="{}",
    )
    db.add(job)
    db.flush()
    event = SiteEvent(
        id=f"event-{record.id}",
        project_id=project.id,
        source_record_id=record.id,
        extraction_job_id=job.id,
        status="CONFIRMED",
        schema_version="1.0",
        event_type="site_inspection",
        ai_output=payload.model_dump_json(),
        draft_data=payload.model_dump_json(),
        confirmed_data=payload.model_dump_json(),
        evidence_map="{}",
        overall_confidence=0.9,
        confirmed_by=member.id,
        confirmed_at=datetime.now(UTC),
    )
    db.add(event)
    db.commit()
    return record, event


def create_log(client, project_id, log_date, log_type="CONSTRUCTION"):
    return client.post(
        f"/api/projects/{project_id}/daily-logs",
        json={"date": log_date, "log_type": log_type},
    )


def test_project_timezone_confirmed_only_and_exact_mapping(auth_client, db, project_data):
    project, location, member = project_data
    # 16:30 UTC belongs to the next calendar day in Asia/Shanghai.
    add_confirmed_event(
        db,
        project,
        location,
        member,
        occurred_at=datetime(2026, 8, 28, 16, 30, tzinfo=UTC),
    )
    _draft_record, draft_event = add_confirmed_event(
        db,
        project,
        location,
        member,
        occurred_at=datetime(2026, 8, 28, 17, 0, tzinfo=UTC),
        activity="未确认作业",
    )
    draft_event.status = "DRAFT"
    draft_event.confirmed_data = None
    db.commit()
    response = create_log(auth_client, project.id, "2026-08-29")
    assert response.status_code == 201
    body = response.json()
    assert len(body["auto_content"]["entries"]) == 1
    entry = body["auto_content"]["entries"][0]
    assert entry["construction"]["activity"] == "钢筋绑扎"
    assert entry["construction"]["worker_count"] == 12
    assert entry["location"] == {"building": "3号楼", "floor": "6层", "zone": "西侧"}
    assert body["manual_content"]["weather"] == ""
    assert create_log(auth_client, project.id, "2026-08-29").json()["id"] == body["id"]


def test_safety_requires_professional_classification(auth_client, db, project_data):
    project, location, member = project_data
    _record, event = add_confirmed_event(
        db,
        project,
        location,
        member,
        occurred_at=datetime(2026, 8, 29, 2, 0, tzinfo=UTC),
    )
    body = create_log(auth_client, project.id, "2026-08-29", "SAFETY").json()
    issue_key = f"{event.id}:0"
    assert body["manual_content"]["hazard_classifications"][issue_key] == "UNCLASSIFIED"
    blocked = auth_client.post(f"/api/daily-logs/{body['id']}/confirm")
    assert blocked.status_code == 422
    manual = body["manual_content"]
    manual["hazard_classifications"][issue_key] = "GENERAL"
    saved = auth_client.patch(f"/api/daily-logs/{body['id']}", json={"manual_content": manual})
    assert saved.status_code == 200
    confirmed = auth_client.post(f"/api/daily-logs/{body['id']}/confirm")
    assert confirmed.status_code == 200
    assert confirmed.json()["status"] == "CONFIRMED"


def test_refresh_preserves_manual_data_and_confirmed_version(auth_client, db, project_data):
    project, location, member = project_data
    first_record, _event = add_confirmed_event(
        db,
        project,
        location,
        member,
        occurred_at=datetime(2026, 8, 29, 1, 0, tzinfo=UTC),
        with_issue=False,
    )
    body = create_log(auth_client, project.id, "2026-08-29").json()
    manual = body["manual_content"]
    manual["weather"] = "晴（成员人工填写）"
    auth_client.patch(f"/api/daily-logs/{body['id']}", json={"manual_content": manual})
    auth_client.post(f"/api/daily-logs/{body['id']}/confirm")
    add_confirmed_event(
        db,
        project,
        location,
        member,
        occurred_at=datetime(2026, 8, 29, 3, 0, tzinfo=UTC),
        activity="模板安装",
        worker_count=5,
        with_issue=False,
    )
    stale = auth_client.get(f"/api/daily-logs/{body['id']}").json()
    assert stale["stale"] is True
    assert stale["new_event_count"] == 1
    refreshed = auth_client.post(f"/api/daily-logs/{body['id']}/refresh").json()
    assert refreshed["id"] != body["id"]
    assert refreshed["version"] == 2
    assert refreshed["status"] == "DRAFT"
    assert refreshed["manual_content"]["weather"] == "晴（成员人工填写）"
    assert len(refreshed["auto_content"]["entries"]) == 2
    old = auth_client.get(f"/api/daily-logs/{body['id']}").json()
    assert old["status"] == "CONFIRMED"
    assert len(old["auto_content"]["entries"]) == 1
    assert db.get(SiteRecord, first_record.id)


def test_auth_isolation_and_referenced_record_delete_blocked(auth_client, client, db, project_data):
    project, location, member = project_data
    record, _event = add_confirmed_event(
        db,
        project,
        location,
        member,
        occurred_at=datetime(2026, 8, 29, 1, 0, tzinfo=UTC),
    )
    log = create_log(auth_client, project.id, "2026-08-29").json()
    assert db.query(DailyLogSource).filter_by(version_id=log["id"]).count() == 1
    blocked = auth_client.delete(f"/api/records/{record.id}")
    assert blocked.status_code == 409
    auth_client.post("/api/auth/logout")
    client.post("/api/auth/login", json={"username": "outsider", "password": "demo123"})
    assert client.get(f"/api/daily-logs/{log['id']}").status_code == 403
    other_project = db.query(Project).filter_by(name="其他项目").one()
    assert create_log(client, other_project.id, "2026-08-29").status_code == 201
    assert db.query(DailyLogVersion).count() == 2
