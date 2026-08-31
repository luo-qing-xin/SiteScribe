import io
from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient
from PIL import Image
from pydantic import ValidationError

from app.event_schemas import SiteEventPayload
from app.models import (
    EventExtractionJob,
    EventRevision,
    MediaFile,
    Project,
    ProjectLocation,
    SiteEvent,
    SiteRecord,
    Task,
    User,
)
from app.providers import ProviderError
from app.site_event_extractor import OpenAIEventExtractor, PreparedImage

DEMO_TEXT = (
    "今天3号楼六层钢筋绑扎完成大约80%，现场12名钢筋工。"
    "西侧材料堆放比较乱，影响通道，通知李班长今天下午处理。"
)


def record_payload(project, location, description=DEMO_TEXT):
    return {
        "project_id": project.id,
        "category": "安全巡查",
        "description": description,
        "occurred_at": datetime.now(UTC).isoformat(),
        "gps_status": "not_requested",
        "location_id": location.id,
    }


def create_record(client: TestClient, project, location, description=DEMO_TEXT) -> int:
    response = client.post("/api/records", json=record_payload(project, location, description))
    assert response.status_code == 201
    return response.json()["id"]


def png_bytes() -> bytes:
    buffer = io.BytesIO()
    Image.new("RGB", (20, 12), "#087354").save(buffer, format="PNG")
    return buffer.getvalue()


def extract(client: TestClient, record_id: int):
    created = client.post(f"/api/records/{record_id}/event-extractions")
    assert created.status_code == 202
    job = client.get(f"/api/event-extraction-jobs/{created.json()['id']}")
    return created, job


def test_requires_login_and_project_membership(client, auth_client, db, project_data):
    project, location, member = project_data
    record_id = create_record(auth_client, project, location)
    auth_client.post("/api/auth/logout")
    assert client.post(f"/api/records/{record_id}/event-extractions").status_code == 401

    other = db.query(Project).filter_by(name="其他项目").one()
    outsider = db.query(User).filter_by(username="outsider").one()
    other_location = ProjectLocation(
        project_id=other.id, building="1号楼", floor="1层", zone="东侧"
    )
    db.add(other_location)
    db.flush()
    other_record = SiteRecord(
        project_id=other.id,
        recorder_id=outsider.id,
        category="安全巡查",
        description="其他项目人工描述",
        occurred_at=datetime.now(UTC),
        gps_status="not_requested",
        location_id=other_location.id,
    )
    db.add(other_record)
    db.commit()
    client.post("/api/auth/login", json={"username": "member", "password": "demo123"})
    assert client.get(f"/api/records/{other_record.id}/event").status_code == 403
    assert client.post(f"/api/records/{other_record.id}/event-extractions").status_code == 403


def test_missing_confirmed_text_is_rejected(auth_client, db, project_data):
    project, location, member = project_data
    record = SiteRecord(
        project_id=project.id,
        recorder_id=member.id,
        category="安全巡查",
        description="",
        occurred_at=datetime.now(UTC),
        gps_status="not_requested",
        location_id=location.id,
    )
    db.add(record)
    db.commit()
    state = auth_client.get(f"/api/records/{record.id}/event").json()
    assert state["can_extract"] is False
    assert "人工确认文本" in state["unavailable_reason"]
    assert auth_client.post(f"/api/records/{record.id}/event-extractions").status_code == 409


def test_mock_extraction_demo_and_text_only_fallback(auth_client, db, project_data):
    project, location, _member = project_data
    record_id = create_record(auth_client, project, location)
    created, job = extract(auth_client, record_id)
    assert created.status_code == 202
    assert job.json()["status"] == "SUCCEEDED"
    state = auth_client.get(f"/api/records/{record_id}/event").json()
    payload = state["event"]["ai_output"]
    assert payload["construction"] == {
        "activity": "钢筋绑扎",
        "crew": None,
        "worker_count": 12,
        "progress": 0.8,
    }
    assert payload["issues"][0]["description"] == "材料堆放影响通道"
    assert payload["issues"][0]["responsible_person"] == "李班长"
    assert payload["issues"][0]["risk_level"] == "pending_confirmation"
    assert payload["issues"][0]["due_at"] is None
    assert payload["field_evidence"]
    snapshot = db.get(EventExtractionJob, job.json()["id"]).input_snapshot
    assert '"photo_ids":[]' in snapshot


def test_schema_rejects_out_of_range_and_negative_values():
    with pytest.raises(ValidationError):
        SiteEventPayload.model_validate(
            {"construction": {"progress": 1.01}, "overall_confidence": 0.8}
        )
    with pytest.raises(ValidationError):
        SiteEventPayload.model_validate(
            {"construction": {"worker_count": -1}, "overall_confidence": 0.8}
        )


