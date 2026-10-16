/**
 * 智能面试 Agent 前端逻辑
 */

let sessionId = null;
let currentSession = null;
let ws = null;
let recognition = null;
let lastAudioBase64 = null;
let answerMode = null;
let isTyping = false;
let displayedTranscript = "";
let currentAgentText = "";
let micStream = null;
let mediaRecorder = null;
let audioChunks = [];
let micPermissionGranted = false;
let isRecording = false;
let savedAnswerText = "";
let sessionFinalTranscript = "";
let sessionInterimTranscript = "";
let recordingTimerInterval = null;
let recordingDeadline = null;
let maxRecordSeconds = 120;
let recordingUseFallback = false;
let currentQuestionIndex = 0;
let currentFollowUpIndex = null;
let questionsStatus = [];
let interviewTotal = 0;
let typewriterGeneration = 0;
let currentAgentAudio = null;

const QUESTION_TYPE_LABELS = {
  intro: "自我介绍",
  project: "项目深挖",
  case: "产品 Case",
  behavior: "行为面试",
  open: "开放题",
  reverse: "反问环节",
};

const steps = [
  "step-upload",
  "step-preview",
  "step-mode",
  "step-interview",
  "step-report",
];

/** 切换步骤面板 */
function showStep(stepId) {
  const activeIndex = steps.indexOf(stepId);
  const previousStep = document.querySelector(".step.active")?.id;
  document.body.dataset.step = stepId;
  const landingHero = document.getElementById("landing-hero");
  if (landingHero) landingHero.hidden = stepId !== "step-upload";
  steps.forEach((id) => {
    document.getElementById(id).classList.toggle("active", id === stepId);
  });
  document.querySelectorAll(".workflow-step").forEach((step, index) => {
    step.classList.toggle("active", index === activeIndex);
    step.classList.toggle("done", index < activeIndex);
    if (index === activeIndex) step.setAttribute("aria-current", "step");
    else step.removeAttribute("aria-current");
  });
  document.querySelector(".container")?.classList.toggle(
    "interview-wide",
    stepId === "step-interview" || stepId === "step-report"
  );
  if (previousStep !== stepId) window.scrollTo({ top: 0, behavior: "instant" });
}

function setSpeechState(message, speaking = false) {
  const state = document.getElementById("speech-state");
  if (!state) return;
  state.textContent = message;
  state.classList.toggle("speaking", speaking);
}

/** 设置状态文本 */
function setStatus(elId, msg, type = "") {
  const el = document.getElementById(elId);
  if (!el) return;
  el.textContent = msg;
  el.className = `status ${type}`;
}

/** 读取真实接口响应，将失败信息转换为可阅读的提示。 */
async function readApiResponse(response, fallbackMessage) {
  const data = await response.json().catch(() => null);
  if (!response.ok) {
    const detail = data?.detail;
    const message = typeof detail === "string"
      ? detail
      : Array.isArray(detail) ? detail.map(item => item.msg).filter(Boolean).join("；") : "";
    throw new Error(message || `${fallbackMessage}（${response.status}）`);
  }
  if (!data || typeof data !== "object") throw new Error(fallbackMessage);
  return data;
}

function requestErrorMessage(error, fallbackMessage) {
  return error instanceof TypeError ? "暂时无法连接服务，请确认服务运行后重试。" : error.message || fallbackMessage;
}

/** 打字机效果 */
function typewriterEffect(elementId, text, speed = 30) {
  return new Promise((resolve) => {
    const generation = ++typewriterGeneration;
    const el = document.getElementById(elementId);
    el.textContent = "";
    el.classList.add("typing");
    isTyping = true;
    let index = 0;

    const tick = () => {
      if (generation !== typewriterGeneration) {
        el.classList.remove("typing");
        isTyping = false;
        resolve();
        return;
      }
      if (index >= text.length) {
        el.classList.remove("typing");
        isTyping = false;
        resolve();
        return;
      }
      el.textContent += text[index];
      index += 1;
      setTimeout(tick, speed);
    };
    tick();
  });
}

/** 重置本题回答文本 */
function resetAnswerText(clearSaved = true) {
  sessionFinalTranscript = "";
  sessionInterimTranscript = "";
  displayedTranscript = "";
  if (clearSaved) savedAnswerText = "";
  updateAnswerDisplay();
}

/**
 * 将当前识别会话文本并入已保存回答，并清空会话缓冲。
 * 停顿后 Web Speech API 会结束并重启识别，必须先提交再重启，否则新旧内容会重复拼接。
 */
function commitSessionTranscript() {
  const current = `${sessionFinalTranscript}${sessionInterimTranscript}`.trim();
  if (current) {
    savedAnswerText = savedAnswerText ? `${savedAnswerText}${current}` : current;
  }
  sessionFinalTranscript = "";
  sessionInterimTranscript = "";
}

/** 合并并更新回答展示区 */
function updateAnswerDisplay() {
  const current = sessionFinalTranscript + sessionInterimTranscript;
  let full = savedAnswerText;
  if (current) {
    full = full ? `${full}${current}` : current;
  }
  full = full.trim();
  const el = document.getElementById("user-transcript");
  el.textContent = full || (isRecording ? "（正在聆听，请开始说话...）" : "（点击「开始回答」后说话）");
  document.getElementById("text-answer").value = full;
  displayedTranscript = full;
}

/** 格式化倒计时 mm:ss */
function formatCountdown(ms) {
  const totalSec = Math.max(0, Math.ceil(ms / 1000));
  const min = Math.floor(totalSec / 60);
  const sec = totalSec % 60;
  return `${min}:${sec.toString().padStart(2, "0")}`;
}

/** 启动录音倒计时 */
function startRecordingTimer() {
  stopRecordingTimer();
  recordingDeadline = Date.now() + maxRecordSeconds * 1000;
  const timerEl = document.getElementById("recording-timer");
  timerEl.classList.remove("hidden", "warning", "danger");
  timerEl.textContent = `录音剩余 ${formatCountdown(maxRecordSeconds * 1000)}`;

  recordingTimerInterval = setInterval(() => {
    const remain = recordingDeadline - Date.now();
    timerEl.textContent = `录音剩余 ${formatCountdown(remain)}`;

    if (remain <= 10000) {
      timerEl.classList.add("danger");
      timerEl.classList.remove("warning");
    } else if (remain <= 30000) {
      timerEl.classList.add("warning");
      timerEl.classList.remove("danger");
    } else {
      timerEl.classList.remove("warning", "danger");
    }

    if (remain <= 0) {
      setStatus("interview-status", "已达 2 分钟录音上限，已自动停止", "success");
      stopRecording(true);
    }
  }, 200);
}

/** 停止录音倒计时 */
function stopRecordingTimer() {
  if (recordingTimerInterval) {
    clearInterval(recordingTimerInterval);
    recordingTimerInterval = null;
  }
  recordingDeadline = null;
  const timerEl = document.getElementById("recording-timer");
  timerEl.classList.add("hidden");
  timerEl.classList.remove("warning", "danger");
}

/** 麦克风权限说明 */
function micErrorMessage(error) {
  const map = {
    "not-allowed": "浏览器拒绝了麦克风权限。请点击地址栏左侧「锁/设置」图标 → 麦克风 → 允许，然后刷新页面重试。",
    "service-not-allowed": "当前环境不允许使用麦克风。请用 Chrome 打开 http://localhost:8001（不要用 IP 地址），或改用文字输入模式。",
    "no-speech": "未检测到语音，请靠近麦克风再试一次。",
    "network": "语音识别网络异常。可改用文字模式，或使用录音降级（仍会自动转写）。",
    "audio-capture": "未找到可用麦克风，请检查系统是否已连接并启用麦克风设备。",
  };
  return map[error] || `语音识别异常: ${error}`;
}

