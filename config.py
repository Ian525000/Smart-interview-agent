"""应用配置模块。"""

import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
SESSIONS_DIR = DATA_DIR / "sessions"
REPORTS_DIR = DATA_DIR / "reports"
AUDIO_DIR = DATA_DIR / "audio"
TEMPLATES_DIR = BASE_DIR / "templates"
PROMPTS_DIR = BASE_DIR / "prompts"

for _dir in (DATA_DIR, SESSIONS_DIR, REPORTS_DIR, AUDIO_DIR):
    _dir.mkdir(parents=True, exist_ok=True)

API_KEY = os.getenv("LLM_API_KEY")
BASE_URL = os.getenv("LLM_BASE_URL")
MODEL_ID = os.getenv("LLM_MODEL_ID")
LLM_TIMEOUT = int(os.getenv("LLM_TIMEOUT", "120"))

TTS_VOICE = os.getenv("TTS_VOICE", "zh-CN-XiaoxiaoNeural")
WHISPER_MODEL = os.getenv("WHISPER_MODEL", "base")
VAD_SILENCE_MS = int(os.getenv("VAD_SILENCE_MS", "2500"))
MAX_FOLLOW_UPS = int(os.getenv("MAX_FOLLOW_UPS", "3"))
FOLLOW_UP_QUESTION_COUNT = int(os.getenv("FOLLOW_UP_QUESTION_COUNT", "3"))
REFLECTION_ROUNDS = int(os.getenv("REFLECTION_ROUNDS", "2"))
MAX_RECORD_SECONDS = int(os.getenv("MAX_RECORD_SECONDS", "120"))
SERVER_PORT = int(os.getenv("SERVER_PORT", "8001"))
