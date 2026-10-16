"""LLM JSON 响应解析工具。"""

import json
import re
from typing import Any, Optional


def extract_json(text: Optional[str]) -> Any:
    """
    从 LLM 响应中提取 JSON 对象或数组。

    @param text - 原始响应文本
    @returns 解析后的 Python 对象
    """
    if not text:
        raise ValueError("LLM 响应为空，无法解析 JSON。")

    cleaned = text.strip()
    fence_match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", cleaned)
    if fence_match:
        cleaned = fence_match.group(1).strip()

    for candidate in _json_candidates(cleaned):
        try:
            return json.loads(candidate)
        except json.JSONDecodeError:
            fixed = _fix_common_json_issues(candidate)
            try:
                return json.loads(fixed)
            except json.JSONDecodeError:
                continue

    raise ValueError(f"无法从响应中解析 JSON: {text[:300]}...")


def _json_candidates(text: str) -> list[str]:
    """
    生成可能的 JSON 子串候选。

    @param text - 原始文本
    @returns 候选 JSON 字符串列表
    """
    candidates = [text]
    for pattern in (r"\{[\s\S]*\}", r"\[[\s\S]*\]"):
        match = re.search(pattern, text)
        if match:
            candidates.append(match.group(0))
    return candidates


def _fix_common_json_issues(text: str) -> str:
    """
    修复 LLM 输出中常见的 JSON 格式问题。

    @param text - 原始 JSON 字符串
    @returns 修复后的字符串
    """
    fixed = text
    fixed = re.sub(r",\s*}", "}", fixed)
    fixed = re.sub(r",\s*]", "]", fixed)
    fixed = fixed.replace("'", '"')
    fixed = re.sub(r"\bTrue\b", "true", fixed)
    fixed = re.sub(r"\bFalse\b", "false", fixed)
    fixed = re.sub(r"\bNone\b", "null", fixed)
    return fixed