/** 检测麦克风权限状态 */
async function queryMicPermissionState() {
  if (!navigator.permissions?.query) return "unknown";
  try {
    const status = await navigator.permissions.query({ name: "microphone" });
    return status.state;
  } catch (_) {
    return "unknown";
  }
}

/** 请求麦克风权限（仅验证，不长期占用设备） */
async function requestMicPermission() {
  if (!navigator.mediaDevices?.getUserMedia) {
    throw new Error("当前浏览器不支持麦克风访问，请改用文字输入模式。");
  }

  const state = await queryMicPermissionState();
  if (state === "denied") {
    throw new Error("麦克风权限被拒绝。请在浏览器地址栏设置中允许麦克风。");
  }

  const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
  stream.getTracks().forEach((track) => track.stop());
  micStream = null;
  micPermissionGranted = true;
  return true;
}

/** 获取录音流（开始录音时调用） */
async function acquireMicStream() {
  if (micStream && micStream.active) {
    return micStream;
  }
  micStream = await navigator.mediaDevices.getUserMedia({ audio: true });
  micPermissionGranted = true;
  return micStream;
}

/** 释放麦克风 */
function releaseMicStream() {
  if (micStream) {
    micStream.getTracks().forEach((track) => track.stop());
    micStream = null;
  }
  micPermissionGranted = false;
}

/** 停止面试官语音播报 */
function stopAgentSpeech() {
  if (currentAgentAudio) {
    currentAgentAudio.pause();
    currentAgentAudio.src = "";
    currentAgentAudio = null;
  }
  if (window.speechSynthesis) {
    window.speechSynthesis.cancel();
  }
}

/** 浏览器语音播报（TTS 降级） */
function speakText(text) {
  return new Promise((resolve) => {
    if (!window.speechSynthesis) {
      resolve();
      return;
    }
    window.speechSynthesis.cancel();
    const utterance = new SpeechSynthesisUtterance(text);
    utterance.lang = "zh-CN";
    utterance.rate = 1;
    utterance.onend = () => resolve();
    utterance.onerror = () => resolve();
    window.speechSynthesis.speak(utterance);
  });
}

/** 播放服务端 TTS 或浏览器降级 */
function playAgentSpeech(text, audioBase64) {
  stopAgentSpeech();
  if (audioBase64) {
    return new Promise((resolve) => {
      const audio = new Audio(`data:audio/mp3;base64,${audioBase64}`);
      currentAgentAudio = audio;
      audio.onended = () => {
        if (currentAgentAudio === audio) currentAgentAudio = null;
        resolve();
      };
      audio.onerror = () => speakText(text).then(resolve);
      audio.play().catch(() => speakText(text).then(resolve));
    });
  }
  return speakText(text);
}

/** 重置模式选择页 */
function resetModeStep() {
  answerMode = null;
  ["btn-mode-voice", "btn-mode-text"].forEach((id) => {
    const button = document.getElementById(id);
    button.classList.remove("selected");
    button.setAttribute("aria-pressed", "false");
    button.querySelector("em").textContent = "点击选择";
  });
  document.getElementById("btn-begin-interview").disabled = true;
  setStatus("mode-status", "请选择一种回答方式（应用于全部题目）", "");
}

/** 重置面试对话页 */
function resetInterviewStep() {
  displayedTranscript = "";
  currentAgentText = "";
  lastAudioBase64 = null;
  savedAnswerText = "";
  sessionFinalTranscript = "";
  sessionInterimTranscript = "";
  isRecording = false;
  stopRecordingTimer();
  recordingUseFallback = false;
  document.getElementById("agent-text").textContent = "等待第一题...";
  document.getElementById("agent-role-label").textContent = "面试官";
  document.getElementById("interview-heading").textContent = "正式面试";
  document.getElementById("interview-description").textContent = "阅读或听完问题后作答；面试官会根据回答选择追问。";
  setSpeechState("等待提问");
  document.getElementById("user-transcript").textContent = "（点击「开始回答」后说话）";
  document.getElementById("answer-helper").textContent = "回答内容会保留到提交或重答本题。";
  document.getElementById("text-answer").value = "";
  document.getElementById("progress-fill").style.width = "0%";
  document.getElementById("progress-text").textContent = "准备中...";
  document.getElementById("btn-replay").disabled = true;
  document.getElementById("btn-mic").classList.remove("recording");
  document.getElementById("btn-mic").textContent = "🎤 开始回答";
  currentQuestionIndex = 0;
  currentFollowUpIndex = null;
  questionsStatus = [];
  seedQuestionNav();
}

/** 选择回答方式（整场面试） */
function selectAnswerMode(mode) {
  answerMode = mode;
  [["btn-mode-voice", "voice"], ["btn-mode-text", "text"]].forEach(([id, value]) => {
    const button = document.getElementById(id);
    const selected = mode === value;
    button.classList.toggle("selected", selected);
    button.setAttribute("aria-pressed", String(selected));
    button.querySelector("em").textContent = selected ? "已选择" : "点击选择";
  });
  document.getElementById("btn-begin-interview").disabled = false;
  setStatus(
    "mode-status",
    mode === "voice" ? "已选择：语音输入（全部题目）" : "已选择：文字输入（全部题目）",
    "success"
  );
}

/** 应用回答方式 UI */
function applyAnswerModeUI() {
  const micBtn = document.getElementById("btn-mic");
  const textArea = document.getElementById("text-answer");
  const transcript = document.getElementById("user-transcript");
  const label = document.getElementById("answer-mode-label");

  if (answerMode === "voice") {
    label.textContent = "当前模式：语音输入";
    micBtn.classList.remove("hidden");
    textArea.classList.add("hidden");
    transcript.classList.remove("hidden");
  } else {
    label.textContent = "当前模式：文字输入";
    micBtn.classList.add("hidden");
    textArea.classList.remove("hidden");
    transcript.classList.add("hidden");
    textArea.focus();
  }
}

/** 加载历史会话 */
async function loadSessions() {
  const list = document.getElementById("session-list");
  const checkAll = document.getElementById("session-check-all");
  const kept = new Set(getSelectedSessionIds());
  const res = await fetch("/api/sessions");
  const data = await readApiResponse(res, "历史会话加载失败");
  const sessions = data.sessions || [];

  list.innerHTML = "";
  if (!sessions.length) {
    list.innerHTML = '<p class="session-empty">还没有历史面试。完成第一场后，可在这里继续或查看报告。</p>';
    if (checkAll) checkAll.checked = false;
    updateSessionSelectionCount();
    return;
  }

  sessions.forEach((s) => {
    const id = s.session_id;
    const label = s.label || formatSessionLabel(s);
    const row = document.createElement("label");
    row.className = "session-item";
    const box = document.createElement("input");
    box.type = "checkbox";
    box.className = "session-check";
    box.value = id;
    box.checked = kept.has(id);
    box.addEventListener("change", updateSessionSelectionCount);
    const text = document.createElement("span");
    text.className = "session-item-label";
    text.textContent = label;
    row.appendChild(box);
    row.appendChild(text);
    list.appendChild(row);
  });

  if (checkAll) {
    checkAll.checked = sessions.length > 0 && kept.size === sessions.length;
  }
  updateSessionSelectionCount();
}

