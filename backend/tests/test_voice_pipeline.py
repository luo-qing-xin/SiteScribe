import io
import wave
from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.config import settings
from app.models import (
    EventDraft,
    MediaFile,
    Project,
    ProjectMember,
    SiteRecord,
    Task,
    TranscriptionJob,
    User,
)
from app.providers import (
    ASRResult,
    MockEventExtractionProvider,
    OpenAICompatibleEventExtractionProvider,
    ProviderError,
)
from app.schemas import EventConfirmIn, EventPayload
from app.services import _match_members_and_deadlines, confirm_event_draft, relative_deadline


def wav_bytes(seconds: float = 0.2, sample_rate: int = 16_000) -> bytes:
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as output:
        output.setnchannels(1)
        output.setsampwidth(2)
        output.setframerate(sample_rate)
        output.writeframes(b"\x00\x00" * int(seconds * sample_rate))
    return buffer.getvalue()


def create_job(client: TestClient, project_id: int, data: bytes | None = None, name="voice.wav"):
    return client.post(
        "/api/transcription-jobs",
        data={"project_id": str(project_id)},
        files={"audio": (name, data or wav_bytes(), "audio/wav")},
    )


def test_valid_audio_upload_is_probed_normalized_and_transcribed(auth_client, db, project_data):
    project, _, _ = project_data
    response = create_job(auth_client, project.id, name="../../misleading.mp3")
    assert response.status_code == 202
    job = auth_client.get(f"/api/transcription-jobs/{response.json()['id']}").json()
    assert job["status"] == "SUCCEEDED"
    assert job["raw_transcript"] == "这是一段待用户核对的测试转写。"
    assert job["original_audio"]["mime_type"] == "audio/wav"
    assert db.get(MediaFile, job["normalized_audio_media_id"]).stored_name.endswith(".wav")


def test_invalid_audio_oversize_and_duration_are_rejected(auth_client, project_data, monkeypatch):
    project, _, _ = project_data
    invalid = create_job(auth_client, project.id, b"not audio", "fake.wav")
    assert invalid.status_code == 422
    monkeypatch.setattr(settings, "audio_max_bytes", 100)
    oversized = create_job(auth_client, project.id, wav_bytes())
    assert oversized.status_code == 413
    monkeypatch.setattr(settings, "audio_max_bytes", 1024 * 1024)
    monkeypatch.setattr(settings, "audio_max_duration_seconds", 0.05)
    too_long = create_job(auth_client, project.id, wav_bytes(0.2))
    assert too_long.status_code == 413


def test_non_member_upload_and_cross_project_job_access(client, db, project_data):
    project, _, _ = project_data
    other = db.query(Project).filter_by(name="其他项目").one()
    client.post("/api/auth/login", json={"username": "outsider", "password": "demo123"})
    assert create_job(client, project.id).status_code == 403
    outsider_job = create_job(client, other.id)
    assert outsider_job.status_code == 202
    client.post("/api/auth/login", json={"username": "member", "password": "demo123"})
    assert client.get(f"/api/transcription-jobs/{outsider_job.json()['id']}").status_code == 403


