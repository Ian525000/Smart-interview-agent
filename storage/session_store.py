"""SQLite 会话持久化。"""

import json
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import List, Optional

from config import DATA_DIR
from models.schemas import InterviewSession

DB_PATH = DATA_DIR / "interview.db"

PHASE_LABELS = {
    "setup": "待生成",
    "preview": "待开始",
    "interviewing": "面试中",
    "scoring": "评分中",
    "completed": "已完成",
}


def _format_session_time(value: str) -> str:
    """
    将 ISO 时间格式化为「年-月-日 时:分」。

    @param value - 原始时间字符串
    @returns 展示用时间
    """
    if not value:
        return ""
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if dt.tzinfo:
            dt = dt.astimezone().replace(tzinfo=None)
        return dt.strftime("%Y-%m-%d %H:%M")
    except ValueError:
        return value.replace("T", " ")[:16]


def _extract_job_title(payload_json: str) -> str:
    """
    从会话 JSON 中提取岗位名称。

    @param payload_json - 会话序列化数据
    @returns 岗位名称
    """
    try:
        payload = json.loads(payload_json or "{}")
        jd = payload.get("jd_profile") or {}
        title = str(jd.get("title") or "").strip()
        company = str(jd.get("company") or "").strip()
        if title:
            return title
        if company and company != "互联网大厂":
            return f"{company}产品岗"
    except (json.JSONDecodeError, TypeError, AttributeError):
        pass
    return "未命名岗位"


def build_session_label(created_at: str, job_title: str, phase: str) -> str:
    """
    生成历史会话展示名：日期时间 · 岗位 · 进度。

    @param created_at - 创建时间
    @param job_title - 岗位名称
    @param phase - 阶段枚举值
    @returns 展示名
    """
    time_str = _format_session_time(created_at)
    title = (job_title or "").strip() or "未命名岗位"
    phase_label = PHASE_LABELS.get(phase, phase or "未知")
    return f"{time_str} · {title} · {phase_label}"


class SessionStore:
    """面试会话存储。"""

    def __init__(self, db_path: Optional[Path] = None):
        """
        @param db_path - 数据库文件路径
        """
        self.db_path = db_path or DB_PATH
        self._init_db()

    def _init_db(self) -> None:
        """初始化数据库表。"""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS sessions (
                    session_id TEXT PRIMARY KEY,
                    phase TEXT NOT NULL,
                    data TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )

    def save(self, session: InterviewSession) -> None:
        """
        保存或更新会话。

        @param session - 面试会话对象
        """
        session.updated_at = datetime.now()
        payload = session.model_dump_json()
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                INSERT INTO sessions (session_id, phase, data, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(session_id) DO UPDATE SET
                    phase=excluded.phase,
                    data=excluded.data,
                    updated_at=excluded.updated_at
                """,
                (
                    session.session_id,
                    session.phase.value,
                    payload,
                    session.created_at.isoformat(),
                    session.updated_at.isoformat(),
                ),
            )

    def load(self, session_id: str) -> Optional[InterviewSession]:
        """
        加载会话。

        @param session_id - 会话 ID
        @returns 会话对象或 None
        """
        with sqlite3.connect(self.db_path) as conn:
            row = conn.execute(
                "SELECT data FROM sessions WHERE session_id = ?",
                (session_id,),
            ).fetchone()
        if not row:
            return None
        return InterviewSession.model_validate_json(row[0])

    def list_sessions(self, limit: int = 50) -> List[dict]:
        """
        列出最近会话摘要（含展示名：时间 + 岗位）。

        @param limit - 返回数量上限
        @returns 会话摘要列表
        """
        with sqlite3.connect(self.db_path) as conn:
            rows = conn.execute(
                """
                SELECT session_id, phase, created_at, updated_at, data
                FROM sessions
                ORDER BY updated_at DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
        summaries = []
        for row in rows:
            job_title = _extract_job_title(row[4])
            summaries.append(
                {
                    "session_id": row[0],
                    "phase": row[1],
                    "phase_label": PHASE_LABELS.get(row[1], row[1] or "未知"),
                    "job_title": job_title,
                    "created_at": row[2],
                    "updated_at": row[3],
                    "label": build_session_label(row[2], job_title, row[1]),
                }
            )
        return summaries

    def delete(self, session_id: str) -> bool:
        """
        删除会话。

        @param session_id - 会话 ID
        @returns 是否删除成功
        """
        deleted = self.delete_many([session_id])
        return session_id in deleted

    def delete_many(self, session_ids: List[str]) -> List[str]:
        """
        批量删除会话，并显式提交事务。

        @param session_ids - 会话 ID 列表
        @returns 实际删除成功的 ID
        """
        cleaned: List[str] = []
        seen = set()
        for raw in session_ids or []:
            sid = str(raw or "").strip()
            if sid and sid not in seen:
                seen.add(sid)
                cleaned.append(sid)
        if not cleaned:
            return []

        deleted: List[str] = []
        conn = sqlite3.connect(self.db_path)
        try:
            for sid in cleaned:
                cursor = conn.execute(
                    "DELETE FROM sessions WHERE session_id = ?",
                    (sid,),
                )
                if cursor.rowcount > 0:
                    deleted.append(sid)
            conn.commit()
        finally:
            conn.close()
        return deleted

    def export_json(self, session_id: str, output_path: str) -> Optional[str]:
        """
        导出会话为 JSON 文件。

        @param session_id - 会话 ID
        @param output_path - 输出路径
        @returns 导出路径或 None
        """
        session = self.load(session_id)
        if not session:
            return None
        path = Path(output_path)
        path.write_text(
            json.dumps(session.model_dump(mode="json"), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        return str(path)