/**
 * 读取当前勾选的历史会话 ID。
 * @returns {string[]}
 */
function getSelectedSessionIds() {
  return [...document.querySelectorAll(".session-check:checked")].map((el) => el.value);
}

/** 更新已选条数与全选框状态 */
function updateSessionSelectionCount() {
  const boxes = [...document.querySelectorAll(".session-check")];
  const selected = boxes.filter((el) => el.checked).length;
  const countEl = document.getElementById("session-selected-count");
  if (countEl) countEl.textContent = `已选 ${selected} 条`;
  const checkAll = document.getElementById("session-check-all");
  if (checkAll) {
    checkAll.checked = boxes.length > 0 && selected === boxes.length;
    checkAll.indeterminate = selected > 0 && selected < boxes.length;
  }
}

/** 全选或取消全选历史会话 */
function toggleSelectAllSessions(event) {
  const checked = event.target.checked;
  document.querySelectorAll(".session-check").forEach((el) => {
    el.checked = checked;
  });
  updateSessionSelectionCount();
}

/** 恢复历史会话：回到题目预览页，不自动开始面试 */
async function resumeSession() {
  const ids = getSelectedSessionIds();
  if (ids.length !== 1) {
    setStatus("upload-status", ids.length ? "恢复会话时请只勾选 1 条" : "请先勾选要恢复的历史会话", "error");
    return;
  }
  const id = ids[0];
  const res = await fetch(`/api/sessions/${id}`);
  if (!res.ok) {
    setStatus("upload-status", "会话不存在", "error");
    await loadSessions();
    return;
  }
  const session = await res.json();
  if (ws) {
    try { ws.close(); } catch (_) { /* ignore */ }
    ws = null;
  }
  resetModeStep();
  resetInterviewStep();
  answerMode = null;
  sessionId = session.session_id;
  currentSession = session;

  renderPreview(session);
  showStep("step-preview");

  const progressHint = session.phase === "interviewing" && (session.turns || []).length
    ? `上次进行到第 ${(session.current_question_index || 0) + 1} 题，开始后将从当前进度继续。`
    : "确认题目后，点击「下一步」选择回答方式，再开始面试。";
  const doneHint = session.phase === "completed"
    ? "该场面试已完成，可查看报告；若再次开始将重新面试。"
    : progressHint;
  setStatus("preview-status", `已恢复：${session.jd_profile?.title || "未命名岗位"}。${doneHint}`, "success");
}

/** 删除勾选的历史会话（支持批量） */
async function deleteSession() {
  const ids = getSelectedSessionIds();
  if (!ids.length) {
    setStatus("upload-status", "请先勾选要删除的历史会话", "error");
    return;
  }
  const hint = ids.length === 1 ? "该条历史会话" : `选中的 ${ids.length} 条历史会话`;
  if (!window.confirm(`确定删除${hint}？此操作不可恢复。`)) {
    return;
  }

  const res = await fetch("/api/sessions/batch-delete", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ session_ids: ids }),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    setStatus("upload-status", typeof err.detail === "string" ? err.detail : "删除失败，请刷新后重试", "error");
    await loadSessions();
    return;
  }
  const data = await res.json();
  const deleted = data.deleted || ids;

  if (sessionId && deleted.includes(sessionId)) {
    sessionId = null;
    currentSession = null;
    if (ws) {
      try { ws.close(); } catch (_) { /* ignore */ }
      ws = null;
    }
  }

  await loadSessions();
  setStatus("upload-status", `已删除 ${deleted.length} 条历史会话`, "success");
}

/**
 * 前端兜底生成会话展示名。
 * @param {object} session - 会话摘要
 * @returns {string}
 */
function formatSessionLabel(session) {
  const timeSource = session.created_at || session.updated_at || "";
  const timeStr = String(timeSource).replace("T", " ").slice(0, 16);
  const title = session.job_title || "未命名岗位";
  const phase = session.phase_label || session.phase || "";
  return [timeStr, title, phase].filter(Boolean).join(" · ");
}

/** 加载岗位模板 */
async function loadTemplates() {
  const res = await fetch("/api/templates");
  const data = await readApiResponse(res, "岗位模板加载失败");
  const select = document.getElementById("template-select");
  (data.templates || []).forEach((t) => {
    const opt = document.createElement("option");
    opt.value = t.id;
    opt.textContent = `${t.name} - ${t.description}`;
    select.appendChild(opt);
  });
}

/** 创建会话 */
async function createSession() {
  const btn = document.getElementById("btn-create");
  if (btn.disabled) return;
  const jdFile = document.getElementById("jd-file").files[0];
  const resumeFile = document.getElementById("resume-file").files[0];
  const jdText = document.getElementById("jd-text").value.trim();
  const resumeText = document.getElementById("resume-text").value.trim();
  const templateId = document.getElementById("template-select").value || null;
  const mockMode = document.getElementById("mock-mode").checked;

  if (!(jdFile && resumeFile) && !(jdText && resumeText)) {
    setStatus("upload-status", "请上传 JD 和简历两个文件，或粘贴两份文本。", "error");
    return;
  }
  const originalLabel = btn.textContent;
  btn.disabled = true;
  btn.setAttribute("aria-busy", "true");
  btn.classList.add("is-loading");
  btn.textContent = "正在生成面试题…";
  setStatus("upload-status", "正在解析并生成面试题，请稍候...", "");

  try {
    let session;
    if (jdFile && resumeFile) {
      const form = new FormData();
      form.append("jd_file", jdFile);
      form.append("resume_file", resumeFile);
      form.append("mode", "voice");
      if (templateId) form.append("template_id", templateId);
      form.append("mock_mode", mockMode);
      const res = await fetch("/api/sessions/upload", { method: "POST", body: form });
      session = await readApiResponse(res, "资料上传失败");
    } else if (jdText && resumeText) {
      const res = await fetch("/api/sessions/text", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          jd_text: jdText,
          resume_text: resumeText,
          mode: "voice",
          template_id: templateId,
          mock_mode: mockMode,
        }),
      });
      session = await readApiResponse(res, "面试题生成失败");
    } else {
      throw new Error("请上传文件或粘贴 JD 和简历文本");
    }

    sessionId = session.session_id;
    currentSession = session;
    renderPreview(session);
    showStep("step-preview");
    setStatus("upload-status", "生成成功！", "success");
    await loadSessions().catch(() => {
      setStatus("preview-status", "题目已生成。历史列表暂时未刷新，稍后可在首页点击刷新。", "");
    });
  } catch (err) {
    setStatus("upload-status", requestErrorMessage(err, "面试题生成失败"), "error");
  } finally {
    btn.disabled = false;
    btn.removeAttribute("aria-busy");
    btn.classList.remove("is-loading");
    btn.textContent = originalLabel;
  }
}

