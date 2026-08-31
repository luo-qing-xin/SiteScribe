import io
from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

from fastapi.testclient import TestClient
from PIL import Image

from app.config import settings
from app.models import MediaFile, Project, SiteRecord


def record_payload(project, location, *, with_gps=False):
    payload = {
        "project_id": project.id,
        "category": "安全巡查",
        "description": "用户输入的原始现场描述",
        "occurred_at": datetime.now(UTC).isoformat(),
        "gps_status": "not_requested",
        "location_id": location.id,
    }
    if with_gps:
        payload.update(
            gps_status="success",
            latitude=23.1291,
            longitude=113.2644,
            gps_accuracy=8.5,
            gps_captured_at=datetime.now(UTC).isoformat(),
        )
    return payload


def make_png() -> bytes:
    buffer = io.BytesIO()
    Image.new("RGB", (12, 12), "#087354").save(buffer, format="PNG")
    return buffer.getvalue()


def test_login_success_failure_and_logout(client: TestClient):
    failed = client.post("/api/auth/login", json={"username": "member", "password": "wrong"})
    assert failed.status_code == 401
    response = client.post("/api/auth/login", json={"username": "member", "password": "demo123"})
    assert response.status_code == 200
    assert "password_hash" not in response.text
    assert client.get("/api/auth/me").status_code == 200
    assert client.post("/api/auth/logout").status_code == 200
    assert client.get("/api/auth/me").status_code == 401


def test_protected_api_requires_login(client: TestClient):
    assert client.get("/api/projects").status_code == 401


def test_project_member_permission(client: TestClient, db, project_data):
    other = db.query(Project).filter_by(name="其他项目").one()
    client.post("/api/auth/login", json={"username": "member", "password": "demo123"})
    response = client.get(f"/api/projects/{other.id}")
    assert response.status_code == 403


def test_dashboard_uses_project_timezone_and_exposes_workflow_metrics(
    auth_client: TestClient, db, project_data
):
    project, location, member = project_data
    project.timezone = "Asia/Shanghai"
    local_now = datetime.now(UTC).astimezone(ZoneInfo(project.timezone))
    local_midnight = local_now.replace(hour=0, minute=0, second=0, microsecond=0)
    today_start = local_midnight.astimezone(UTC)
    db.add_all(
        [
            SiteRecord(
                project_id=project.id,
                recorder_id=member.id,
                category="安全巡查",
                description="项目本地今日记录",
                occurred_at=today_start + timedelta(minutes=10),
                gps_status="not_requested",
                location_id=location.id,
            ),
            SiteRecord(
                project_id=project.id,
                recorder_id=member.id,
                category="安全巡查",
                description="项目本地昨日记录",
                occurred_at=today_start - timedelta(minutes=10),
                gps_status="not_requested",
                location_id=location.id,
            ),
        ]
    )
    db.commit()
    payload = auth_client.get(f"/api/projects/{project.id}/dashboard").json()
    assert payload["today_records"] == 1
    assert payload["confirmed_events"] == 0
    assert payload["pending_issues"] == 0
    assert payload["waiting_review_rectifications"] == 0
    assert payload["closed_rectifications_today"] == 0


def test_create_record_with_and_without_gps(auth_client: TestClient, project_data):
    project, location, _ = project_data
    no_gps = auth_client.post("/api/records", json=record_payload(project, location))
    assert no_gps.status_code == 201
    assert no_gps.json()["latitude"] is None
    assert no_gps.json()["description"] == "用户输入的原始现场描述"
    gps = auth_client.post("/api/records", json=record_payload(project, location, with_gps=True))
    assert gps.status_code == 201
    assert gps.json()["gps_status"] == "success"


def test_upload_valid_image_and_reject_invalid(auth_client: TestClient, project_data):
    project, location, _ = project_data
    record_id = auth_client.post("/api/records", json=record_payload(project, location)).json()[
        "id"
    ]
    uploaded = auth_client.post(
        f"/api/records/{record_id}/photos",
        files={"files": ("../../unsafe.png", make_png(), "image/png")},
    )
    assert uploaded.status_code == 201
    photo = uploaded.json()[0]
    assert photo["mime_type"] == "image/png"
    assert "unsafe" not in photo["content_url"]
    assert auth_client.get(photo["content_url"]).status_code == 200
    invalid = auth_client.post(
        f"/api/records/{record_id}/photos",
        files={"files": ("fake.jpg", b"not an image", "image/jpeg")},
    )
    assert invalid.status_code == 422


def test_reject_oversized_photo(auth_client: TestClient, project_data):
    project, location, _ = project_data
    record_id = auth_client.post("/api/records", json=record_payload(project, location)).json()[
        "id"
    ]
    response = auth_client.post(
        f"/api/records/{record_id}/photos",
        files={"files": ("large.png", b"x" * (10 * 1024 * 1024 + 1), "image/png")},
    )
    assert response.status_code == 413


def test_linked_task_and_status_update(auth_client: TestClient, project_data):
    project, location, member = project_data
    record_id = auth_client.post("/api/records", json=record_payload(project, location)).json()[
        "id"
    ]
    task = auth_client.post(
        "/api/tasks",
        json={
            "project_id": project.id,
            "source_record_id": record_id,
            "assignee_id": member.id,
            "title": "完成临边检查",
            "description": "按现场要求复查并留痕",
            "due_at": (datetime.now(UTC) + timedelta(days=1)).isoformat(),
            "status": "待处理",
        },
    )
    assert task.status_code == 201
    assert task.json()["source_record_id"] == record_id
    updated = auth_client.patch(f"/api/tasks/{task.json()['id']}", json={"status": "处理中"})
    assert updated.status_code == 200
    assert updated.json()["status"] == "处理中"


def test_delete_record_cleans_media(auth_client: TestClient, db, project_data):
    project, location, _ = project_data
    record_id = auth_client.post("/api/records", json=record_payload(project, location)).json()[
        "id"
    ]
    auth_client.post(
        f"/api/records/{record_id}/photos", files={"files": ("photo.png", make_png(), "image/png")}
    )
    media = db.query(MediaFile).filter_by(site_record_id=record_id).one()
    path = settings.upload_dir / media.stored_name
    assert path.exists()
    response = auth_client.delete(f"/api/records/{record_id}")
    assert response.status_code == 200
    assert not path.exists()
    assert db.get(SiteRecord, record_id) is None