def test_asr_failure_retry_and_raw_transcript_is_immutable(auth_client, project_data, monkeypatch):
    from app import services

    project, _, _ = project_data

    class FailingASR:
        name = "test_failure"
        model = "test"

        def transcribe(self, _path):
            raise ProviderError("ASR_TEST_FAILURE", "测试转写失败")

    monkeypatch.setattr(services, "get_asr_provider", lambda: FailingASR())
    created = create_job(auth_client, project.id)
    job_id = created.json()["id"]
    failed = auth_client.get(f"/api/transcription-jobs/{job_id}").json()
    assert failed["status"] == "FAILED"
    assert failed["raw_transcript"] is None
    assert failed["error_code"] == "ASR_TEST_FAILURE"

    class SuccessASR:
        name = "test_success"
        model = "test"

        def transcribe(self, _path):
            return ASRResult("不可覆盖的原始转写", "zh")

    monkeypatch.setattr(services, "get_asr_provider", lambda: SuccessASR())
    assert auth_client.post(f"/api/transcription-jobs/{job_id}/retry").status_code == 200
    edited = auth_client.patch(
        f"/api/transcription-jobs/{job_id}/transcript",
        json={"edited_transcript": "用户单独保存的修订文本"},
    )
    assert edited.status_code == 200
    assert edited.json()["raw_transcript"] == "不可覆盖的原始转写"
    assert edited.json()["edited_transcript"] == "用户单独保存的修订文本"
    forbidden = auth_client.patch(
        f"/api/transcription-jobs/{job_id}/transcript",
        json={"raw_transcript": "恶意覆盖", "edited_transcript": "第二版修订"},
    )
    assert forbidden.status_code == 422
    assert (
        auth_client.get(f"/api/transcription-jobs/{job_id}").json()["raw_transcript"]
        == "不可覆盖的原始转写"
    )


def test_event_schema_bounds_invalid_json_and_missing_facts(monkeypatch):
    with pytest.raises(ValidationError):
        EventPayload.model_validate(
            {
                "schema_version": "1.0",
                "event_type": "general",
                "construction": {"progress_percent": 101},
            }
        )
    result = MockEventExtractionProvider().extract("现场情况正常，没有提供人数或进度。")
    assert result.construction.worker_count is None
    assert result.construction.progress_percent is None

    provider = OpenAICompatibleEventExtractionProvider()
    calls = []
    monkeypatch.setattr(
        provider, "_request", lambda _text, repair: calls.append(repair) or "not json"
    )
    with pytest.raises(ProviderError) as captured:
        provider.extract("测试")
    assert captured.value.code == "EVENT_SCHEMA_INVALID"
    assert calls == [False, True]


def test_member_matching_unique_ambiguous_unmatched_and_project_timezone(db, project_data):
    project, _, member = project_data
    job = TranscriptionJob(
        id="match-job",
        project_id=project.id,
        created_by=member.id,
        status="SUCCEEDED",
        provider="mock",
        model="mock",
        raw_transcript="测试",
        created_at=datetime(2026, 8, 24, 1, 0, tzinfo=UTC),
    )
    db.add(job)
    payload = EventPayload.model_validate(
        {
            "schema_version": "1.0",
            "event_type": "general",
            "construction": {},
            "issues": [
                {
                    "description": "A",
                    "category": "other",
                    "responsible_person_text": "成员",
                    "deadline_text": "明天下午",
                    "evidence_quote": "A",
                },
                {
                    "description": "B",
                    "category": "other",
                    "responsible_person_text": "不存在",
                    "evidence_quote": "B",
                },
            ],
        }
    )
    matched = _match_members_and_deadlines(db, job, payload)
    assert matched.issues[0].candidate_project_member_id == member.id
    assert matched.issues[0].proposed_deadline == datetime(2026, 8, 25, 7, 0, tzinfo=UTC)
    assert matched.issues[1].candidate_project_member_id is None
    duplicate = User(
        username="member2", password_hash="x", name="成员", role="施工员", organization="测试单位"
    )
    db.add(duplicate)
    db.flush()
    db.add(ProjectMember(project_id=project.id, user_id=duplicate.id))
    db.flush()
    payload.issues[0].candidate_project_member_id = None
    assert (
        _match_members_and_deadlines(db, job, payload).issues[0].candidate_project_member_id is None
    )
    assert relative_deadline("明天下午", job.created_at, project) == datetime(
        2026, 8, 25, 7, 0, tzinfo=UTC
    )


def completed_draft(auth_client, project_id):
    created = create_job(auth_client, project_id)
    job_id = created.json()["id"]
    auth_client.patch(
        f"/api/transcription-jobs/{job_id}/transcript",
        json={"edited_transcript": "施工进度大约八成，防护有问题。"},
    )
    draft = auth_client.post(f"/api/transcription-jobs/{job_id}/event-drafts").json()
    return job_id, draft


