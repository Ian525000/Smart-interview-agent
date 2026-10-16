"""LLM 画像数据归一化，兼容多种 JSON 结构。"""

from typing import Any


def _to_str(value: Any) -> str:
    """
    将任意值转为字符串。

    @param value - 原始值
    @returns 字符串
    """
    if value is None:
        return ""
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, (int, float, bool)):
        return str(value)
    if isinstance(value, dict):
        parts = [f"{k}: {_to_str(v)}" for k, v in value.items() if v not in (None, "")]
        return "；".join(parts)
    if isinstance(value, list):
        return "；".join(_to_str(item) for item in value if item not in (None, ""))
    return str(value).strip()


def _to_str_list(value: Any) -> list[str]:
    """
    将任意值转为字符串列表。

    @param value - 原始值
    @returns 字符串列表
    """
    if value is None:
        return []
    if isinstance(value, str):
        return [line.strip() for line in value.split("\n") if line.strip()] or [value.strip()]
    if isinstance(value, dict):
        return [_to_str(value)]
    if isinstance(value, list):
        result: list[str] = []
        for item in value:
            text = _to_str(item)
            if text:
                result.append(text)
        return result
    text = _to_str(value)
    return [text] if text else []


def _to_float(value: Any, default: float = 0.0) -> float:
    """
    将任意值转为浮点数。

    @param value - 原始值
    @param default - 默认值
    @returns 浮点数
    """
    if value is None:
        return default
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        cleaned = value.strip().replace("%", "")
        try:
            return float(cleaned)
        except ValueError:
            return default
    return default


def normalize_jd_profile(data: dict[str, Any]) -> dict[str, Any]:
    """
    归一化 JD 画像字段。

    @param data - 原始字典
    @returns 归一化后的字典
    """
    return {
        "title": _to_str(data.get("title")),
        "company": _to_str(data.get("company")) or "互联网大厂",
        "level": _to_str(data.get("level")),
        "core_skills": _to_str_list(data.get("core_skills")),
        "keywords": _to_str_list(data.get("keywords")),
        "responsibilities": _to_str_list(data.get("responsibilities")),
        "requirements": _to_str_list(data.get("requirements")),
        "raw_text": _to_str(data.get("raw_text")),
    }


def normalize_resume_profile(data: dict[str, Any]) -> dict[str, Any]:
    """
    归一化简历画像字段。

    @param data - 原始字典
    @returns 归一化后的字典
    """
    return {
        "name": _to_str(data.get("name")),
        "years_experience": _to_str(data.get("years_experience")),
        "education": _to_str_list(data.get("education")),
        "work_experience": _to_str_list(data.get("work_experience")),
        "projects": _to_str_list(data.get("projects")),
        "skills": _to_str_list(data.get("skills")),
        "highlights": _to_str_list(data.get("highlights")),
        "raw_text": _to_str(data.get("raw_text")),
    }


def normalize_match_analysis(data: dict[str, Any]) -> dict[str, Any]:
    """
    归一化匹配分析字段。

    @param data - 原始字典
    @returns 归一化后的字典
    """
    return {
        "match_points": _to_str_list(data.get("match_points")),
        "risk_points": _to_str_list(data.get("risk_points")),
        "hypotheses": _to_str_list(data.get("hypotheses")),
        "overall_match_score": _to_float(data.get("overall_match_score")),
    }
