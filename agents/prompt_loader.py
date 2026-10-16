"""Prompt 模板加载工具。"""

from pathlib import Path

from config import PROMPTS_DIR


def load_prompt(name: str, **kwargs: str) -> str:
    """
    加载并格式化 Prompt 模板，仅替换已知占位符，避免 JSON 花括号冲突。

    @param name - 模板文件名（不含扩展名）
    @param kwargs - 模板占位符
    @returns 格式化后的 Prompt
    """
    path = PROMPTS_DIR / f"{name}.txt"
    template = path.read_text(encoding="utf-8")
    result = template
    for key, value in kwargs.items():
        result = result.replace("{" + key + "}", str(value))
    return result
