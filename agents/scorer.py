"""Reflection 打分 Agent。"""

import json

from config import REFLECTION_ROUNDS
from agents.interviewer import InterviewerAgent
from agents.prompt_loader import load_prompt
from llm_client import HelloAgentsLLM
from models.schemas import (
    DimensionScore,
    InterviewSession,
    InterviewSummary,
    QuestionScore,
)
from utils.json_parser import extract_json


class ScoringAgent:
    """逐题打分与 Reflection 校准。"""

    def __init__(self, llm: HelloAgentsLLM):
        """
        @param llm - LLM 客户端
        """
        self.llm = llm
        self.interviewer = InterviewerAgent(llm)

    def score_session(self, session: InterviewSession) -> InterviewSession:
        """
        对整个会话逐题打分并生成总评。

        @param session - 面试会话
        @returns 更新后的会话
        """
        session.scores = []
        for question in session.questions:
            answer, follow_ups = self.interviewer.get_transcript_for_question(session, question.id)
            if not answer:
                answer = "（未作答）"
            score = self._score_question(session, question, answer, follow_ups)
            session.scores.append(score)

        session.summary = self._generate_summary(session)
        return session

    def _score_question(
        self,
        session: InterviewSession,
        question,
        answer: str,
        follow_ups: list[str],
    ) -> QuestionScore:
        """
        对单题打分并进行 Reflection 校准。

        @param session - 面试会话
        @param question - 问题对象
        @param answer - 主回答
        @param follow_ups - 追问回答
        @returns 单题评分
        """
        prompt = load_prompt(
            "score",
            question_text=question.text,
            question_type=question.type.value,
            answer=answer,
            follow_ups="; ".join(follow_ups) if follow_ups else "无",
            jd_profile=session.jd_profile.model_dump_json(indent=2) if session.jd_profile else "{}",
            resume_profile=session.resume_profile.model_dump_json(indent=2) if session.resume_profile else "{}",
        )
        initial = self.llm.think([{"role": "user", "content": prompt}], temperature=0)
        score_data = extract_json(initial)

        for _ in range(REFLECTION_ROUNDS):
            reflect_prompt = load_prompt(
                "reflect_score",
                initial_score=json.dumps(score_data, ensure_ascii=False, indent=2),
                question_text=question.text,
                answer=answer,
            )
            reflect_response = self.llm.think([{"role": "user", "content": reflect_prompt}], temperature=0)
            if not reflect_response:
                break
            try:
                reflect_data = extract_json(reflect_response)
            except ValueError:
                break
            if reflect_data.get("no_change"):
                break
            score_data = reflect_data

        dimensions = []
        for d in score_data.get("dimensions", []):
            raw_score = d.get("score", 3)
            d["score"] = max(1, min(5, round(float(raw_score))))
            dimensions.append(DimensionScore.model_validate(d))
        if not dimensions:
            dimensions = [
                DimensionScore(dimension="综合", score=3, comment="自动默认分")
            ]

        total = score_data.get("total_score")
        if total is None:
            total = sum(d.score for d in dimensions) / len(dimensions)

        return QuestionScore(
            question_id=question.id,
            question_text=question.text,
            dimensions=dimensions,
            total_score=float(total),
            evidence_quotes=score_data.get("evidence_quotes", []),
            feedback=score_data.get("feedback", ""),
            high_score_framework=score_data.get("high_score_framework", ""),
            resume_inconsistency=score_data.get("resume_inconsistency"),
        )

    def _generate_summary(self, session: InterviewSession) -> InterviewSummary:
        """
        生成面试总评。

        @param session - 面试会话
        @returns 总评对象
        """
        scores_summary = "\n".join(
            f"- {s.question_id}: {s.total_score:.1f} - {s.feedback[:80]}"
            for s in session.scores
        )
        avg = sum(s.total_score for s in session.scores) / max(len(session.scores), 1)

        prompt = load_prompt(
            "summary",
            job_title=session.jd_profile.title if session.jd_profile else "产品岗",
            scores_summary=scores_summary,
            match_analysis=session.match_analysis.model_dump_json(indent=2) if session.match_analysis else "{}",
        )
        response = self.llm.think([{"role": "user", "content": prompt}], temperature=0)
        data = extract_json(response)
        data["average_score"] = data.get("average_score", avg)
        return InterviewSummary.model_validate(data)
