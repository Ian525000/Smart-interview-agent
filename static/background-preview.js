const stage = document.getElementById("design-stage");
const directionDescription = document.getElementById("direction-description");
const previewNotice = document.querySelector(".preview-notice");
const descriptions = {
  workbench: "推荐方向：以用户旅程、产品原型和数据洞察构成真实的背景图，突出产品岗位特色。",
  office: "真实办公：用现代面试空间与窗外城市营造临场感，蓝调与暖光让界面更沉稳。",
  dialogue: "智能对话：以声音波形和透明结构表达 AI 对话与思考，深蓝视觉更有科技辨识度。"
};

document.querySelectorAll("[data-theme-choice]").forEach(button => {
  button.addEventListener("click", () => {
    const theme = button.dataset.themeChoice;
    stage.dataset.theme = theme;
    document.querySelectorAll("[data-theme-choice]").forEach(item => {
      item.setAttribute("aria-pressed", String(item === button));
    });
    directionDescription.textContent = descriptions[theme];
  });
});

document.querySelectorAll("[data-view-choice]").forEach(button => {
  button.addEventListener("click", () => {
    const view = button.dataset.viewChoice;
    stage.dataset.view = view;
    stage.querySelector(".prepare-view").hidden = view !== "prepare";
    stage.querySelector(".interview-view").hidden = view !== "interview";
    document.querySelectorAll("[data-view-choice]").forEach(item => {
      item.setAttribute("aria-pressed", String(item === button));
    });
  });
});

const deviceButton = document.querySelector(".device-toggle");
deviceButton.addEventListener("click", () => {
  const phone = stage.classList.toggle("phone-preview");
  deviceButton.setAttribute("aria-pressed", String(phone));
  deviceButton.textContent = phone ? "返回桌面效果" : "查看手机效果";
});

stage.querySelector(".hero-action").addEventListener("click", () => {
  stage.querySelector(".materials-panel").scrollIntoView({ behavior: "smooth", block: "center" });
});

stage.querySelectorAll(".preview-action").forEach(button => {
  button.addEventListener("click", () => {
    previewNotice.textContent = "这是视觉方案预览；正式功能仍在主网页 http://localhost:8001/ 中。";
  });
});

document.getElementById("preview-stop").addEventListener("click", event => {
  const button = event.currentTarget;
  const stopped = button.dataset.stopped !== "true";
  button.dataset.stopped = String(stopped);
  button.textContent = stopped ? "● 继续录音" : "■ 停止录音";
  document.querySelector(".recording-badge").innerHTML = stopped
    ? "已停止 · 内容已保留"
    : '<i></i>录音中 <b>01:26</b>';
  document.querySelector(".answer-footer span").textContent = stopped
    ? "文字已保留，确认后可以提交"
    : "正在持续转写，之前的内容会保留";
  document.querySelector(".typing-cursor").hidden = stopped;
});
