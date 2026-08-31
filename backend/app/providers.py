import json
import re
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

import httpx
from pydantic import ValidationError

from .config import settings
from .schemas import ConstructionEvent, EventIssue, EventPayload


class ProviderError(Exception):
    def __init__(self, code: str, safe_message: str):
        super().__init__(safe_message)
        self.code = code
        self.safe_message = safe_message


@dataclass(frozen=True)
class ASRResult:
    transcript: str
    detected_language: str | None


class ASRProvider(Protocol):
    name: str
    model: str

    def transcribe(self, audio_path: Path) -> ASRResult: ...


class MockASRProvider:
    name = "mock"
    model = "mock-asr-v1"

    def transcribe(self, audio_path: Path) -> ASRResult:
        if not audio_path.is_file():
            raise ProviderError("ASR_INPUT_MISSING", "待转写音频不存在")
        return ASRResult("这是一段待用户核对的测试转写。", "zh")


class FasterWhisperASRProvider:
    name = "faster_whisper"
    _models: dict[tuple[str, str, str], object] = {}
    _lock = threading.Lock()

    def __init__(self) -> None:
        self.model = settings.asr_model

    def _model(self):
        key = (settings.asr_model, settings.asr_device, settings.asr_compute_type)
        with self._lock:
            if key not in self._models:
                try:
                    from faster_whisper import WhisperModel
                except ImportError as exc:
                    raise ProviderError(
                        "ASR_PROVIDER_UNAVAILABLE", "语音识别组件尚未安装，请联系管理员"
                    ) from exc
                self._models[key] = WhisperModel(
                    settings.asr_model,
                    device=settings.asr_device,
                    compute_type=settings.asr_compute_type,
                )
        return self._models[key]

    def transcribe(self, audio_path: Path) -> ASRResult:
        try:
            segments, info = self._model().transcribe(
                str(audio_path), language=settings.asr_default_language or None, vad_filter=True
            )
            transcript = "".join(segment.text for segment in segments).strip()
        except ProviderError:
            raise
        except Exception as exc:
            raise ProviderError("ASR_FAILED", "语音识别失败，请稍后重试") from exc
        if not transcript:
            raise ProviderError("ASR_EMPTY", "未识别到清晰语音，请重新录制")
        return ASRResult(transcript, getattr(info, "language", None))


class EventExtractionProvider(Protocol):
    name: str
    model: str

    def extract(self, transcript: str) -> EventPayload: ...


class MockEventExtractionProvider:
    name = "mock"
    model = "mock-event-v1"

    def extract(self, transcript: str) -> EventPayload:
        source = "edited_transcript"
        progress = None
        progress_quote = None
        match = re.search(r"(?:大约|约)?([一二三四五六七八九])成", transcript)
        if match:
            progress = "一二三四五六七八九".index(match.group(1)) * 10 + 10
            progress_quote = match.group(0)
        numeric = re.search(r"(\d{1,3})%", transcript)
        if numeric and int(numeric.group(1)) <= 100:
            progress, progress_quote = float(numeric.group(1)), numeric.group(0)
        event_type = "general"
        if any(word in transcript for word in ("进度", "施工", "绑扎", "浇筑")):
            event_type = "construction_progress"
        elif any(word in transcript for word in ("安全", "防护", "隐患")):
            event_type = "safety_inspection"
        elif any(word in transcript for word in ("质量", "验收", "垂直度")):
            event_type = "quality_inspection"
        issue = None
        issue_match = re.search(r"([^。！？]*(?:问题|未|缺少|损坏|松动)[^。！？]*)", transcript)
        if issue_match:
            quote = issue_match.group(1).strip("，, ")
            issue = EventIssue(
                description=quote,
                category="safety" if any(x in quote for x in ("安全", "防护", "隐患")) else "other",
                evidence_quote=quote,
            )
        evidence = {}
        if progress_quote:
            evidence["construction.progress_percent"] = [
                {"source_type": source, "quote": progress_quote}
            ]
        if issue:
            evidence["issues.0.description"] = [
                {"source_type": source, "quote": issue.evidence_quote}
            ]
        return EventPayload(
            event_type=event_type,
            construction=ConstructionEvent(progress_percent=progress),
            issues=[issue] if issue else [],
            notes=transcript,
            missing_fields=["construction.activity"]
            if event_type == "construction_progress"
            else [],
            warnings=["AI 内容仅为草稿，请逐项核对"],
            field_evidence=evidence,
        )


SYSTEM_PROMPT = """你是施工现场信息抽取器。只提取转写中明确出现的事实；没有证据必须为 null。
输出单个 JSON 对象并严格符合 schema_version 1.0。AI 输出只是待人工确认草稿。
不得推断人数、责任人或事故等级，不得提出停工意见。每个非空事实需在 field_evidence 中提供原文。
issues 中 needs_confirmation 必须为 true。不要输出置信度。"""


class OpenAICompatibleEventExtractionProvider:
    name = "openai_compatible"

    def __init__(self) -> None:
        self.model = settings.event_extraction_model

    def _request(self, transcript: str, repair: bool) -> str:
        if (
            not settings.event_extraction_base_url
            or not settings.event_extraction_api_key
            or not self.model
        ):
            raise ProviderError("EVENT_PROVIDER_NOT_CONFIGURED", "智能抽取服务尚未配置")
        user_text = f"转写文本：\n{transcript}"
        if repair:
            user_text += "\n上次输出无法通过 Schema 校验。请仅返回修正后的 JSON，不添加说明。"
        url = f"{settings.event_extraction_base_url.rstrip('/')}/chat/completions"
        try:
            response = httpx.post(
                url,
                headers={"Authorization": f"Bearer {settings.event_extraction_api_key}"},
                json={
                    "model": self.model,
                    "temperature": 0,
                    "response_format": {"type": "json_object"},
                    "messages": [
                        {"role": "system", "content": SYSTEM_PROMPT},
                        {"role": "user", "content": user_text},
                    ],
                },
                timeout=settings.event_extraction_timeout_seconds,
            )
            response.raise_for_status()
            return response.json()["choices"][0]["message"]["content"]
        except (httpx.HTTPError, KeyError, TypeError, ValueError) as exc:
            raise ProviderError("EVENT_PROVIDER_FAILED", "智能抽取服务暂时不可用，请重试") from exc

    def extract(self, transcript: str) -> EventPayload:
        last_error: Exception | None = None
        for repair in (False, True):
            try:
                return EventPayload.model_validate(json.loads(self._request(transcript, repair)))
            except (json.JSONDecodeError, ValidationError) as exc:
                last_error = exc
        raise ProviderError("EVENT_SCHEMA_INVALID", "智能抽取结果格式无效，请重试") from last_error


def get_asr_provider() -> ASRProvider:
    if settings.asr_provider == "mock":
        return MockASRProvider()
    if settings.asr_provider == "faster_whisper":
        return FasterWhisperASRProvider()
    raise ProviderError("ASR_PROVIDER_UNKNOWN", "语音识别服务配置无效")


def get_event_provider() -> EventExtractionProvider:
    if settings.event_extraction_provider == "mock":
        return MockEventExtractionProvider()
    if settings.event_extraction_provider == "openai_compatible":
        return OpenAICompatibleEventExtractionProvider()
    raise ProviderError("EVENT_PROVIDER_UNKNOWN", "智能抽取服务配置无效")