/** 渲染问题预览 */
function renderPreview(session) {
  const info = document.getElementById("session-info");
  const jd = session.jd_profile || {};
  const resume = session.resume_profile || {};
  const created = String(session.created_at || "").replace("T", " ").slice(0, 16);
  info.innerHTML = `
    <p><strong>会话:</strong> ${escapeHtml(created || session.session_id)} · ${escapeHtml(jd.title || "未命名岗位")}</p>
    <p><strong>公司:</strong> ${escapeHtml(jd.company || "互联网大厂")}</p>
    <p><strong>候选人:</strong> ${escapeHtml(resume.name || "未知")}</p>
    ${session.match_analysis ? `<p><strong>匹配度:</strong> ${escapeHtml(session.match_analysis.overall_match_score)}/100</p>` : ""}
  `;

  const list = document.getElementById("questions-list");
  list.innerHTML = "";
  session.questions.forEach((q, i) => {
    const isFollowUp = (session.follow_up_targets || []).includes(q.id);
    const div = document.createElement("div");
    div.className = "question-item";
    div.innerHTML = `
      <div class="q-header">
        <span>第 ${i + 1} 题 <span class="tag">${escapeHtml(QUESTION_TYPE_LABELS[q.type] || q.type || "面试题")}</span>
          ${isFollowUp ? '<span class="tag follow-up">可深度追问</span>' : ""}
        </span>
        <span>${escapeHtml(q.suggested_minutes || 2)} 分钟</span>
      </div>
      <textarea data-qid="${escapeHtml(q.id)}" rows="2">${escapeHtml(q.text)}</textarea>
    `;
    list.appendChild(div);
  });

  const reportBtn = document.getElementById("btn-view-report");
  const hasReport = session.phase === "completed" || (session.scores || []).length > 0;
  reportBtn.classList.toggle("hidden", !hasReport);
}

/** 保存问题并进入模式选择页 */
async function goToModeStep() {
  const btn = document.getElementById("btn-to-mode");
  btn.disabled = true;
  setStatus("preview-status", "正在保存题目...", "");

  try {
    const textareas = document.querySelectorAll("#questions-list textarea");
    const questions = (currentSession?.questions || []).map((q, i) => {
      const ta = textareas[i];
      return { ...q, text: ta ? ta.value : q.text };
    });
    if (!questions.length || questions.some(q => !q.text.trim())) {
      throw new Error("请补全每道题的内容后再开始面试。");
    }

    const res = await fetch(`/api/sessions/${sessionId}/questions`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ questions }),
    });
    currentSession = await readApiResponse(res, "保存题目失败");

    resetModeStep();
    showStep("step-mode");
    setStatus("mode-status", "请选择回答方式，然后点击「确认并开始面试」", "success");
  } catch (err) {
    setStatus("preview-status", requestErrorMessage(err, "保存题目失败"), "error");
  } finally {
    btn.disabled = false;
  }
}

/** 确认模式并开始正式面试 */
async function beginInterview() {
  if (!answerMode) {
    setStatus("mode-status", "请先选择语音或文字输入", "error");
    return;
  }

  const btn = document.getElementById("btn-begin-interview");
  btn.disabled = true;
  document.getElementById("btn-mode-back").disabled = true;

  if (answerMode === "voice") {
    setStatus("mode-status", "正在检测麦克风...", "");
    try {
      await requestMicPermission();
      setStatus("mode-status", "麦克风已就绪，正在进入面试...", "success");
    } catch (err) {
      setStatus(
        "mode-status",
        `${err.message} 仍将进入面试，点击「开始回答」时可再次授权或使用录音转写。`,
        "error"
      );
    }
  }

  recordingUseFallback = false;
  resetInterviewStep();
  applyAnswerModeUI();
  showStep("step-interview");
  setStatus("interview-status", "正在连接面试官，请稍候...", "");
  connectWebSocket();
  btn.disabled = false;
  document.getElementById("btn-mode-back").disabled = false;
}

/**
 * 根据当前会话预填左侧题号列表，避免进入面试页时导航为空。
 */
function seedQuestionNav() {
  const qs = currentSession?.questions || [];
  interviewTotal = qs.length || interviewTotal;
  const statuses = qs.map((q, i) => ({
    index: i,
    id: q.id,
    type: q.type,
    text: q.text,
    active: i === currentQuestionIndex,
    current: i === currentQuestionIndex && currentFollowUpIndex == null,
    answered: false,
    skipped: false,
    follow_ups: [],
  }));
  renderQuestionNav(statuses);
}

/**
 * 截取导航展示文本。
 * @param {string} text
 * @param {number} max
 * @returns {string}
 */
function truncateNavText(text, max = 22) {
  const value = String(text || "").replace(/\s+/g, " ").trim();
  if (value.length <= max) return value;
  return `${value.slice(0, max)}…`;
}

/**
 * 主问题导航标题。
 * @param {object} item
 * @param {number} index
 * @returns {string}
 */
function mainQuestionLabel(item, index) {
  const typeLabel = QUESTION_TYPE_LABELS[item.type] || "";
  const text = truncateNavText(item.text || "", typeLabel ? 14 : 22);
  if (typeLabel && text) return `${index + 1}. ${typeLabel}`;
  if (typeLabel) return `${index + 1}. ${typeLabel}`;
  return `${index + 1}. ${text || "面试题"}`;
}

/**
 * 渲染左侧题目导航（含追问子项）。
 * @param {Array} statuses - 各题状态
 */
function renderQuestionNav(statuses) {
  const nav = document.getElementById("question-nav");
  if (!nav) return;
  if (Array.isArray(statuses) && statuses.length) {
    questionsStatus = statuses;
  }
  const questions = currentSession?.questions || [];
  const total = Math.max(
    questionsStatus.length,
    questions.length,
    interviewTotal || 0
  );
  nav.innerHTML = "";
  for (let i = 0; i < total; i++) {
    const st = questionsStatus.find((item) => item.index === i) || {
      index: i,
      follow_ups: [],
    };
    const q = questions[i] || {};
    const item = { ...st, text: st.text || q.text, type: st.type || q.type };

    const wrap = document.createElement("div");
    wrap.className = "q-nav-item";

    const mainBtn = document.createElement("button");
    mainBtn.type = "button";
    mainBtn.className = "q-nav-main";
    if (item.current) mainBtn.classList.add("current");
    if (item.active && !item.current) mainBtn.classList.add("active");
    if (item.answered) mainBtn.classList.add("answered");
    if (item.skipped) mainBtn.classList.add("skipped");
    mainBtn.textContent = mainQuestionLabel(item, i);
    mainBtn.title = item.text || `跳转到第 ${i + 1} 题`;
    mainBtn.addEventListener("click", () => jumpToQuestion(i, null));
    wrap.appendChild(mainBtn);

    const followUps = item.follow_ups || [];
    if (followUps.length) {
      const subWrap = document.createElement("div");
      subWrap.className = "q-nav-subs";
      followUps.forEach((fu, j) => {
        const subBtn = document.createElement("button");
        subBtn.type = "button";
        subBtn.className = "q-nav-sub";
        if (fu.current) subBtn.classList.add("current");
        if (fu.answered) subBtn.classList.add("answered");
        subBtn.textContent = `${i + 1}.${j + 1} 追问`;
        subBtn.title = fu.text || `第 ${i + 1} 题追问 ${j + 1}`;
        subBtn.addEventListener("click", () => jumpToQuestion(i, j));
        subWrap.appendChild(subBtn);
      });
      wrap.appendChild(subWrap);
    }

    nav.appendChild(wrap);
  }

  updatePrevNextButtons();
}

/**
 * 扁平化导航顺序：主问题与其追问交替排列。
 * @returns {Array<{questionIndex: number, followUpIndex: number|null}>}
 */
function getNavSequence() {
  const seq = [];
  const total = Math.max(questionsStatus.length, currentSession?.questions?.length || 0, interviewTotal || 0);
  for (let i = 0; i < total; i++) {
    const st = questionsStatus.find((item) => item.index === i) || { follow_ups: [] };
    seq.push({ questionIndex: i, followUpIndex: null });
    (st.follow_ups || []).forEach((_, j) => {
      seq.push({ questionIndex: i, followUpIndex: j });
    });
  }
  return seq;
}

