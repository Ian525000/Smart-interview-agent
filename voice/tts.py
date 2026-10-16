"""TTS 语音合成（Edge TTS + 重试 + 失败降级）。"""

import asyncio
import uuid
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Optional

from config import AUDIO_DIR, TTS_VOICE

_executor = ThreadPoolExecutor(max_workers=2)


async def synthesize_async(text: str, voice: Optional[str] = None, retries: int = 3) -> str:
    """
    异步合成语音，失败时自动重试。

    @param text - 待合成文本
    @param voice - 语音角色
    @param retries - 重试次数
    @returns 音频文件路径
    """
    import edge_tts

    output_path = AUDIO_DIR / f"tts_{uuid.uuid4().hex[:8]}.mp3"
    voice = voice or TTS_VOICE
    last_error: Optional[Exception] = None

    for attempt in range(retries):
        try:
            communicate = edge_tts.Communicate(text, voice)
            await communicate.save(str(output_path))
            if output_path.exists() and output_path.stat().st_size > 0:
                return str(output_path)
            raise OSError("TTS 输出文件为空")
        except Exception as exc:
            last_error = exc
            if attempt < retries - 1:
                await asyncio.sleep(0.8 * (attempt + 1))

    raise RuntimeError(f"TTS 合成失败: {last_error}")


async def synthesize_safe(text: str, voice: Optional[str] = None) -> Optional[str]:
    """
    安全合成语音，失败返回 None 而不抛异常。

    @param text - 待合成文本
    @param voice - 语音角色
    @returns 音频路径或 None
    """
    try:
        return await synthesize_async(text, voice)
    except Exception as exc:
        print(f"[TTS] 合成失败，将降级为纯文字播报: {exc}")
        return None


def synthesize(text: str, voice: Optional[str] = None) -> str:
    """
    同步合成语音（CLI 等无事件循环场景）。

    @param text - 待合成文本
    @param voice - 语音角色
    @returns 音频文件路径
    """
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        path = asyncio.run(synthesize_safe(text, voice))
        if not path:
            raise RuntimeError("TTS 合成失败")
        return path

    future = _executor.submit(lambda: asyncio.run(synthesize_safe(text, voice)))
    path = future.result()
    if not path:
        raise RuntimeError("TTS 合成失败")
    return path


async def synthesize_to_bytes_async(text: str, voice: Optional[str] = None) -> Optional[bytes]:
    """
    异步合成并返回 MP3 字节。

    @param text - 待合成文本
    @param voice - 语音角色
    @returns MP3 二进制数据或 None
    """
    path = await synthesize_safe(text, voice)
    if not path:
        return None
    return Path(path).read_bytes()
