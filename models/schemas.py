"""面试会话核心数据模型。"""

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class QuestionType(str, Enum):
    """面试题型。"""

    INTRO = "intro"
    PROJECT = "project"
    CASE = "case"
    BEHAVIOR = "behavior"
    OPEN = "open"
    REVERSE = "reverse"


class InterviewPhase(str, Enum):
    """面试阶段。"""

    SETUP = "setup"
    PREVIEW = "preview"
    INTERVIEWING = "interviewing"
    SCORING = "scoring"
    COMPLETED = "completed"


class JDProfile(BaseModel):
    """岗位画像。"""

    title: str = ""
    company: str = "互联网大厂"
    level: str = ""
    core_skills: List[str] = Field(default_factory=list)
    keywords: List[str] = Field(default_factory=list)
    responsibilities: List[str] = Field(default_factory=list)
    requirements: List[str] = Field(default_factory=list)
    raw_text: str = ""


class ResumeProfile(BaseModel):
    """简历画像。"""

    name: str = ""
    years_experience: str = ""
    education: List[str] = Field(default_factory=list)
    work_experience: List[str] = Field(default_factory=list)
    projects: List[str] = Field(default_factory=list)
    skills: List[str] = Field(default_factory=list)
    highlights: List[str] = Field(default_factory=list)
    raw_text: str = ""


class MatchAnalysis(BaseModel):
    """JD 与简历匹配分析。"""

    match_points: List[str] = Field(default_factory=list)
    risk_points: List[str] = Field(default_factory=list)
    hypotheses: List[str] = Field(default_factory=list)
    overall_match_score: float = 0.0


class Question(BaseModel):
    """面试问题。"""

    id: str
    type: QuestionType
    text: str
    suggested_minutes: int = 4
    rationale: str = ""
    follow_up_enabled: bool = False


class Turn(BaseModel):
    """单轮对话。"""

    question_id: str
    agent_text: str
    user_transcript: str = ""
    audio_path: Optional[str] = None
    is_follow_up: bool = False
    timestamp: datetime = Field(default_factory=datetime.now)


class DimensionScore(BaseModel):
    """单维度评分。"""

    dimension: str
    score: int = Field(ge=1, le=5)
    comment: str = ""


class QuestionScore(BaseModel):
    """单题评分。"""

    question_id: str
    question_text: str
    dimensions: List[DimensionScore] = Field(default_factory=list)
    total_score: float = 0.0
    evidence_quotes: List[str] = Field(default_factory=list)
    feedback: str = ""
    high_score_framework: str = ""
    resume_inconsistency: Optional[str] = None


class InterviewSummary(BaseModel):
    """面试总评。"""

    strengths: List[str] = Field(default_factory=list)
    risks: List[str] = Field(default_factory=list)
    recommendation: str = ""
    average_score: float = 0.0
    next_steps: str = ""


class InterviewSession(BaseModel):
    """完整面试会话。"""

    session_id: str
    phase: InterviewPhase = InterviewPhase.SETUP
    mode: str = "text"
    jd_profile: Optional[JDProfile] = None
    resume_profile: Optional[ResumeProfile] = None
    match_analysis: Optional[MatchAnalysis] = None
    questions: List[Question] = Field(default_factory=list)
    turns: List[Turn] = Field(default_factory=list)
    follow_up_targets: List[str] = Field(default_factory=list)
    current_question_index: int = 0
    follow_up_count: int = 0
    scores: List[QuestionScore] = Field(default_factory=list)
    summary: Optional[InterviewSummary] = None
    report_path: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)
    metadata: Dict[str, Any] = Field(default_factory=dict)


class SessionCreateRequest(BaseModel):
    """创建会话请求。"""

    jd_text: Optional[str] = None
    resume_text: Optional[str] = None
    mode: str = "text"
    template_id: Optional[str] = None
    mock_mode: bool = False


class AnswerRequest(BaseModel):
    """提交回答请求。"""

    answer: str
    skip: bool = False
    retry: bool = False


class QuestionUpdateRequest(BaseModel):
    """更新问题请求。"""

    question_id: str
    text: str


class QuestionsLockRequest(BaseModel):
    """锁定问题并开始面试。"""

    questions: Optional[List[Question]] = None
