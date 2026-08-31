import json
import subprocess
from dataclasses import dataclass
from pathlib import Path
from uuid import uuid4

from fastapi import UploadFile

from .config import settings


@dataclass
class AudioError(Exception):
    code: str
    message: str
    status_code: int = 422


@dataclass(frozen=True)
class AudioInfo:
    duration_seconds: float
    extension: str
    mime_type: str


def _run(command: list[str], timeout: float = 45) -> subprocess.CompletedProcess[str]:
    try:
        return subprocess.run(command, capture_output=True, text=True, timeout=timeout, check=False)
    except FileNotFoundError as exc:
        raise AudioError(
            "AUDIO_TOOL_UNAVAILABLE", "服务器音频处理组件不可用，请联系管理员", 503
        ) from exc
    except subprocess.TimeoutExpired as exc:
        raise AudioError("AUDIO_TOOL_TIMEOUT", "音频检查超时，请缩短录音后重试") from exc


def probe_audio(path: Path) -> AudioInfo:
    result = _run(
        [
            settings.ffprobe_bin,
            "-v",
            "error",
            "-show_entries",
            "format=duration,format_name:stream=codec_type,codec_name",
            "-of",
            "json",
            str(path),
        ]
    )
    if result.returncode:
        raise AudioError("INVALID_AUDIO", "文件不是可解码的受支持音频")
    try:
        payload = json.loads(result.stdout)
        streams = [item for item in payload.get("streams", []) if item.get("codec_type") == "audio"]
        duration = float(payload["format"]["duration"])
        format_names = set(payload["format"].get("format_name", "").split(","))
    except (KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
        raise AudioError("INVALID_AUDIO", "无法读取音频信息") from exc
    if not streams or duration <= 0:
        raise AudioError("INVALID_AUDIO", "文件中没有有效音轨")
    if duration > settings.audio_max_duration_seconds:
        raise AudioError(
            "AUDIO_TOO_LONG",
            f"录音不能超过 {int(settings.audio_max_duration_seconds)} 秒",
            413,
        )
    if "wav" in format_names:
        return AudioInfo(duration, ".wav", "audio/wav")
    if "mp3" in format_names:
        return AudioInfo(duration, ".mp3", "audio/mpeg")
    if format_names.intersection({"webm", "matroska"}):
        return AudioInfo(duration, ".webm", "audio/webm")
    if "ogg" in format_names:
        return AudioInfo(duration, ".ogg", "audio/ogg")
    if format_names.intersection({"mov", "mp4", "m4a", "3gp"}):
        return AudioInfo(duration, ".m4a", "audio/mp4")
    if "aac" in format_names:
        return AudioInfo(duration, ".aac", "audio/aac")
    raise AudioError("UNSUPPORTED_AUDIO", "仅支持 WebM、MP4/M4A/AAC、OGG、WAV 或 MP3 音频")


def save_and_validate_upload(upload: UploadFile) -> tuple[Path, AudioInfo, int]:
    settings.upload_dir.mkdir(parents=True, exist_ok=True)
    temporary = settings.upload_dir / f"{uuid4().hex}.audio-upload"
    total = 0
    try:
        with temporary.open("wb") as destination:
            while chunk := upload.file.read(1024 * 1024):
                total += len(chunk)
                if total > settings.audio_max_bytes:
                    raise AudioError(
                        "AUDIO_TOO_LARGE",
                        f"音频不能超过 {settings.audio_max_bytes // (1024 * 1024)}MB",
                        413,
                    )
                destination.write(chunk)
        if total == 0:
            raise AudioError("EMPTY_AUDIO", "请选择非空音频文件")
        info = probe_audio(temporary)
        final_path = settings.upload_dir / f"{uuid4().hex}{info.extension}"
        temporary.replace(final_path)
        return final_path, info, total
    except Exception:
        temporary.unlink(missing_ok=True)
        raise


def normalize_audio(original: Path) -> Path:
    output = settings.upload_dir / f"{uuid4().hex}.wav"
    result = _run(
        [
            settings.ffmpeg_bin,
            "-nostdin",
            "-v",
            "error",
            "-i",
            str(original),
            "-vn",
            "-ac",
            "1",
            "-ar",
            "16000",
            "-c:a",
            "pcm_s16le",
            "-y",
            str(output),
        ],
        timeout=max(45, settings.audio_max_duration_seconds),
    )
    if result.returncode or not output.is_file():
        output.unlink(missing_ok=True)
        raise AudioError("AUDIO_NORMALIZATION_FAILED", "音频标准化失败，请重新录制")
    return output


def stored_path(relative_path: str) -> Path:
    root = settings.upload_dir.parent.resolve()
    path = (root / relative_path).resolve()
    if path != root and root not in path.parents:
        raise AudioError("INVALID_MEDIA_PATH", "媒体路径无效", 404)
    return path
