"""STT 语音识别。"""

import uuid
from pathlib import Path
from typing import Optional

from config import AUDIO_DIR, WHISPER_MODEL


def transcribe_file(audio_path: str, language: str = "zh") -> str:
    """
    转写音频文件（faster-whisper）。

    @param audio_path - 音频文件路径
    @param language - 语言代码
    @returns 转写文本
    """
    try:
        from faster_whisper import WhisperModel
    except ImportError:
        return _fallback_transcribe(audio_path)

    model = WhisperModel(WHISPER_MODEL, device="cpu", compute_type="int8")
    segments, _ = model.transcribe(audio_path, language=language)
    return "".join(seg.text for seg in segments).strip()


def transcribe_bytes(audio_bytes: bytes, suffix: str = ".webm", language: str = "zh") -> str:
    """
    转写二进制音频。

    @param audio_bytes - 音频数据
    @param suffix - 文件后缀
    @param language - 语言代码
    @returns 转写文本
    """
    path = AUDIO_DIR / f"stt_{uuid.uuid4().hex[:8]}{suffix}"
    path.write_bytes(audio_bytes)
    return transcribe_file(str(path), language)


def _fallback_transcribe(audio_path: str) -> str:
    """
    无 faster-whisper 时的降级提示。

    @param audio_path - 音频路径
    @returns 提示文本
    """
    return f"（音频已保存于 {audio_path}，请安装 faster-whisper 或使用浏览器语音转写）"
