"""PDF / Word 文档解析。"""

from pathlib import Path
from typing import Optional


def parse_document(file_path: str) -> str:
    """
    解析 PDF 或 Word 文档为纯文本。

    @param file_path - 文件路径
    @returns 提取的文本内容
    """
    path = Path(file_path)
    suffix = path.suffix.lower()

    if suffix == ".pdf":
        return _parse_pdf(path)
    if suffix in (".docx", ".doc"):
        return _parse_docx(path)
    if suffix in (".txt", ".md"):
        return path.read_text(encoding="utf-8", errors="ignore")

    raise ValueError(f"不支持的文件格式: {suffix}")


def _parse_pdf(path: Path) -> str:
    """解析 PDF 文件。"""
    try:
        import pdfplumber
    except ImportError as exc:
        raise ImportError("请安装 pdfplumber: pip install pdfplumber") from exc

    texts: list[str] = []
    with pdfplumber.open(path) as pdf:
        for page in pdf.pages:
            page_text = page.extract_text()
            if page_text:
                texts.append(page_text.strip())
    return "\n\n".join(texts)


def _parse_docx(path: Path) -> str:
    """解析 Word 文件。"""
    try:
        from docx import Document
    except ImportError as exc:
        raise ImportError("请安装 python-docx: pip install python-docx") from exc

    doc = Document(str(path))
    paragraphs = [p.text.strip() for p in doc.paragraphs if p.text.strip()]
    return "\n".join(paragraphs)


def parse_upload_bytes(filename: str, content: bytes, save_dir: Optional[str] = None) -> str:
    """
    保存上传文件并解析为文本。

    @param filename - 原始文件名
    @param content - 文件二进制内容
    @param save_dir - 可选保存目录
    @returns 解析后的文本
    """
    from config import DATA_DIR

    target_dir = Path(save_dir) if save_dir else DATA_DIR / "uploads"
    target_dir.mkdir(parents=True, exist_ok=True)
    target_path = target_dir / filename
    target_path.write_bytes(content)
    return parse_document(str(target_path))
