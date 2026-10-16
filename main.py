"""FastAPI 主入口。"""

import base64
from pathlib import Path
from typing import List, Optional

from fastapi import FastAPI, File, Form, HTTPException, UploadFile, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from config import BASE_DIR, MAX_RECORD_SECONDS, SERVER_PORT, VAD_SILENCE_MS
from models.schemas import AnswerRequest, Question
from services.interview_service import InterviewService
from storage.session_store import SessionStore
from voice.stt import transcribe_bytes
from voice.tts import synthesize_safe

app = FastAPI(title="智能面试 Agent", version="1.0.0")
app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")

service = InterviewService()
store = SessionStore()


async def _attach_tts(result: dict) -> dict:
    """
    为面试结果附加 TTS 音频，失败时不中断流程。

    @param result - 面试动作结果
    @returns 附加 audio_base64 后的结果
    """
    agent_text = result.get("agent_text")
    if not agent_text:
        return result
    tts_path = await synthesize_safe(agent_text)
    if tts_path:
        result["audio_base64"] = base64.b64encode(Path(tts_path).read_bytes()).decode()
    else:
        result["tts_fallback"] = True
    return result


class TextSessionRequest(BaseModel):
    """文字创建会话请求。"""

    jd_text: str
    resume_text: str
    mode: str = "text"
    template_id: Optional[str] = None
    mock_mode: bool = False


class BatchDeleteBody(BaseModel):
    """批量删除会话请求。"""

    session_ids: List[str]


class GotoQuestionBody(BaseModel):
    """跳转题目请求。"""

    question_index: int
    follow_up_index: Optional[int] = None


class UpdateQuestionBody(BaseModel):
    """批量更新问题。"""

    questions: List[Question]


@app.get("/api/health")
async def health_check():
    """供本地启动器检查服务是否已就绪。"""
    return {"status": "ok", "service": "interview-agent"}


@app.get("/", response_class=HTMLResponse)
async def index():
    """首页。"""
    html_path = BASE_DIR / "static" / "index.html"
    return HTMLResponse(html_path.read_text(encoding="utf-8"))


@app.get("/api/templates")
async def list_templates():
    """获取岗位模板列表。"""
    return {"templates": service.list_templates()}


@app.post("/api/sessions/text")
async def create_session_text(body: TextSessionRequest):
    """从文本创建会话。"""
    try:
        session = service.create_session_from_text(
            body.jd_text,
            body.resume_text,
            mode=body.mode,
            template_id=body.template_id,
            mock_mode=body.mock_mode,
        )
        return session.model_dump(mode="json")
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/api/sessions/upload")
async def create_session_upload(
    jd_file: UploadFile = File(...),
    resume_file: UploadFile = File(...),
    mode: str = Form("voice"),
    template_id: Optional[str] = Form(None),
    mock_mode: bool = Form(False),
):
    """从文件创建会话。"""
    try:
        jd_content = await jd_file.read()
        resume_content = await resume_file.read()
        session = service.create_session_from_files(
            jd_file.filename or "jd.pdf",
            jd_content,
            resume_file.filename or "resume.pdf",
            resume_content,
            mode=mode,
            template_id=template_id,
            mock_mode=mock_mode,
        )
        return session.model_dump(mode="json")
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/api/sessions")
async def list_sessions():
    """列出历史会话。"""
    return {"sessions": store.list_sessions()}


@app.post("/api/sessions/batch-delete")
async def batch_delete_sessions(body: BatchDeleteBody):
    """批量删除历史会话。须放在 /{session_id} 路由之前，避免被路径参数吞掉。"""
    deleted = service.delete_sessions(body.session_ids or [])
    if not deleted:
        raise HTTPException(status_code=404, detail="没有匹配的历史会话可删除")
    return {"ok": True, "deleted": deleted, "count": len(deleted)}


@app.get("/api/sessions/{session_id}")
async def get_session(session_id: str):
    """获取会话详情。"""
    try:
        session = service.get_session(session_id)
        return session.model_dump(mode="json")
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.delete("/api/sessions/{session_id}")
async def delete_session(session_id: str):
    """删除历史会话。"""
    deleted = service.delete_session(session_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"会话不存在: {session_id}")
    return {"ok": True, "session_id": session_id}


@app.put("/api/sessions/{session_id}/questions")
async def update_questions(session_id: str, body: UpdateQuestionBody):
    """预览阶段编辑问题。"""
    try:
        session = service.update_questions(session_id, body.questions)
        return session.model_dump(mode="json")
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.post("/api/sessions/{session_id}/start")
async def start_interview(session_id: str):
    """锁定问题并开始面试。"""
    try:
        result = service.lock_questions_and_start(session_id)
        return result
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.post("/api/sessions/{session_id}/answer")
async def submit_answer(session_id: str, body: AnswerRequest):
    """提交文字回答。"""
    try:
        result = service.submit_answer(
            session_id,
            body.answer,
            skip=body.skip,
            retry=body.retry,
        )
        return result
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.post("/api/sessions/{session_id}/goto")
async def goto_question(session_id: str, body: GotoQuestionBody):
    """面试进行中跳转到指定题目。"""
    try:
        return service.goto_question(session_id, body.question_index, body.follow_up_index)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/api/sessions/{session_id}/finish")
