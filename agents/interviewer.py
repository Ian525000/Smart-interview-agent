"""面试对话 FSM Agent。"""

from datetime import datetime
from typing import Optional

from config import FOLLOW_UP_QUESTION_COUNT, MAX_FOLLOW_UPS
from agents.prompt_loader import load_prompt
from llm_client import HelloAgentsLLM
from models.schemas import (
    InterviewPhase,
    InterviewSession,
    Question,
    QuestionType,
    Turn,
)
from utils.json_parser import extract_json

SKIP_PLACEHOLDER = "（候选人选择跳过此题）"


class InterviewerAgent:
    """面试有限状态机，管理提问与追问。"""

    def __init__(self, llm: HelloAgentsLLM):
        """
        @param llm - LLM 客户端
        """
        self.llm = llm

    def prepare_follow_up_targets(self, session: InterviewSession) -> None:
        """
        选取 2-3 道可深度展开的问题。

        @param session - 面试会话
        """
        candidates = [q for q in session.questions if q.follow_up_enabled]
        priority = sorted(
            candidates,
            key=lambda q: (
                0 if q.type == QuestionType.PROJECT else
                1 if q.type == QuestionType.CASE else 2
            ),
        )
        session.follow_up_targets = [q.id for q in priority[:FOLLOW_UP_QUESTION_COUNT]]

    def get_current_question(self, session: InterviewSession) -> Optional[Question]:
        """
        获取当前问题。

        @param session - 面试会话
        @returns 当前问题或 None
        """
        if session.current_question_index >= len(session.questions):
            return None
        return session.questions[session.current_question_index]

    def start_question(self, session: InterviewSession) -> dict:
        """
        开始当前问题，返回 Agent 提问文本。

        @param session - 面试会话
        @returns 包含 question 与 agent_text 的字典
        """
        question = self.get_current_question(session)
        if not question:
            return {"done": True, "message": "所有问题已完成。"}

        session.follow_up_count = 0
        agent_text = self._format_question_intro(session, question)
        session.turns.append(
            Turn(
                question_id=question.id,
                agent_text=agent_text,
                is_follow_up=False,
            )
        )
        session.phase = InterviewPhase.INTERVIEWING
        return self._decorate_result(
            session,
            {
                "done": False,
                "question_id": question.id,
                "question_index": session.current_question_index,
                "total": len(session.questions),
                "agent_text": agent_text,
                "follow_up_enabled": question.id in session.follow_up_targets,
            },
        )

    def goto_question(
        self,
        session: InterviewSession,
        question_index: int,
        follow_up_index: Optional[int] = None,
    ) -> dict:
        """
        跳转到指定题目或该题下的某一追问。

        @param session - 面试会话
        @param question_index - 目标主问题序号（0 起）
        @param follow_up_index - 追问序号（0 起），None 表示跳到主问题
        @returns 目标题信息
        """
        if not session.questions:
            raise ValueError("当前没有可跳转的题目")
        if question_index < 0 or question_index >= len(session.questions):
            raise ValueError(f"题目序号无效，应在 1-{len(session.questions)} 之间")
        if session.phase == InterviewPhase.COMPLETED:
            raise ValueError("面试已结束，无法跳转题目")

        if follow_up_index is not None:
            return self._goto_follow_up(session, question_index, follow_up_index)

        session.phase = InterviewPhase.INTERVIEWING
        session.current_question_index = question_index
        session.follow_up_count = 0
        result = self.start_question(session)
        result["action"] = "goto"
        return result

    def _goto_follow_up(
        self,
        session: InterviewSession,
        question_index: int,
        follow_up_index: int,
    ) -> dict:
        """
        跳转到某主问题下已生成的追问。

        @param session - 面试会话
        @param question_index - 主问题序号
        @param follow_up_index - 追问序号（0 起）
        @returns 追问信息
        """
        question = session.questions[question_index]
        follow_turns = [
            t for t in session.turns
            if t.question_id == question.id and t.is_follow_up
        ]
        unique_follow_ups = []
        seen_texts = set()
        for turn in follow_turns:
            if turn.agent_text in seen_texts:
                continue
            seen_texts.add(turn.agent_text)
            unique_follow_ups.append(turn)
        if follow_up_index < 0 or follow_up_index >= len(unique_follow_ups):
            raise ValueError("追问序号无效")

        target = unique_follow_ups[follow_up_index]
        session.phase = InterviewPhase.INTERVIEWING
        session.current_question_index = question_index
        session.follow_up_count = follow_up_index + 1
        previous = target.user_transcript or ""

        last = session.turns[-1] if session.turns else None
        if last is not target or previous:
            session.turns.append(
                Turn(
                    question_id=question.id,
                    agent_text=target.agent_text,
                    is_follow_up=True,
                )
            )

        return self._decorate_result(
            session,
            {
                "done": False,
                "action": "goto_follow_up",
                "agent_text": target.agent_text,
                "question_id": question.id,
                "follow_up_count": session.follow_up_count,
                "previous_answer": previous,
                "previous_skipped": False,
            },
        )

    def get_questions_status(self, session: InterviewSession) -> list[dict]:
        """
        汇总每题作答状态及已生成的追问，供左侧导航使用。

        @param session - 面试会话
        @returns 状态列表
        """
        current_fu = self._current_follow_up_index(session)
        items = []
        for i, question in enumerate(session.questions):
            previous, _ = self.get_transcript_for_question(session, question.id)
            skipped = previous == SKIP_PLACEHOLDER
            answered = bool(previous) and not skipped
            follow_turns = [
                t for t in session.turns
                if t.question_id == question.id and t.is_follow_up
            ]
            unique_follow_ups = []
            seen_texts = set()
            for turn in follow_turns:
                if turn.agent_text in seen_texts:
                    continue
                seen_texts.add(turn.agent_text)
                unique_follow_ups.append(turn)
            follow_ups = []
            last_turn = session.turns[-1] if session.turns else None
            for j, turn in enumerate(unique_follow_ups):
                follow_ups.append(
                    {
                        "index": j,
                        "text": turn.agent_text,
                        "answered": bool(turn.user_transcript) or any(
                            x.agent_text == turn.agent_text and x.user_transcript
                            for x in follow_turns
                        ),
                        "current": (
                            i == session.current_question_index
                            and last_turn is not None
                            and last_turn.is_follow_up
                            and last_turn.question_id == question.id
                            and last_turn.agent_text == turn.agent_text
                        ),
                    }
                )
            items.append(
                {
                    "index": i,
                    "id": question.id,
                    "type": question.type.value if hasattr(question.type, "value") else str(question.type),
                    "text": question.text,
                    "active": i == session.current_question_index,
                    "current": i == session.current_question_index and current_fu is None,
                    "answered": answered,
                    "skipped": skipped,
                    "follow_ups": follow_ups,
                }
            )
        return items

    def _current_follow_up_index(self, session: InterviewSession) -> Optional[int]:
        """
        当前若正在回答某道追问，返回该追问序号。

        @param session - 面试会话
        @returns 追问序号或 None
        """
        question = self.get_current_question(session)
        if not question or not session.turns:
            return None
        last = session.turns[-1]
        if last.question_id != question.id or not last.is_follow_up:
            return None
        follow_turns = [
            t for t in session.turns
            if t.question_id == question.id and t.is_follow_up
        ]
        return len(follow_turns) - 1 if follow_turns else None

    def _decorate_result(self, session: InterviewSession, result: dict) -> dict:
        """
        为面试动作结果附加导航与上次作答信息。

        @param session - 面试会话
        @param result - 原始结果
        @returns 附加导航字段后的结果
        """
        result.setdefault("question_index", session.current_question_index)
        result.setdefault("total", len(session.questions))
        result["questions_status"] = self.get_questions_status(session)
        result["questions"] = [
            {
                "id": q.id,
                "text": q.text,
                "type": q.type.value if hasattr(q.type, "value") else str(q.type),
            }
            for q in session.questions
        ]
        result["current_follow_up_index"] = self._current_follow_up_index(session)
        if result.get("action") == "follow_up":
            result["previous_answer"] = ""
            result["previous_skipped"] = False
            return result

        question = self.get_current_question(session)
        if not question:
            result.setdefault("previous_answer", "")
            result.setdefault("previous_skipped", False)
            return result

        previous, _ = self.get_transcript_for_question(session, question.id)
        skipped = previous == SKIP_PLACEHOLDER
        result.setdefault("previous_answer", "" if skipped else previous)
        result.setdefault("previous_skipped", skipped)
        return result

    def submit_answer(
        self,
        session: InterviewSession,
        answer: str,
        skip: bool = False,
        retry: bool = False,
    ) -> dict:
        """
        提交回答并决定追问或下一题。

        @param session - 面试会话
        @param answer - 候选人回答
        @param skip - 是否跳过
        @param retry - 是否重答（清除本轮回答）
        @returns 下一步动作
        """
        question = self.get_current_question(session)
        if not question:
            return {"done": True, "message": "面试已结束。"}

        if retry:
            session.turns = [
                t for t in session.turns
                if not (t.question_id == question.id and not t.is_follow_up and not t.user_transcript)
            ]
            if session.turns and session.turns[-1].question_id == question.id:
                session.turns.pop()
            intro = self._format_question_intro(session, question)
            session.turns.append(Turn(question_id=question.id, agent_text=intro))
            return self._decorate_result(
                session,
                {
                    "action": "retry",
                    "agent_text": intro,
                    "question_id": question.id,
                },
            )

        if skip:
            answer = SKIP_PLACEHOLDER

        if session.turns:
            session.turns[-1].user_transcript = answer
            session.turns[-1].timestamp = datetime.now()

        if self._should_follow_up(session, question, answer, skip):
            return self._decorate_result(
                session,
                self._generate_follow_up(session, question, answer),
            )

        next_index = session.current_question_index + 1
        if next_index < len(session.questions):
            session.current_question_index = next_index
            session.follow_up_count = 0
            next_result = self.start_question(session)
            next_result["action"] = "next_question"
            return next_result

        session.follow_up_count = 0
        return self._decorate_result(
            session,
            {
                "action": "await_next",
                "done": False,
                "message": "本题已完成。可点击题号跳转到其他题目，或点击「完成面试」生成报告。",
                "question_id": question.id,
            },
        )

    def _should_follow_up(
        self,
        session: InterviewSession,
        question: Question,
        answer: str,
        skip: bool,
    ) -> bool:
        """
        判断是否触发追问。

        @param session - 面试会话
        @param question - 当前问题
        @param answer - 候选人回答
        @param skip - 是否跳过
        @returns 是否需要追问
        """
        if skip:
            return False
        if question.id not in session.follow_up_targets:
            return False
        if session.follow_up_count >= MAX_FOLLOW_UPS:
            return False
        if len(answer.strip()) < 10:
            return True
        shallow_keywords = ["大概", "好像", "忘了", "不太清楚", "没有数据"]
        if any(kw in answer for kw in shallow_keywords):
            return True
        if question.type in (QuestionType.PROJECT, QuestionType.CASE) and session.follow_up_count == 0:
            return True
        return False

    def _generate_follow_up(
        self,
        session: InterviewSession,
        question: Question,
        answer: str,
    ) -> dict:
        """
        生成追问。

        @param session - 面试会话
        @param question - 当前问题
        @param answer - 候选人回答
        @returns 追问结果
        """
        prompt = load_prompt(
            "follow_up",
            question_text=question.text,
            answer=answer,
            follow_up_count=session.follow_up_count + 1,
            max_follow_ups=MAX_FOLLOW_UPS,
        )
        response = self.llm.think([{"role": "user", "content": prompt}], temperature=0.3)
        data = extract_json(response)
        follow_up_text = data.get("follow_up", "能再具体说说你的个人贡献吗？")

        session.follow_up_count += 1
        session.turns.append(
            Turn(
                question_id=question.id,
                agent_text=follow_up_text,
                is_follow_up=True,
            )
        )
        return {
            "action": "follow_up",
            "agent_text": follow_up_text,
            "reason": data.get("reason", ""),
            "question_id": question.id,
            "follow_up_count": session.follow_up_count,
        }

    @staticmethod
    def _format_question_intro(session: InterviewSession, question: Question) -> str:
        """
        格式化问题播报文本。

        @param session - 面试会话
        @param question - 当前问题
        @returns 提问文本
        """
        idx = session.current_question_index + 1
        total = len(session.questions)
        type_label = {
            QuestionType.INTRO: "自我介绍",
            QuestionType.PROJECT: "项目深挖",
            QuestionType.CASE: "产品 Case",
            QuestionType.BEHAVIOR: "行为面试",
            QuestionType.OPEN: "开放题",
            QuestionType.REVERSE: "反问环节",
        }.get(question.type, "面试题")
        return f"第 {idx}/{total} 题（{type_label}）：{question.text}"

    def get_transcript_for_question(self, session: InterviewSession, question_id: str) -> tuple[str, list[str]]:
        """
        获取某题最近一次主回答与其后的追问记录。

        @param session - 面试会话
        @param question_id - 问题 ID
        @returns (主回答, 追问回答列表)
        """
        turns = [t for t in session.turns if t.question_id == question_id]
        last_main_pos = -1
        for i, turn in enumerate(turns):
            if not turn.is_follow_up and turn.user_transcript:
                last_main_pos = i
        if last_main_pos < 0:
            return "", []
        main_answer = turns[last_main_pos].user_transcript
        follow_ups = [
            t.user_transcript
            for t in turns[last_main_pos + 1 :]
            if t.is_follow_up and t.user_transcript
        ]
        return main_answer, follow_ups
