"""面试问题生成 Agent（Plan & Solve）。"""

import uuid

from agents.prompt_loader import load_prompt
from llm_client import HelloAgentsLLM
from models.schemas import JDProfile, MatchAnalysis, Question, QuestionType, ResumeProfile
from utils.json_parser import extract_json

QUESTION_TYPE_MAP = {
    "intro": QuestionType.INTRO,
    "project": QuestionType.PROJECT,
    "case": QuestionType.CASE,
    "behavior": QuestionType.BEHAVIOR,
    "open": QuestionType.OPEN,
    "reverse": QuestionType.REVERSE,
}


class QuestionGeneratorAgent:
    """Plan & Solve 模式生成 10 道面试题。"""

    def __init__(self, llm: HelloAgentsLLM):
        """
        @param llm - LLM 客户端
        """
        self.llm = llm

    def generate(
        self,
        jd: JDProfile,
        resume: ResumeProfile,
        match: MatchAnalysis,
    ) -> list[Question]:
        """
        生成 10 道结构化面试题。

        @param jd - 岗位画像
        @param resume - 简历画像
        @param match - 匹配分析
        @returns 问题列表
        """
        ctx = {
            "jd_profile": jd.model_dump_json(indent=2),
            "resume_profile": resume.model_dump_json(indent=2),
            "match_analysis": match.model_dump_json(indent=2),
        }

        plan_prompt = load_prompt("question_plan", **ctx)
        plan_response = self.llm.think([{"role": "user", "content": plan_prompt}], temperature=0)
        plan_items = extract_json(plan_response)
        if not isinstance(plan_items, list):
            raise ValueError("出题计划必须是 JSON 数组。")

        questions: list[Question] = []
        for item in plan_items[:10]:
            gen_prompt = load_prompt(
                "question_gen",
                index=item.get("index", len(questions) + 1),
                plan_item=str(item),
                **ctx,
            )
            gen_response = self.llm.think([{"role": "user", "content": gen_prompt}], temperature=0.3)
            gen_data = extract_json(gen_response)

            q_type = QUESTION_TYPE_MAP.get(item.get("type", "open"), QuestionType.OPEN)
            questions.append(
                Question(
                    id=f"q{len(questions) + 1}",
                    type=q_type,
                    text=gen_data.get("text", ""),
                    suggested_minutes=int(item.get("suggested_minutes", 4)),
                    rationale=item.get("rationale", ""),
                    follow_up_enabled=bool(gen_data.get("follow_up_enabled", q_type in {
                        QuestionType.PROJECT, QuestionType.CASE, QuestionType.BEHAVIOR
                    })),
                )
            )

        self._ensure_follow_up_targets(questions)
        return questions

    @staticmethod
    def _ensure_follow_up_targets(questions: list[Question]) -> None:
        """
        确保有 2-3 题可深度追问。

        @param questions - 问题列表（原地修改 follow_up_enabled）
        """
        enabled = [q for q in questions if q.follow_up_enabled]
        if len(enabled) >= 2:
            return
        for q in questions:
            if q.type in (QuestionType.PROJECT, QuestionType.CASE, QuestionType.BEHAVIOR):
                q.follow_up_enabled = True

    def generate_from_template(self, template_questions: list[dict]) -> list[Question]:
        """
        从岗位模板生成问题列表。

        @param template_questions - 模板问题配置
        @returns 问题列表
        """
        questions: list[Question] = []
        for idx, item in enumerate(template_questions[:10], start=1):
            q_type = QUESTION_TYPE_MAP.get(item.get("type", "open"), QuestionType.OPEN)
            questions.append(
                Question(
                    id=item.get("id", f"q{idx}"),
                    type=q_type,
                    text=item.get("text", ""),
                    suggested_minutes=int(item.get("suggested_minutes", 4)),
                    rationale=item.get("rationale", "来自岗位模板"),
                    follow_up_enabled=bool(item.get("follow_up_enabled", False)),
                )
            )
        return questions