def test_invalid_and_foreign_photo_evidence_is_removed_with_warning(
    auth_client, db, project_data, monkeypatch
):
    from app import site_event_service
    from app.event_schemas import EventEvidenceRef, SiteConstruction, SiteEventPayload
    from app.site_event_extractor import ExtractionResult

    project, location, _member = project_data
    first_id = create_record(auth_client, project, location, "钢筋绑扎完成。")
    second_id = create_record(auth_client, project, location, "另一个记录。")
    upload = auth_client.post(
        f"/api/records/{second_id}/photos",
        files={"files": ("other.png", png_bytes(), "image/png")},
    )
    foreign_id = upload.json()[0]["id"]

    class ForgingProvider:
        name = "test"
        model = "test"

        def extract(self, snapshot, images):
            ref = EventEvidenceRef(
                evidence_type="photo",
                source_id=f"media:{foreign_id}",
                media_file_id=foreign_id,
                description="另一记录的图片",
                confidence=0.9,
            )
            return ExtractionResult(
                payload=SiteEventPayload(
                    construction=SiteConstruction(activity="钢筋绑扎"),
                    field_evidence={"construction.activity": [ref]},
                    overall_confidence=0.9,
                ),
                response_metadata={},
            )

    monkeypatch.setattr(site_event_service, "get_site_event_extractor", lambda: ForgingProvider())
    _created, job = extract(auth_client, first_id)
    assert job.json()["status"] == "SUCCEEDED"
    event = auth_client.get(f"/api/records/{first_id}/event").json()["event"]
    payload = event["draft_data"]
    assert payload["field_evidence"] == {}
    assert "construction.activity" in payload["needs_confirmation_fields"]
    assert any("media_file_id" in warning for warning in payload["warnings"])
    assert (
        event["ai_output"]["field_evidence"]["construction.activity"][0]["media_file_id"]
        == foreign_id
    )


@pytest.mark.parametrize(
    ("code", "message"),
    [
        ("EVENT_TIMEOUT", "Event 抽取超时，请稍后重试"),
        ("EVENT_INVALID_JSON", "Event 抽取服务返回了无效 JSON"),
        ("EVENT_SCHEMA_MISMATCH", "Event 抽取结果不符合 Schema"),
    ],
)
def test_provider_failures_are_safe(auth_client, project_data, monkeypatch, code, message):
    from app import site_event_service

    project, location, _member = project_data
    record_id = create_record(auth_client, project, location)

    class FailingProvider:
        name = "test"
        model = "test"

        def extract(self, snapshot, images):
            raise ProviderError(code, message)

    monkeypatch.setattr(site_event_service, "get_site_event_extractor", lambda: FailingProvider())
    _created, job = extract(auth_client, record_id)
    assert job.json()["status"] == "FAILED"
    assert job.json()["error_code"] == code
    assert job.json()["error_message"] == message
    assert auth_client.get(f"/api/records/{record_id}/event").json()["event"] is None


def test_active_job_is_idempotent(auth_client, db, project_data):
    from app.site_event_service import build_input_snapshot

    project, location, member = project_data
    record_id = create_record(auth_client, project, location)
    record = db.get(SiteRecord, record_id)
    job = EventExtractionJob(
        id="active-job",
        project_id=project.id,
        record_id=record_id,
        requested_by=member.id,
        status="RUNNING",
        provider="mock",
        model="mock",
        schema_version="1.0",
        input_snapshot=__import__("json").dumps(build_input_snapshot(db, record)),
    )
    db.add(job)
    db.commit()
    response = auth_client.post(f"/api/records/{record_id}/event-extractions")
    assert response.status_code == 202
    assert response.json()["id"] == "active-job"
    assert db.query(EventExtractionJob).filter_by(record_id=record_id).count() == 1


def test_edit_confirm_audit_preserves_ai_and_creates_no_task(auth_client, db, project_data):
    project, location, member = project_data
    record_id = create_record(auth_client, project, location)
    _created, job = extract(auth_client, record_id)
    event = auth_client.get(f"/api/records/{record_id}/event").json()["event"]
    original = event["ai_output"]
    edited = event["draft_data"]
    edited["construction"]["activity"] = "人工修订的钢筋作业"
    patched = auth_client.patch(f"/api/events/{event['id']}", json={"payload": edited})
    assert patched.status_code == 200
    assert patched.json()["ai_output"] == original
    assert patched.json()["draft_data"]["construction"]["activity"] == "人工修订的钢筋作业"
    assert db.query(EventRevision).filter_by(event_id=event["id"], action="EDITED").count() == 1

    confirmed = auth_client.post(f"/api/events/{event['id']}/confirm")
    assert confirmed.status_code == 200
    body = confirmed.json()
    assert body["status"] == "CONFIRMED"
    assert body["confirmed_by"] == member.id
    assert body["confirmed_at"]
    assert body["confirmed_data"]["construction"]["activity"] == "人工修订的钢筋作业"
    assert body["ai_output"] == original
    assert db.query(Task).count() == 0
    assert auth_client.post(f"/api/records/{record_id}/event-extractions").status_code == 409
    assert db.get(EventExtractionJob, job.json()["id"]).result_event_id == event["id"]