/** 根据当前位置启用或禁用上一题 / 下一题 */
function updatePrevNextButtons() {
  const seq = getNavSequence();
  const pos = seq.findIndex(
    (x) => x.questionIndex === currentQuestionIndex && x.followUpIndex === currentFollowUpIndex
  );
  const resolved = pos >= 0 ? pos : seq.findIndex((x) => x.questionIndex === currentQuestionIndex);
  const prevBtn = document.getElementById("btn-prev-q");
  const nextBtn = document.getElementById("btn-next-q");
  if (prevBtn) prevBtn.disabled = seq.length === 0 || resolved <= 0;
  if (nextBtn) nextBtn.disabled = seq.length === 0 || resolved < 0 || resolved >= seq.length - 1;
}

/**
 * 上一题 / 下一题，按左侧列表（含追问）顺序跳转。
 * @param {number} delta - -1 或 1
 */
function jumpRelative(delta) {
  const seq = getNavSequence();
  let pos = seq.findIndex(
    (x) => x.questionIndex === currentQuestionIndex && x.followUpIndex === currentFollowUpIndex
  );
  if (pos < 0) {
    pos = seq.findIndex((x) => x.questionIndex === currentQuestionIndex && x.followUpIndex == null);
  }
  const target = seq[pos + delta];
  if (!target) return;
  jumpToQuestion(target.questionIndex, target.followUpIndex);
}

/**
 * 根据状态更新进度条与导航。
 * @param {object} data - 面试推送数据
 */
function updateQuestionProgress(data) {
  if (Array.isArray(data.questions) && data.questions.length) {
    if (!currentSession) currentSession = {};
    currentSession.questions = data.questions;
  }
  if (data.total) interviewTotal = data.total;
  if (data.question_index !== undefined) {
    currentQuestionIndex = data.question_index;
  }
  currentFollowUpIndex = data.current_follow_up_index == null ? null : data.current_follow_up_index;
  if (data.action === "follow_up" && currentFollowUpIndex == null) {
    const st = (data.questions_status || []).find((s) => s.index === currentQuestionIndex);
    const currentFu = (st?.follow_ups || []).find((fu) => fu.current);
    currentFollowUpIndex = currentFu ? currentFu.index : null;
  }
  renderQuestionNav(data.questions_status || questionsStatus);

  const total = interviewTotal || data.total || currentSession?.questions?.length || 0;
  if (!total) return;
  const doneCount = (questionsStatus || []).filter((s) => s.answered || s.skipped).length;
  const pct = Math.max(((currentQuestionIndex + 1) / total) * 100, (doneCount / total) * 100);
  document.getElementById("progress-fill").style.width = `${pct}%`;
  const fuLabel = currentFollowUpIndex == null ? "" : `.${currentFollowUpIndex + 1}`;
  document.getElementById("progress-text").textContent =
    currentFollowUpIndex == null
      ? `第 ${currentQuestionIndex + 1} / ${total} 题`
      : `第 ${currentQuestionIndex + 1}${fuLabel} 追问 / 共 ${total} 题`;
  const question = currentSession?.questions?.[currentQuestionIndex];
  const typeLabel = QUESTION_TYPE_LABELS[question?.type] || "面试题";
  const isFollowUp = currentFollowUpIndex != null;
  document.getElementById("interview-heading").textContent =
    `第 ${currentQuestionIndex + 1} / ${total} 题 · ${isFollowUp ? "追问" : typeLabel}`;
  document.getElementById("interview-description").textContent = isFollowUp
    ? "请针对刚才的回答补充具体细节。"
    : `建议用时 ${question?.suggested_minutes || 2} 分钟 · 听完问题后再开始回答。`;
  document.getElementById("agent-role-label").textContent =
    `面试官 · ${isFollowUp ? "追问" : typeLabel}`;
}

/**
 * 跳转到指定题目或追问。
 * @param {number} index - 主问题序号（0 起）
 * @param {number|null} followUpIndex - 追问序号，null 表示主问题
 */
async function jumpToQuestion(index, followUpIndex = null) {
  if (!ws || ws.readyState !== WebSocket.OPEN) {
    setStatus("interview-status", "连接已断开，无法跳转题目", "error");
    return;
  }
  const total = interviewTotal || (currentSession?.questions || []).length || questionsStatus.length;
  if (index < 0 || (total && index >= total)) return;
  if (index === currentQuestionIndex && followUpIndex === currentFollowUpIndex) return;

  const live = `${sessionFinalTranscript}${sessionInterimTranscript}`.trim();
  const textVal = (document.getElementById("text-answer").value || "").trim();
  const baseline = (savedAnswerText || "").trim();
  const unsaved = isRecording || !!live || (textVal && textVal !== baseline);
  if (unsaved && !window.confirm("当前回答尚未提交，跳转将丢弃未提交内容。确定跳转？")) {
    return;
  }

  typewriterGeneration += 1;
  isTyping = false;
  stopAgentSpeech();
  if (isRecording) {
    await stopRecording(false);
  }

  const payload = { type: "goto", question_index: index };
  if (followUpIndex != null) payload.follow_up_index = followUpIndex;
  ws.send(JSON.stringify(payload));
  const label = followUpIndex == null ? `第 ${index + 1} 题` : `第 ${index + 1}.${followUpIndex + 1} 追问`;
  setStatus("interview-status", `正在跳转到${label}...`, "");
}

/** 主动结束面试并生成报告 */
async function finishInterview() {
  if (!ws || ws.readyState !== WebSocket.OPEN) {
    setStatus("interview-status", "连接已断开，无法结束面试", "error");
    return;
  }
  const pending = (questionsStatus || []).filter((s) => !s.answered && !s.skipped).length;
  const msg = pending
    ? `还有 ${pending} 道题未作答或未跳过，确定结束面试并生成报告？`
    : "确定结束面试并生成评分报告？";
  if (!window.confirm(msg)) return;

  typewriterGeneration += 1;
  isTyping = false;
  stopAgentSpeech();
  if (isRecording) {
    await stopRecording(false);
  }
  setStatus("interview-status", "正在结束面试并生成评分报告（约 3-6 分钟）...", "success");
  ws.send(JSON.stringify({ type: "finish" }));
}

/** WebSocket 连接 */
function connectWebSocket() {
  if (ws) ws.close();

  const protocol = location.protocol === "https:" ? "wss:" : "ws:";
  ws = new WebSocket(`${protocol}//${location.host}/ws/interview/${sessionId}`);

  ws.onopen = () => {
    ws.send(JSON.stringify({ type: "start" }));
    if (answerMode === "voice") initSpeechRecognition();
  };

  ws.onmessage = (event) => {
    handleWsMessage(JSON.parse(event.data));
  };

  ws.onerror = () => setStatus("interview-status", "WebSocket 连接失败", "error");
}

