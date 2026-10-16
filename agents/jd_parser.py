"""JD 与简历解析 Agent。"""

import json

from agents.prompt_loader import load_prompt
from llm_client import HelloAgentsLLM
from models.schemas import JDProfile, MatchAnalysis, ResumeProfile
from utils.json_parser import extract_json
from utils.profile_normalizer import (
    normalize_jd_profile,
    normalize_match_analysis,
    normalize_resume_profile,
)


class JDParserAgent:
    """解析 JD 和简历并生成匹配分析。"""

    def __init__(self, llm: HelloAgentsLLM):
        """
        @param llm - LLM 客户端
        """
        self.llm = llm

    def parse(self, jd_text: str, resume_text: str) -> tuple[JDProfile, ResumeProfile, MatchAnalysis]:
        """
        解析 JD 与简历文本。

        @param jd_text - 岗位 JD 文本
        @param resume_text - 简历文本
        @returns 岗位画像、简历画像、匹配分析
        """
        prompt = load_prompt("jd_parse", jd_text=jd_text, resume_text=resume_text)
        response = self.llm.think([{"role": "user", "content": prompt}], temperature=0)
        data = extract_json(response)

        jd_data = normalize_jd_profile(data.get("jd_profile", {}))
        jd_data["raw_text"] = jd_text
        resume_data = normalize_resume_profile(data.get("resume_profile", {}))
        resume_data["raw_text"] = resume_text
        match_data = normalize_match_analysis(data.get("match_analysis", {}))

        return (
            JDProfile.model_validate(jd_data),
            ResumeProfile.model_validate(resume_data),
            MatchAnalysis.model_validate(match_data),
        )

    @staticmethod
    def profiles_to_json(jd: JDProfile, resume: ResumeProfile, match: MatchAnalysis) -> dict:
        """
        将画像转为 JSON 字符串供后续 Prompt 使用。

        @param jd - 岗位画像
        @param resume - 简历画像
        @param match - 匹配分析
        @returns 字典对象
        """
        return {
            "jd_profile": json.dumps(jd.model_dump(), ensure_ascii=False, indent=2),
            "resume_profile": json.dumps(resume.model_dump(), ensure_ascii=False, indent=2),
            "match_analysis": json.dumps(match.model_dump(), ensure_ascii=False, indent=2),
        }
