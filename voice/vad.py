"""VAD 语音活动检测。"""

import struct
from typing import List


def detect_speech_segments(
    pcm_data: bytes,
    sample_rate: int = 16000,
    frame_duration_ms: int = 30,
    energy_threshold: float = 500.0,
    silence_duration_ms: int = 2500,
) -> List[tuple[int, int]]:
    """
    基于能量的简易 VAD，检测语音片段起止样本索引。

    @param pcm_data - 16-bit PCM 原始数据
    @param sample_rate - 采样率
    @param frame_duration_ms - 帧长（毫秒）
    @param energy_threshold - 能量阈值
    @param silence_duration_ms - 静音判定时长
    @returns [(start_sample, end_sample), ...]
    """
    frame_size = int(sample_rate * frame_duration_ms / 1000) * 2
    silence_frames = int(silence_duration_ms / frame_duration_ms)

    segments: List[tuple[int, int]] = []
    in_speech = False
    speech_start = 0
    silence_count = 0

    for i in range(0, len(pcm_data) - frame_size, frame_size):
        frame = pcm_data[i : i + frame_size]
        samples = struct.unpack(f"<{len(frame)//2}h", frame)
        energy = sum(abs(s) for s in samples) / len(samples)

        if energy > energy_threshold:
            if not in_speech:
                in_speech = True
                speech_start = i // 2
            silence_count = 0
        elif in_speech:
            silence_count += 1
            if silence_count >= silence_frames:
                end_sample = (i + frame_size) // 2
                segments.append((speech_start, end_sample))
                in_speech = False
                silence_count = 0

    if in_speech:
        segments.append((speech_start, len(pcm_data) // 2))

    return segments


def is_speech_end(
    pcm_chunk: bytes,
    sample_rate: int = 16000,
    silence_ms: int = 2500,
    threshold: float = 500.0,
) -> bool:
    """
    判断当前音频块是否处于「答毕」状态（持续静音）。

    @param pcm_chunk - PCM 数据块
    @param sample_rate - 采样率
    @param silence_ms - 静音阈值毫秒
    @param threshold - 能量阈值
    @returns 是否判定为答毕
    """
    if len(pcm_chunk) < 2:
        return False
    samples = struct.unpack(f"<{len(pcm_chunk)//2}h", pcm_chunk)
    energy = sum(abs(s) for s in samples) / len(samples)
    duration_ms = len(samples) / sample_rate * 1000
    return energy < threshold and duration_ms >= silence_ms