/** 处理 WebSocket 消息 */
async function handleWsMessage(data) {
  if (data.event === "error") {
    setStatus("interview-status", data.message, "error");
    setSpeechState("提问失败");
    return;
  }

  if (data.agent_text) {
    stopRecordingTimer();
    isRecording = false;
    resetAnswerText(true);
    currentAgentText = data.agent_text;
    lastAudioBase64 = data.audio_base64 || null;
    document.getElementById("btn-replay").disabled = true;
    document.getElementById("btn-mic").classList.remove("recording");
    document.getElementById("btn-mic").textContent = "🎤 开始回答";

    if (answerMode === "voice") {
      updateAnswerDisplay();
    } else {
      document.getElementById("text-answer").value = "";
    }

    if (data.action !== "follow_up" && data.previous_answer) {
      savedAnswerText = data.previous_answer;
      updateAnswerDisplay();
      document.getElementById("text-answer").value = data.previous_answer;
    } else if (data.previous_skipped) {
      setStatus("interview-status", "该题上次已跳过，可重新作答或再次跳过", "");
    }

    updateQuestionProgress(data);

    setStatus("interview-status", "面试官正在播报题目...", "");
    setSpeechState("正在播报", true);

    await Promise.all([
      typewriterEffect("agent-text", data.agent_text, 28),
      playAgentSpeech(data.agent_text, data.audio_base64),
    ]);
    setSpeechState("等待回答");

    // 浏览器语音兜底也可重播，且不能沿用上一题的音频。
    document.getElementById("btn-replay").disabled = !currentAgentText;

    if (data.tts_fallback) {
      setStatus("interview-status", "已使用浏览器语音播报（服务端 TTS 暂不可用）", "");
    }

    setStatus(
      "interview-status",
      answerMode === "voice"
        ? "请听题完成后点击「开始回答」，说完后点「提交回答」。也可点击题号跳转。"
        : "请在输入框作答，完成后点击「提交回答」。也可点击题号跳转。",
      "success"
    );
    applyAnswerModeUI();
  } else if (data.questions_status || data.question_index !== undefined) {
    updateQuestionProgress(data);
  }

  if (data.event === "complete") {
    setSpeechState("面试完成");
    setStatus("interview-status", "面试完成，正在生成评分报告（约 3-6 分钟）...", "success");
    showReport(data.scoring);
  }

  if (data.action === "follow_up") {
    setStatus("interview-status", `追问：${data.reason || "请补充细节"}`, "");
  }

  if (data.action === "await_next") {
    setStatus(
      "interview-status",
      data.message || "本题已完成。可跳转到其他题目，或点击「完成面试」。",
      "success"
    );
  }
}

/** 初始化语音识别 */
function initSpeechRecognition() {
  if (recordingUseFallback) return;

  const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
  if (!SpeechRecognition) {
    recordingUseFallback = true;
    return;
  }

  if (recognition) return;

  recognition = new SpeechRecognition();
  recognition.lang = "zh-CN";
  recognition.continuous = true;
  recognition.interimResults = true;

  recognition.onresult = (event) => {
    if (!isRecording) return;
    let finalText = "";
    let interimText = "";
    // event.results 是当前识别会话的完整列表，必须整体重建，不能对历史定稿做 +=。
    for (let i = 0; i < event.results.length; i++) {
      const result = event.results[i][0].transcript;
      if (event.results[i].isFinal) {
        finalText += result;
      } else {
        interimText += result;
      }
    }
    sessionFinalTranscript = finalText;
    sessionInterimTranscript = interimText;
    updateAnswerDisplay();
  };

  recognition.onend = () => {
    if (isRecording && !recordingUseFallback) {
      commitSessionTranscript();
      updateAnswerDisplay();
      try {
        recognition.start();
      } catch (_) {
        recordingUseFallback = true;
      }
    }
  };

  recognition.onerror = (event) => {
    if (event.error === "aborted" || event.error === "no-speech") return;
    if (event.error === "network" || event.error === "not-allowed" || event.error === "service-not-allowed") {
      recordingUseFallback = true;
      setStatus(
        "interview-status",
        "实时转写不可用，已切换为录音模式。停止后将自动转写文字。",
        "success"
      );
      return;
    }
    setStatus("interview-status", micErrorMessage(event.error), "error");
  };
}

/** 录音降级：MediaRecorder + 服务端 STT */
async function startRecorderFallback() {
  const stream = await acquireMicStream();
  audioChunks = [];
  mediaRecorder = new MediaRecorder(stream);
  mediaRecorder.ondataavailable = (e) => {
    if (e.data.size > 0) audioChunks.push(e.data);
  };
  mediaRecorder.start(1000);
}

async function stopRecorderFallback() {
  if (!mediaRecorder || mediaRecorder.state === "inactive") return null;

  return new Promise((resolve) => {
    mediaRecorder.onstop = async () => {
      const blob = new Blob(audioChunks, { type: "audio/webm" });
      const form = new FormData();
      form.append("audio", blob, "answer.webm");
      try {
        const res = await fetch("/api/stt", { method: "POST", body: form });
        const data = await res.json();
        resolve(data.text || "");
      } catch (_) {
        resolve("");
      }
    };
    mediaRecorder.stop();
  });
}

/** 停止录音并保留文本 */
async function stopRecording(autoStopped = false) {
  if (!isRecording) return;

  isRecording = false;
  stopRecordingTimer();

  const btn = document.getElementById("btn-mic");
  if (recognition) {
    try { recognition.stop(); } catch (_) { /* ignore */ }
  }

  let extra = `${sessionFinalTranscript}${sessionInterimTranscript}`.trim();
  sessionFinalTranscript = "";
  sessionInterimTranscript = "";

  if (mediaRecorder && mediaRecorder.state === "recording") {
    if (!extra) {
      setStatus("interview-status", "正在转写录音...", "");
    }
    const sttText = await stopRecorderFallback();
    const sttUsable = sttText
      && sttText.indexOf("请安装 faster-whisper") === -1
      && sttText.indexOf("音频已保存") === -1;
    // 实时转写已有内容时不再拼接整段录音 STT，避免全文重复。
    if (!extra && sttUsable) {
      extra = sttText.trim();
    }
  }

  if (extra) {
    savedAnswerText = savedAnswerText ? `${savedAnswerText}${extra}` : extra;
  }
  updateAnswerDisplay();

  btn.classList.remove("recording");
  btn.textContent = "🎤 开始回答";

  const finalText = savedAnswerText.trim();
  if (finalText) {
    document.getElementById("answer-helper").textContent = "文字已保留，请检查内容并提交；点击重答可重新录制。";
    setStatus(
      "interview-status",
      autoStopped
        ? "录音已达上限，内容已保留，确认后点击「提交回答」"
        : "录音已停止，内容已保留，确认后点击「提交回答」",
      "success"
    );
  } else if (!autoStopped) {
    document.getElementById("answer-helper").textContent = "未识别到语音，请重试。";
    setStatus("interview-status", "未识别到语音，请重试或改用文字输入", "error");
  }
}

/** 语音回答控制 */
async function toggleRecording() {
  if (answerMode !== "voice" || isTyping) return;

  const btn = document.getElementById("btn-mic");

  if (isRecording) {
    await stopRecording(false);
    return;
  }

  try {
    await acquireMicStream();
  } catch (err) {
    setStatus("interview-status", `${err.message}`, "error");
    return;
  }

  sessionFinalTranscript = "";
  sessionInterimTranscript = "";
  document.getElementById("user-transcript").classList.remove("hidden");
  document.getElementById("text-answer").classList.add("hidden");
  updateAnswerDisplay();

  isRecording = true;

  try {
    await startRecorderFallback();
  } catch (err) {
    isRecording = false;
    setStatus("interview-status", `无法启动录音: ${err.message}`, "error");
    return;
  }

  if (recognition && !recordingUseFallback) {
    try {
      recognition.start();
    } catch (_) {
      recordingUseFallback = true;
    }
  }

  if (recordingUseFallback) {
    setStatus("interview-status", "录音中（停止后自动转写，最长 2 分钟）...", "success");
  } else {
    setStatus("interview-status", "正在聆听，请连续作答（最长 2 分钟）...", "success");
  }

  startRecordingTimer();
  document.getElementById("answer-helper").textContent = recordingUseFallback
    ? "正在录音；停止后会将语音转写成文字，最长 2 分钟。"
    : "正在录音并转写；已识别内容会持续保留，最长 2 分钟。";
  btn.classList.add("recording");
  btn.textContent = "⏹ 停止回答";
}