def test_reject_and_retry_preserve_original_results(auth_client, db, project_data):
    project, location, _member = project_data
    record_id = create_record(auth_client, project, location)
    _created, _job = extract(auth_client, record_id)
    event = auth_client.get(f"/api/records/{record_id}/event").json()["event"]
    rejected = auth_client.post(f"/api/events/{event['id']}/reject", json={"reason": "证据不足"})
    assert rejected.status_code == 200
    assert rejected.json()["status"] == "REJECTED"
    assert rejected.json()["ai_output"] == event["ai_output"]
    assert db.get(SiteEvent, event["id"]).ai_output


def test_photo_is_preprocessed_without_modifying_original(auth_client, db, project_data):
    project, location, _member = project_data
    record_id = create_record(auth_client, project, location)
    upload = auth_client.post(
        f"/api/records/{record_id}/photos",
        files={"files": ("site.png", png_bytes(), "image/png")},
    )
    media = db.get(MediaFile, upload.json()[0]["id"])
    original_path = (
        __import__("app.config", fromlist=["settings"]).settings.upload_dir / media.stored_name
    )
    before = original_path.read_bytes()
    _created, job = extract(auth_client, record_id)
    assert job.json()["status"] == "SUCCEEDED"
    assert original_path.read_bytes() == before


def test_openai_provider_sends_structured_multimodal_request(monkeypatch):
    from app.config import settings

    monkeypatch.setattr(settings, "event_extraction_model", "configured-multimodal-model")
    monkeypatch.setattr(settings, "openai_api_key", "test-secret")
    provider = OpenAIEventExtractor()
    captured = {}

    class Response:
        def json(self):
            payload = SiteEventPayload(overall_confidence=0.5)
            return {
                "choices": [{"message": {"content": payload.model_dump_json()}}],
                "usage": {"prompt_tokens": 10, "completion_tokens": 5, "ignored": "value"},
            }

    def request(body):
        captured.update(body)
        return Response()

    monkeypatch.setattr(provider, "_request", request)
    snapshot = {
        "confirmed_text": {"text": "人工确认文本", "source_id": "record:1:description"},
        "location": {
            "source_id": "location:1",
            "building": "3号楼",
            "floor": "6层",
            "zone": "西侧",
        },
        "record_metadata": {"source_id": "record:1", "record_id": 1},
        "photo_ids": [7],
    }
    result = provider.extract(
        snapshot,
        [
            PreparedImage(
                media_file_id=7, mime_type="image/jpeg", data_url="data:image/jpeg;base64,AA=="
            )
        ],
    )
    assert captured["model"] == "configured-multimodal-model"
    assert captured["response_format"]["type"] == "json_schema"
    assert captured["response_format"]["json_schema"]["strict"] is True
    content = captured["messages"][1]["content"]
    assert content[1]["image_url"]["url"].startswith("data:image/jpeg;base64,")
    assert result.response_metadata["usage"] == {"prompt_tokens": 10, "completion_tokens": 5}


def test_record_delete_cascades_event_audit_without_touching_other_data(
    auth_client, db, project_data
):
    project, location, _member = project_data
    record_id = create_record(auth_client, project, location)
    _created, _job = extract(auth_client, record_id)
    event_id = auth_client.get(f"/api/records/{record_id}/event").json()["event"]["id"]
    response = auth_client.delete(f"/api/records/{record_id}")
    assert response.status_code == 200
    assert db.get(SiteRecord, record_id) is None
    assert db.get(SiteEvent, event_id) is None
    assert db.query(EventExtractionJob).filter_by(record_id=record_id).count() == 0


def test_photo_referenced_by_event_cannot_be_deleted_independently(
    auth_client, project_data, monkeypatch
):
    from app import site_event_service
    from app.event_schemas import EventEvidenceRef, SiteConstruction
    from app.site_event_extractor import ExtractionResult

    project, location, _member = project_data
    record_id = create_record(auth_client, project, location, "现场照片显示明确作业。")
    photo_id = auth_client.post(
        f"/api/records/{record_id}/photos",
        files={"files": ("evidence.png", png_bytes(), "image/png")},
    ).json()[0]["id"]

    class PhotoProvider:
        name = "test"
        model = "test"

        def extract(self, snapshot, images):
            ref = EventEvidenceRef(
                evidence_type="photo",
                source_id=f"media:{photo_id}",
                media_file_id=photo_id,
                description="当前记录照片",
                confidence=0.8,
            )
            return ExtractionResult(
                payload=SiteEventPayload(
                    construction=SiteConstruction(activity="现场作业"),
                    field_evidence={"construction.activity": [ref]},
                    overall_confidence=0.8,
                ),
                response_metadata={},
            )

    monkeypatch.setattr(site_event_service, "get_site_event_extractor", lambda: PhotoProvider())
    _created, job = extract(auth_client, record_id)
    assert job.json()["status"] == "SUCCEEDED"
    response = auth_client.delete(f"/api/photos/{photo_id}")
    assert response.status_code == 409
    assert "Event 证据" in response.json()["detail"]
