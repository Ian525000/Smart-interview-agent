"""面试编排服务。"""

import json
import uuid
from pathlib import Path
from typing import Optional

from agents import (
    JDParserAgent,
    InterviewerAgent,
    QuestionGeneratorAgent,
    ReportWriter,
    ScoringAgent,
)
from config import TEMPLATES_DIR
from llm_client import HelloAgentsLLM
from models.schemas import InterviewPhase, InterviewSession, Question
from parsers.document import parse_document, parse_upload_bytes
from storage.session_store import SessionStore


class InterviewService:
    """面试全流程编排。"""

    def __init__(self):
        """初始化 LLM、Agent 与存储。"""
        self.llm = HelloAgentsLLM()
        self.jd_parser = JDParserAgent(self.llm)
        self.question_gen = QuestionGeneratorAgent(self.llm)
        self.interviewer = InterviewerAgent(self.llm)
        self.scorer = ScoringAgent(self.llm)
        self.report_writer = ReportWriter()
        self.store = SessionStore()

    def create_session_from_text(
        self,
        jd_text: str,
        resume_text: str,
        mode: str = "text",
        template_id: Optional[str] = None,
        mock_mode: bool = False,
    ) -> InterviewSession:
        """
        从文本创建会话并完成预设阶段。

        @param jd_text - JD 文本
        @param resume_text - 简历文本
        @param mode - 交互模式 text/voice
        @param template_id - 岗位模板 ID
        @param mock_mode - Mock 练习模式
        @returns 会话对象
        """
        session = InterviewSession(
            session_id=str(uuid.uuid4())[:8],
            mode=mode,
            metadata={"mock_mode": mock_mode, "template_id": template_id},
        )

        if mock_mode:
            template_id = template_id or "bytedance_product_mock"
            session = self._apply_template(session, template_id, jd_text, resume_text)
        else:
            jd, resume, match = self.jd_parser.parse(jd_text, resume_text)
            session.jd_profile = jd
            session.resume_profile = resume
            session.match_analysis = match

            if template_id:
                session = self._merge_template_questions(session, template_id)

            if not session.questions:
                session.questions = self.question_gen.generate(jd, resume, match)

        self.interviewer.prepare_follow_up_targets(session)
        session.phase = InterviewPhase.PREVIEW
        self.store.save(session)
        return session

    def create_session_from_files(
        self,
        jd_filename: str,
        jd_content: bytes,
        resume_filename: str,
        resume_content: bytes,
        mode: str = "voice",
        template_id: Optional[str] = None,
        mock_mode: bool = False,
    ) -> InterviewSession:
        """
        从上传文件创建会话。

        @param jd_filename - JD 文件名
        @param jd_content - JD 文件内容
        @param resume_filename - 简历文件名
        @param resume_content - 简历文件内容
        @param mode - 交互模式
        @param template_id - 模板 ID
        @param mock_mode - Mock 模式
        @returns 会话对象
        """
        jd_text = parse_upload_bytes(jd_filename, jd_content)
        resume_text = parse_upload_bytes(resume_filename, resume_content)
        return self.create_session_from_text(
            jd_text, resume_text, mode, template_id, mock_mode
        )

    def update_questions(self, session_id: str, questions: list[Question]) -> InterviewSession:
        """
        更新预览阶段的问题列表。

        @param session_id - 会话 ID
        @param questions - 新问题列表
        @returns 更新后的会话
        """
        session = self._require_session(session_id)
        session.questions = questions
        self.interviewer.prepare_follow_up_targets(session)
        self.store.save(session)
        return session

    def lock_questions_and_start(self, session_id: str) -> dict:
        """
        锁定问题并开始面试。

        @param session_id - 会话 ID
        @returns 首题信息
        """
        session = self._require_session(session_id)

        if session.phase == InterviewPhase.INTERVIEWING and session.turns:
            if session.current_question_index >= len(session.questions):
                session.current_question_index = max(0, len(session.questions) - 1)
            question = self.interviewer.get_current_question(session)
            if question:
                last_turn = session.turns[-1]
                result = {
                    "done": False,
                    "question_id": question.id,
                    "question_index": session.current_question_index,
                    "total": len(session.questions),
                    "agent_text": last_turn.agent_text,
                    "follow_up_enabled": question.id in session.follow_up_targets,
                    "resumed": True,
                }
                return self.interviewer._decorate_result(session, result)

        session.phase = InterviewPhase.INTERVIEWING
        session.current_question_index = 0
        session.turns = []
        self.store.save(session)
        result = self.interviewer.start_question(session)
        self.store.save(session)
        return result

    def submit_answer(
        self,
        session_id: str,
        answer: str,
        skip: bool = False,
        retry: bool = False,
        audio_path: Optional[str] = None,
    ) -> dict:
        """
        提交回答。

        @param session_id - 会话 ID
        @param answer - 回答文本
        @param skip - 是否跳过
        @param retry - 是否重答
        @param audio_path - 音频路径
        @returns 下一步动作
        """
        session = self._require_session(session_id)
        if audio_path and session.turns:
            session.turns[-1].audio_path = audio_path

        result = self.interviewer.submit_answer(session, answer, skip, retry)

        if result.get("action") == "complete":
            session.phase = InterviewPhase.SCORING
            self.store.save(session)
            score_result = self.run_scoring(session_id)
            result["scoring"] = score_result

        self.store.save(session)
        return result

    def goto_question(
        self, session_id: str, question_index: int, follow_up_index: Optional[int] = None
    ) -> dict:
        """
        面试进行中跳转到指定题目或追问。

        @param session_id - 会话 ID
        @param question_index - 目标主问题序号（0 起）
        @param follow_up_index - 追问序号（0 起），None 表示主问题
        @returns 目标题信息
        """
        session = self._require_session(session_id)
        result = self.interviewer.goto_question(session, question_index, follow_up_index)
        self.store.save(session)
        return result

    def finish_interview(self, session_id: str) -> dict:
        """
        结束面试并生成评分报告。

        @param session_id - 会话 ID
        @returns 完成结果（含评分）
        """
        session = self._require_session(session_id)
        if session.phase == InterviewPhase.COMPLETED:
            return {
                "action": "complete",
                "done": True,
                "message": "面试已完成。",
                "scoring": {
                    "markdown": session.report_path,
                    "pdf": session.metadata.get("pdf_path"),
                    "qa_markdown": session.metadata.get("qa_path"),
                    "qa_pdf": session.metadata.get("qa_pdf_path"),
                    "summary": session.summary.model_dump() if session.summary else None,
                },
            }

        session.phase = InterviewPhase.SCORING
        self.store.save(session)
        score_result = self.run_scoring(session_id)
        return {
            "action": "complete",
            "done": True,
            "message": "面试完成，正在进入评分阶段。",
            "scoring": score_result,
        }

    def run_scoring(self, session_id: str) -> dict:
        """
        执行打分并生成报告。

        @param session_id - 会话 ID
        @returns 报告路径信息
        """
        session = self._require_session(session_id)
        session = self.scorer.score_session(session)
        md_path = self.report_writer.write_markdown(session)
        qa_md_path = self.report_writer.write_qa_markdown(session)
        try:
            pdf_path = self.report_writer.write_eval_pdf(session)
        except Exception as exc:
            print(f"[报告] 评估 PDF 生成失败，不影响评分：{exc}")
            pdf_path = None
        try:
            qa_pdf_path = self.report_writer.write_qa_pdf(session)
        except Exception as exc:
            print(f"[报告] 问答 PDF 生成失败，不影响评分：{exc}")
            qa_pdf_path = None
        session.phase = InterviewPhase.COMPLETED
        session.report_path = md_path
        session.metadata["qa_path"] = qa_md_path
        if pdf_path:
            session.metadata["pdf_path"] = pdf_path
        if qa_pdf_path:
            session.metadata["qa_pdf_path"] = qa_pdf_path
        self.store.save(session)
        return {
            "markdown": md_path,
            "pdf": pdf_path,
            "qa_markdown": qa_md_path,
            "qa_pdf": qa_pdf_path,
            "summary": session.summary.model_dump() if session.summary else None,
        }

    def export_eval_report(self, session_id: str, fmt: str = "md") -> Path:
        """
        按最新模板生成评估报告并返回文件路径。

        @param session_id - 会话 ID
        @param fmt - md 或 pdf
        @returns 文件路径
        """
        session = self._require_session(session_id)
        md_path = self.report_writer.write_markdown(session)
        session.report_path = md_path
        if fmt == "pdf":
            pdf_path = self.report_writer.write_eval_pdf(session)
            if not pdf_path:
                self.store.save(session)
                raise RuntimeError("评估报告 PDF 生成失败")
            session.metadata["pdf_path"] = pdf_path
            self.store.save(session)
            return Path(pdf_path)
        self.store.save(session)
        return Path(md_path)

    def export_qa_transcript(self, session_id: str, fmt: str = "md") -> Path:
        """
        按最新模板生成问答实录并返回文件路径。

        @param session_id - 会话 ID
        @param fmt - md 或 pdf
        @returns 文件路径
        """
        session = self._require_session(session_id)
        qa_md_path = self.report_writer.write_qa_markdown(session)
        session.metadata["qa_path"] = qa_md_path
        if fmt == "pdf":
            qa_pdf_path = self.report_writer.write_qa_pdf(session)
            if not qa_pdf_path:
                self.store.save(session)
                raise RuntimeError("问答实录 PDF 生成失败")
            session.metadata["qa_pdf_path"] = qa_pdf_path
            self.store.save(session)
            return Path(qa_pdf_path)
        self.store.save(session)
        return Path(qa_md_path)

    def get_session(self, session_id: str) -> InterviewSession:
        """
        获取会话。

        @param session_id - 会话 ID
        @returns 会话对象
        """
        return self._require_session(session_id)

    def delete_session(self, session_id: str) -> bool:
        """
        删除历史会话。

        @param session_id - 会话 ID
        @returns 是否删除成功
        """
        return self.store.delete(session_id)

    def delete_sessions(self, session_ids: list[str]) -> list[str]:
        """
        批量删除历史会话。

        @param session_ids - 会话 ID 列表
        @returns 实际删除成功的 ID
        """
        return self.store.delete_many(session_ids)

    def list_templates(self) -> list[dict]:
        """
        列出岗位模板。

        @returns 模板列表
        """
        path = TEMPLATES_DIR / "job_templates.json"
        if not path.exists():
            return []
        data = json.loads(path.read_text(encoding="utf-8"))
        return data.get("templates", [])

    def _require_session(self, session_id: str) -> InterviewSession:
        """
        @param session_id - 会话 ID
        @returns 会话对象
        """
        session = self.store.load(session_id)
        if not session:
            raise ValueError(f"会话不存在: {session_id}")
        return session

    def _apply_template(
        self,
        session: InterviewSession,
        template_id: str,
        jd_text: str,
        resume_text: str,
    ) -> InterviewSession:
        """
        Mock 模式：使用模板问题，简化解析。

        @param session - 会话对象
        @param template_id - 模板 ID
        @param jd_text - JD 文本
        @param resume_text - 简历文本
        @returns 更新后的会话
        """
        templates = self.list_templates()
        template = next((t for t in templates if t["id"] == template_id), None)
        if not template:
            raise ValueError(f"模板不存在: {template_id}")

        session.jd_profile = None
        session.resume_profile = None
        session.match_analysis = None

        try:
            jd, resume, match = self.jd_parser.parse(jd_text or template.get("sample_jd", ""), resume_text or "Mock 候选人")
            session.jd_profile = jd
            session.resume_profile = resume
            session.match_analysis = match
        except Exception:
            pass

        session.questions = self.question_gen.generate_from_template(template["questions"])
        return session

    def _merge_template_questions(self, session: InterviewSession, template_id: str) -> InterviewSession:
        """
        用模板问题替换部分自动生成问题。

        @param session - 会话对象
        @param template_id - 模板 ID
        @returns 更新后的会话
        """
        templates = self.list_templates()
        template = next((t for t in templates if t["id"] == template_id), None)
        if template and template.get("questions"):
            session.questions = self.question_gen.generate_from_template(template["questions"])
        return session

    @staticmethod
    def parse_file_path(file_path: str) -> str:
        """
        @param file_path - 文件路径
        @returns 文本内容
        """
        return parse_document(file_path)