/** 提交回答 */
async function submitAnswer(skip = false, retry = false) {
  if (isTyping) {
    setStatus("interview-status", "请等待面试官播报完成", "error");
    return;
  }

  if (isRecording) {
    await stopRecording(false);
  }

  let text = "";
  if (answerMode === "text") {
    text = document.getElementById("text-answer").value.trim();
  } else {
    text = savedAnswerText.trim()
      || document.getElementById("text-answer").value.trim()
      || document.getElementById("user-transcript").textContent.trim();
  }

  if (!skip && !retry && !text) {
    setStatus("interview-status", "请先输入或录下你的回答", "error");
    return;
  }

  if (retry) {
    resetAnswerText(true);
  }

  if (recognition) {
    try { recognition.stop(); } catch (_) { /* ignore */ }
  }
  isRecording = false;
  stopRecordingTimer();
  document.getElementById("btn-mic").classList.remove("recording");
  document.getElementById("btn-mic").textContent = "🎤 开始回答";

  if (ws && ws.readyState === WebSocket.OPEN) {
    ws.send(JSON.stringify({
      type: skip ? "skip" : retry ? "retry" : "answer",
      text,
    }));
    setStatus(
      "interview-status",
      retry ? "正在重答..." : skip ? "已跳过" : "已提交，请等待下一题...",
      "success"
    );
  }
}

/**
 * 转义 HTML 特殊字符。
 * @param {string} text
 * @returns {string}
 */