async def finish_interview(session_id: str):
    """结束面试并生成评分报告。"""
    try:
        return service.finish_interview(session_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.post("/api/sessions/{session_id}/score")
async def run_scoring(session_id: str):
    """手动触发打分。"""
    try:
        return service.run_scoring(session_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


def _file_download(path: Path, download_name: str, media_type: str) -> FileResponse:
    """
    构造带中文文件名的下载响应。

    @param path - 本地文件路径
    @param download_name - 浏览器保存的文件名
    @param media_type - MIME 类型
    @returns FileResponse
    """
    return FileResponse(path, filename=download_name, media_type=media_type)


@app.get("/api/sessions/{session_id}/report")
async def download_report(session_id: str, format: str = "md"):
    """下载评估报告（Markdown 或 PDF）。"""
    fmt = (format or "md").lower()
    if fmt not in {"md", "pdf"}:
        raise HTTPException(status_code=400, detail="format 仅支持 md 或 pdf")
    try:
        path = service.export_eval_report(session_id, fmt)
        name = "面试评估报告.pdf" if fmt == "pdf" else "面试评估报告.md"
        media = "application/pdf" if fmt == "pdf" else "text/markdown; charset=utf-8"
        return _file_download(path, name, media)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.get("/api/sessions/{session_id}/transcript")
async def download_transcript(session_id: str, format: str = "md"):
    """下载候选人问答实录（Markdown 或 PDF）。"""
    fmt = (format or "md").lower()
    if fmt not in {"md", "pdf"}:
        raise HTTPException(status_code=400, detail="format 仅支持 md 或 pdf")
    try:
        path = service.export_qa_transcript(session_id, fmt)
        name = "面试问答实录.pdf" if fmt == "pdf" else "面试问答实录.md"
        media = "application/pdf" if fmt == "pdf" else "text/markdown; charset=utf-8"
        return _file_download(path, name, media)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.post("/api/tts")
async def text_to_speech(text: str = Form(...)):
    """TTS 合成。"""
    try:
        audio_path = await synthesize_safe(text)
        if not audio_path:
            return {"audio_base64": None, "tts_fallback": True}
        audio_bytes = Path(audio_path).read_bytes()
        return {
            "audio_base64": base64.b64encode(audio_bytes).decode(),
            "audio_path": audio_path,
        }
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.post("/api/stt")
async def speech_to_text(audio: UploadFile = File(...)):
    """STT 转写上传音频。"""
    try:
        content = await audio.read()
        suffix = Path(audio.filename or ".webm").suffix
        text = transcribe_bytes(content, suffix=suffix)
        return {"text": text}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.websocket("/ws/interview/{session_id}")
async def interview_websocket(websocket: WebSocket, session_id: str):
    """
    语音面试 WebSocket。
    消息格式：{"type": "answer"|"start"|"skip"|"retry"|"goto"|"finish", "text": "...", "question_index": 0}
    """
    await websocket.accept()
    try:
        while True:
            data = await websocket.receive_json()
            msg_type = data.get("type", "answer")

            if msg_type == "start":
                result = service.lock_questions_and_start(session_id)
                result = await _attach_tts(result)
                await websocket.send_json({"event": "question", **result})
                continue

            if msg_type == "goto":
                fu_raw = data.get("follow_up_index", None)
                follow_up_index = None if fu_raw is None or fu_raw == "" else int(fu_raw)
                result = service.goto_question(
                    session_id,
                    int(data.get("question_index", 0)),
                    follow_up_index,
                )
                result = await _attach_tts(result)
                await websocket.send_json({"event": "question", **result})
                continue

            if msg_type == "finish":
                result = service.finish_interview(session_id)
                await websocket.send_json({"event": "complete", **result})
                continue

            answer_text = data.get("text", "")
            audio_b64 = data.get("audio")
            audio_path = None

            if audio_b64 and not answer_text:
                audio_bytes = base64.b64decode(audio_b64)
                answer_text = transcribe_bytes(audio_bytes)
                from config import AUDIO_DIR
                import uuid
                audio_path = str(AUDIO_DIR / f"ws_{uuid.uuid4().hex[:8]}.webm")
                Path(audio_path).write_bytes(audio_bytes)

            result = service.submit_answer(
                session_id,
                answer_text,
                skip=msg_type == "skip",
                retry=msg_type == "retry",
                audio_path=audio_path,
            )

            if result.get("agent_text"):
                result = await _attach_tts(result)

            event = result.get("action", "next_question")
            if result.get("done") or result.get("action") == "complete":
                event = "complete"
            await websocket.send_json({"event": event, **result})

    except WebSocketDisconnect:
        pass
    except ValueError as exc:
        await websocket.send_json({"event": "error", "message": str(exc)})
    except Exception as exc:
        await websocket.send_json({"event": "error", "message": str(exc)})


@app.get("/api/config")
async def get_config():
    """前端配置。"""
    return {"vad_silence_ms": VAD_SILENCE_MS, "max_record_seconds": MAX_RECORD_SECONDS}


def run():
    """启动服务。"""
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=SERVER_PORT, reload=False)


if __name__ == "__main__":
    run()