def confirm_body(project, location, member, event, *, create_task=False):
    return {
        "payload": event,
        "record": {
            "category": "安全巡查",
            "description": "用户确认后的现场描述",
            "occurred_at": datetime.now(UTC).isoformat(),
            "gps_status": "not_requested",
            "location_id": location.id,
        },
        "issues": (
            [
                {
                    "issue_index": 0,
                    "create_task": True,
                    "assignee_id": member.id,
                    "due_at": (datetime.now(UTC) + timedelta(days=1)).isoformat(),
                    "title": "用户确认的待办",
                }
            ]
            if create_task
            else []
        ),
    }


def test_draft_edit_unconfirmed_no_writes_confirm_idempotent_and_task_opt_in(
    auth_client, db, project_data
):
    project, location, member = project_data
    job_id, draft = completed_draft(auth_client, project.id)
    assert draft["status"] == "READY"
    assert db.query(SiteRecord).filter_by(source_type="VOICE_AI").count() == 0
    assert db.query(Task).count() == 0
    event = draft["raw_payload"]
    event["notes"] = "用户修订的结构化备注"
    patched = auth_client.patch(f"/api/event-drafts/{draft['id']}", json={"payload": event})
    assert patched.json()["raw_payload"] != patched.json()["user_corrected_payload"]
    first = auth_client.post(
        f"/api/event-drafts/{draft['id']}/confirm",
        json=confirm_body(project, location, member, event),
    )
    assert first.status_code == 200
    assert first.json()["tasks"] == []
    second = auth_client.post(
        f"/api/event-drafts/{draft['id']}/confirm",
        json=confirm_body(project, location, member, event),
    )
    assert second.json()["record"]["id"] == first.json()["record"]["id"]
    assert db.query(SiteRecord).filter_by(source_type="VOICE_AI").count() == 1
    assert db.query(SiteRecord).filter_by(source_transcription_job_id=job_id).count() == 1
    assert db.query(Task).count() == 0
    assert db.get(TranscriptionJob, job_id).record_id == first.json()["record"]["id"]

    _, second_draft = completed_draft(auth_client, project.id)
    confirmed = auth_client.post(
        f"/api/event-drafts/{second_draft['id']}/confirm",
        json=confirm_body(project, location, member, second_draft["raw_payload"], create_task=True),
    )
    assert confirmed.status_code == 200
    assert len(confirmed.json()["tasks"]) == 1
    assert confirmed.json()["tasks"][0]["source_record_id"] == confirmed.json()["record"]["id"]


def test_confirmation_transaction_rolls_back_on_task_failure(
    auth_client, db, project_data, monkeypatch
):
    from app import services

    project, location, member = project_data
    job_id, draft_data = completed_draft(auth_client, project.id)
    draft = db.get(EventDraft, draft_data["id"])
    job = db.get(TranscriptionJob, job_id)
    request = EventConfirmIn.model_validate(
        confirm_body(project, location, member, draft_data["raw_payload"], create_task=True)
    )
    monkeypatch.setattr(
        services,
        "create_task_item",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(RuntimeError("test rollback")),
    )
    with pytest.raises(RuntimeError):
        confirm_event_draft(db, draft, job, request, member.id)
    assert db.query(SiteRecord).filter_by(source_type="VOICE_AI").count() == 0
    assert db.query(Task).count() == 0
    assert db.get(EventDraft, draft.id).confirmed_record_id is None


def test_delete_orphan_job_cleans_original_and_derived_files(auth_client, db, project_data):
    project, _, _ = project_data
    created = create_job(auth_client, project.id)
    job_id = created.json()["id"]
    paths = [
        settings.upload_dir.parent / media.relative_path
        for media in db.query(MediaFile).filter_by(transcription_job_id=job_id).all()
    ]
    assert all(path.exists() for path in paths)
    assert auth_client.delete(f"/api/transcription-jobs/{job_id}").status_code == 200
    assert all(not path.exists() for path in paths)
    assert db.get(TranscriptionJob, job_id) is None