function escapeHtml(text) {
  return String(text ?? "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

/**
 * 将评估长文本转为带段落/列表的 HTML。
 * @param {string} text
 * @returns {string}
 */
function formatReportRichText(text) {
  const raw = String(text || "").trim();
  if (!raw) return "<p>—</p>";
  const withBold = escapeHtml(raw).replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>");
  return withBold.split(/\n{2,}/).map((block) => {
    const lines = block.split("\n").map((line) => line.trim()).filter(Boolean);
    if (!lines.length) return "";
    const isList = lines.every((line) => /^[-•]\s/.test(line) || /^\d+[.、)]\s/.test(line));
    if (isList) {
      const items = lines
        .map((line) => `<li>${line.replace(/^[-•]\s/, "").replace(/^\d+[.、)]\s/, "")}</li>`)
        .join("");
      return `<ul>${items}</ul>`;
    }
    return `<p>${lines.join("<br>")}</p>`;
  }).join("");
}

/**
 * 将高分框架拆成 STAR 步骤卡片；无法拆分时退回富文本。
 * @param {string} text
 * @returns {string}
 */
function formatFramework(text) {
  const raw = String(text || "").trim();
  if (!raw) return "<p>—</p>";
  const re = /(Situation|Task|Action|Result|情境|任务|行动|动作|结果)\s*[:：]/gi;
  const matches = [];
  let match = re.exec(raw);
  while (match) {
    matches.push({ label: match[1], index: match.index, end: match.index + match[0].length });
    match = re.exec(raw);
  }
  if (matches.length < 3) {
    return formatReportRichText(raw);
  }
  const intro = raw.slice(0, matches[0].index).trim();
  const stepsHtml = matches.map((item, idx) => {
    const end = idx + 1 < matches.length ? matches[idx + 1].index : raw.length;
    const body = raw.slice(item.end, end).trim();
    return `<li><span class="star-label">${escapeHtml(item.label)}</span><span class="star-body">${escapeHtml(body)}</span></li>`;
  }).join("");
  const introHtml = intro ? `<p class="framework-intro">${escapeHtml(intro)}</p>` : "";
  return `${introHtml}<ol class="star-steps">${stepsHtml}</ol>`;
}

/**
 * 根据分数返回维度样式等级。
 * @param {number} score
 * @returns {string}
 */
function dimLevelClass(score) {
  if (score >= 4) return "dim-high";
  if (score >= 3) return "dim-mid";
  return "dim-low";
}

/** 展示报告 */
async function showReport(scoring) {
  showStep("step-report");
  document.getElementById("report-summary").textContent = "";
  document.getElementById("scores-list").textContent = "";
  document.getElementById("report-summary").setAttribute("aria-busy", "true");
  document.getElementById("report-downloads").hidden = true;
  document.getElementById("btn-report-retry").classList.add("hidden");
  setStatus("report-status", "正在读取评估报告…", "");
  let session = null;
  try {
    if (!sessionId) throw new Error("请先选择一场面试，再查看报告。");
    const sessionRes = await fetch(`/api/sessions/${sessionId}`);
    session = await readApiResponse(sessionRes, "面试记录加载失败");
    if (!scoring) {
      if (session.scores?.length) {
        scoring = { summary: session.summary };
      } else {
        setStatus("report-status", "正在生成逐题评分和高分作答框架，请稍候…", "");
        const res = await fetch(`/api/sessions/${sessionId}/score`, { method: "POST" });
        scoring = await readApiResponse(res, "报告生成失败");
        const updatedSessionRes = await fetch(`/api/sessions/${sessionId}`);
        session = await readApiResponse(updatedSessionRes, "报告加载失败");
      }
    }
  } catch (err) {
    setStatus("report-status", requestErrorMessage(err, "报告加载失败"), "error");
    document.getElementById("btn-report-retry").classList.remove("hidden");
    return;
  } finally {
    document.getElementById("report-summary").removeAttribute("aria-busy");
  }
  currentSession = session;
  if (!session) session = {};
  const summary = scoring.summary || session.summary || {};
  const jd = session.jd_profile || {};
  const resume = session.resume_profile || {};
  const match = session.match_analysis || {};
  const avg = Number(summary.average_score || 0);
  const matchScore = Number(match.overall_match_score || 0);
  const strengths = summary.strengths || [];
  const risks = summary.risks || [];
  const questions = session.questions || [];

  const chips = [
    ...strengths.map((item) => `<span class="chip chip-good">${escapeHtml(item)}</span>`),
    ...risks.map((item) => `<span class="chip chip-warn">${escapeHtml(item)}</span>`),
  ].join("");

  const matchPoints = (match.match_points || []).map((item) => `<li>${escapeHtml(item)}</li>`).join("");
  const riskPoints = (match.risk_points || []).map((item) => `<li>${escapeHtml(item)}</li>`).join("");

  document.getElementById("report-summary").innerHTML = `
    <div class="report-hero">
      <div class="report-score-ring" style="--pct:${Math.max(0, Math.min(100, (avg / 5) * 100))}">
        <div class="report-score-inner">
          <span class="report-score-num">${avg.toFixed(1)}</span>
          <span class="report-score-max">/ 5.0</span>
        </div>
      </div>
      <div class="report-hero-meta">
        <p class="report-kicker">综合评估</p>
        <h3>${escapeHtml(resume.name || "候选人")} · ${escapeHtml(jd.title || "目标岗位")}</h3>
        <p class="report-reco">${escapeHtml(summary.recommendation || "待定")}</p>
        <div class="report-match-row">
          <span>JD 匹配度</span>
          <div class="match-track"><div class="match-fill" style="width:${Math.max(0, Math.min(100, matchScore))}%"></div></div>
          <strong>${matchScore.toFixed(0)} / 100</strong>
        </div>
      </div>
    </div>
    ${chips ? `<div class="chip-row">${chips}</div>` : ""}
    ${summary.next_steps ? `<div class="report-next">${formatReportRichText(summary.next_steps)}</div>` : ""}
    ${(matchPoints || riskPoints) ? `
      <div class="match-grid">
        <div class="match-col match-good"><h4>匹配点</h4><ul>${matchPoints || "<li>暂无</li>"}</ul></div>
        <div class="match-col match-risk"><h4>风险点</h4><ul>${riskPoints || "<li>暂无</li>"}</ul></div>
      </div>
    ` : ""}
  `;

  const scoresList = document.getElementById("scores-list");
  scoresList.innerHTML = "";
  (session.scores || []).forEach((s, i) => {
    const qIndex = questions.findIndex((q) => q.id === s.question_id);
    const question = qIndex >= 0 ? questions[qIndex] : null;
    const displayIndex = qIndex >= 0 ? qIndex + 1 : i + 1;
    const typeLabel = QUESTION_TYPE_LABELS[question?.type] || "";
    const qtext = question?.text || s.question_text || "";
    const dims = (s.dimensions || []).map((d) => {
      const score = Number(d.score || 0);
      const pct = Math.max(0, Math.min(100, (score / 5) * 100));
      const comment = d.comment ? `<p class="dim-comment">${escapeHtml(d.comment)}</p>` : "";
      return `
        <div class="dim-item ${dimLevelClass(score)}">
          <div class="dim-head">
            <span class="dim-name">${escapeHtml(d.dimension)}</span>
            <span class="dim-score">${score}</span>
          </div>
          <div class="dim-bar-track"><div class="dim-bar" style="width:${pct}%"></div></div>
          ${comment}
        </div>
      `;
    }).join("");
    const quotes = (s.evidence_quotes || [])
      .map((quote) => `<blockquote>${escapeHtml(quote)}</blockquote>`)
      .join("");
    const inconsistency = s.resume_inconsistency
      ? `<div class="report-alert">简历一致性提醒：${escapeHtml(s.resume_inconsistency)}</div>`
      : "";
    const div = document.createElement("details");
    div.className = "score-card";
    div.innerHTML = `
      <summary class="score-card-head">
        <div>
          <p class="score-kicker">第 ${displayIndex} 题${typeLabel ? ` · ${escapeHtml(typeLabel)}` : ""}</p>
          ${qtext ? `<p class="score-question">${escapeHtml(qtext)}</p>` : ""}
        </div>
        <h4>${Number(s.total_score || 0).toFixed(1)} <span>/ 5.0</span></h4>
      </summary>
      <div class="score-dims">${dims}</div>
      <div class="report-block">
        <h5>反馈</h5>
        <div class="report-prose">${formatReportRichText(s.feedback)}</div>
      </div>
      ${quotes ? `<div class="report-block"><h5>作答证据</h5>${quotes}</div>` : ""}
      <div class="report-block framework-block">
        <h5>高分作答框架</h5>
        <div class="report-prose">${formatFramework(s.high_score_framework)}</div>
      </div>
      ${inconsistency}
    `;
    scoresList.appendChild(div);
  });

  document.getElementById("btn-download-md").href = `/api/sessions/${sessionId}/report?format=md`;
  document.getElementById("btn-download-pdf").href = `/api/sessions/${sessionId}/report?format=pdf`;
  document.getElementById("btn-download-qa-md").href = `/api/sessions/${sessionId}/transcript?format=md`;
  document.getElementById("btn-download-qa-pdf").href = `/api/sessions/${sessionId}/transcript?format=pdf`;
  document.getElementById("report-downloads").hidden = false;
  setStatus("report-status", "", "");
}

/** 初始化 */
document.addEventListener("DOMContentLoaded", async () => {
  document.getElementById("btn-create").addEventListener("click", createSession);
  document.getElementById("btn-start-preparation").addEventListener("click", () => {
    document.querySelector(".upload-card").scrollIntoView({
      behavior: window.matchMedia("(prefers-reduced-motion: reduce)").matches ? "instant" : "smooth",
      block: "start",
    });
  });
  document.getElementById("btn-resume").addEventListener("click", resumeSession);
  document.getElementById("btn-refresh-sessions").addEventListener("click", async (event) => {
    const button = event.currentTarget;
    button.disabled = true;
    try {
      await loadSessions();
      setStatus("upload-status", "历史会话已刷新。", "success");
    } catch (err) {
      setStatus("upload-status", requestErrorMessage(err, "历史会话刷新失败"), "error");
    } finally {
      button.disabled = false;
    }
  });
  document.getElementById("btn-delete-session").addEventListener("click", deleteSession);
  document.getElementById("session-check-all").addEventListener("change", toggleSelectAllSessions);
  document.getElementById("btn-to-mode").addEventListener("click", goToModeStep);
  document.getElementById("btn-view-report").addEventListener("click", () => showReport(null));
  document.getElementById("btn-preview-back").addEventListener("click", () => showStep("step-upload"));
  document.getElementById("btn-mode-back").addEventListener("click", () => showStep("step-preview"));
  document.getElementById("btn-report-back").addEventListener("click", () => {
    if (currentSession) {
      renderPreview(currentSession);
      showStep("step-preview");
    } else {
      showStep("step-upload");
    }
  });
  document.getElementById("btn-report-retry").addEventListener("click", () => showReport(null));
  document.getElementById("btn-mode-voice").addEventListener("click", () => selectAnswerMode("voice"));
  document.getElementById("btn-mode-text").addEventListener("click", () => selectAnswerMode("text"));
  document.getElementById("btn-begin-interview").addEventListener("click", beginInterview);
  document.getElementById("btn-mic").addEventListener("click", toggleRecording);
  document.getElementById("btn-submit").addEventListener("click", () => submitAnswer(false));
  document.getElementById("btn-skip").addEventListener("click", () => submitAnswer(true));
  document.getElementById("btn-retry").addEventListener("click", () => submitAnswer(false, true));
  document.getElementById("btn-prev-q").addEventListener("click", () => jumpRelative(-1));
  document.getElementById("btn-next-q").addEventListener("click", () => jumpRelative(1));
  document.getElementById("btn-finish-interview").addEventListener("click", finishInterview);
  document.getElementById("btn-replay").addEventListener("click", () => {
    if (lastAudioBase64) {
      playAgentSpeech(currentAgentText, lastAudioBase64);
    } else if (currentAgentText) {
      speakText(currentAgentText);
    }
  });
  document.getElementById("btn-restart").addEventListener("click", () => {
    sessionId = null;
    answerMode = null;
    showStep("step-upload");
  });

  // 先绑定按钮，再并行加载资料；某个接口失败时仍能使用其余功能。
  const initialization = await Promise.allSettled([
    loadTemplates(),
    loadSessions(),
    fetch("/api/config").then(res => readApiResponse(res, "配置读取失败")).then(config => {
      maxRecordSeconds = config.max_record_seconds || 120;
    }),
  ]);
  if (initialization[1].status === "rejected") {
    document.getElementById("session-list").innerHTML = '<p class="session-empty">历史会话暂时无法加载，请点击上方「刷新」。</p>';
  }
  if (initialization[0].status === "rejected" || initialization[1].status === "rejected") {
    setStatus("upload-status", "部分资料暂时无法加载，请确认服务连接后重试。", "error");
  }
});
