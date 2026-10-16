# 大厂互联网产品岗位智能面试 Agent

面向互联网产品岗位的中文 AI 模拟面试工具。根据岗位 JD 和个人简历生成 10 道定制问题，通过语音或文字完成面试、展开追问，最后获得逐题评分、反馈、高分作答框架和可下载报告。

采用 FastAPI + 原生 HTML/CSS/JavaScript，无需安装 Node.js 或构建前端即可使用。网页采用「真实办公 · 蓝调」主题，支持桌面和窄屏布局。

> 本项目用于个人面试练习，不隶属于任何招聘企业。AI 评分仅供参考，不代表真实录用结论。项目不附带可用的 API 密钥，需自行配置模型服务；调用费用由对应服务商收取。

## 目录

- [功能与使用流程](#功能与使用流程)
- [运行前准备](#运行前准备)
- [Windows 从零开始](#windows-从零开始)
- [macOS / Linux 安装](#macos--linux-安装)
- [语音功能与可选依赖](#语音功能与可选依赖)
- [配置项说明](#配置项说明)
- [数据保存与隐私](#数据保存与隐私)
- [常见问题](#常见问题)
- [更新与开发](#更新与开发)

## 功能与使用流程

| 步骤 | 页面 | 如何操作 |
| --- | --- | --- |
| 1 | 上传材料 / 历史会话 | 上传岗位 JD 和简历，或粘贴两份材料的文本；也可恢复历史面试。 |
| 2 | 预览题目 | 等待 AI 生成 10 道题，查看岗位匹配摘要，按需编辑问题。 |
| 3 | 选择回答方式 | 在独立步骤选择本场面试统一使用「语音回答」或「文字回答」，再确认开始。 |
| 4 | 正式面试 | 查看题号、进度和追问；问题逐字显示并尝试语音播报，提交回答后继续。 |
| 5 | 评估报告 | 查看综合评分、逐题维度评分、反馈和高分作答框架，下载评估报告及问答实录。 |

### 第一次练习建议

1. 先使用 `samples/jd_sample.txt` 和 `samples/resume_sample.txt` 跑通流程。这些是虚构示例，不是真实候选人的材料。
2. 首次建议选择「文字回答」，确认模型调用正常后再测试麦克风和语音。
3. 生成题目和评分需要模型调用；请等待状态提示，不要连续重复提交。
4. 面试中会根据回答对部分题目展开追问；可使用重答、跳过和题号导航。
5. 语音模式中，点击「开始回答」才会开始录音；问题播报不等于已经开始录音。停止后保留已识别的回答，确认内容后再「提交回答」。默认每次录音最长 2 分钟，页面显示剩余时间，到时停止录音，不自动提交。
6. 完成后等待评估生成。评估报告与问答实录是两份独立文档，均支持 Markdown / PDF 下载。

历史会话保存在当前电脑，可刷新列表、恢复进度或查看已完成报告。删除操作请谨慎，重要报告请先下载备份。

## 运行前准备

- Python **3.10 或以上**；本项目曾在 Windows + Python 3.12 环境检查。
- 可连接互联网，能够安装 Python 依赖并访问所选模型服务。
- 支持 **OpenAI 兼容 Chat Completions API** 的服务地址、模型名称和 API Key。三者必须属于同一服务商/接入点。
- 语音回答需要麦克风和浏览器授权；建议使用 Chrome 或 Edge 的较新版本。
- Git 是可选的：不熟悉 Git 的用户可直接下载 ZIP。

项目是本地运行的 Web 应用，不是已托管的 SaaS。默认仅监听本机 `127.0.0.1`，访问地址为 `http://localhost:8001/`。

## Windows 从零开始

### 1. 下载完整项目

方式 A：打开 [GitHub 仓库](https://github.com/Ian525000/Smart-interview-agent)，点击 **Code → Download ZIP**，解压后进入项目目录。不要直接在 ZIP 预览窗口里运行。

方式 B：安装 Git 后，在 PowerShell 中运行：

```powershell
git clone https://github.com/Ian525000/Smart-interview-agent.git
cd Smart-interview-agent
```

后续命令都在包含 `main.py`、`requirements-core.txt` 和 `static` 文件夹的项目根目录执行。下载后的文件夹可能叫 `Smart-interview-agent-main`，不影响运行。

### 2. 创建虚拟环境并安装基础依赖

在项目文件夹空白处右键打开终端，运行：

```powershell
py -3 --version
py -3 -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -r requirements-core.txt
```

若系统没有 `py` 命令，但 `python --version` 正常且版本不低于 3.10，可将前两条中的 `py -3` 换为 `python`。如果两者都没有，请先安装 Python 并重新打开终端。

这里直接使用虚拟环境中的 Python，不需要执行 `Activate.ps1`，也不需要修改 PowerShell 执行策略。

基础依赖支持网页、文字面试、浏览器支持的实时语音转写、TTS 以及 ReportLab PDF 导出。服务端语音转写需额外安装，见[语音功能与可选依赖](#语音功能与可选依赖)。

### 3. 配置自己的模型接口

仅在第一次安装、尚无 `.env` 时复制模板：

```powershell
Copy-Item .env.example .env
notepad .env
```

至少填写以下三项；此处仅为接入格式示例，不含可用密钥：

```dotenv
LLM_API_KEY=your_api_key_here
LLM_MODEL_ID=qwen-max
LLM_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
SERVER_PORT=8001
```

- `LLM_API_KEY`：替换为自己在模型服务商控制台获取的密钥，不要保留占位符。
- `LLM_MODEL_ID`：改为该密钥有权限调用的模型名。
- `LLM_BASE_URL`：填写对应服务的 OpenAI 兼容基础地址，不要在末尾另加 `/chat/completions`。
- 示例不保证适用于所有账号、地区或套餐，以服务商为你的账号提供的接入信息为准。

保存后再启动服务。`.env.example` 是可公开的配置说明，`.env` 是只留在本机的真实配置。**不要上传、截图公开或发送 `.env`。** 更新项目时也不要用模板覆盖已有 `.env`。

### 4. 启动网页

安装和配置完成后，双击项目中的 **`启动网页.bat`**。启动器会检查端口、在后台启动本项目并打开浏览器。

也可以在终端运行：

```powershell
.\.venv\Scripts\python.exe start_local.py
```

随后访问：**[http://localhost:8001/](http://localhost:8001/)**。

- 重复运行启动器会复用已经运行的本项目，不会结束其他项目的进程。
- 关闭启动窗口不影响后台服务；电脑重启后需再次启动。
- 日志位于 `data/logs/`。仅启动、不自动打开浏览器可加 `--no-browser`。

开发或排查错误时，推荐改用前台方式查看完整日志（不要与后台方式同时启动同一端口）：

```powershell
.\.venv\Scripts\python.exe main.py
```

前台方式按 `Ctrl+C` 停止，关闭终端也会停止服务。修改 `.env` 或 Python 代码后需要重启服务；后台服务可在任务管理器中根据 PID 和命令行确认对应的 `uvicorn main:app` 进程后结束，勿批量结束所有 Python 进程。仅修改网页样式时通常强制刷新即可。

### 5. 检查是否启动成功

打开 [健康检查](http://localhost:8001/api/health)，应看到：

```json
{"status":"ok","service":"interview-agent"}
```

这只说明网页服务就绪，不代表模型密钥有效。请再使用示例材料生成题目，验证模型调用。配置占位密钥可能让网页打开，但无法正常生成问题或评分。

## macOS / Linux 安装

下载/克隆项目后，在根目录执行：

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements-core.txt
cp .env.example .env
# 用编辑器填写 .env 中的三个模型配置项
python main.py
```

访问 `http://localhost:8001/`，按 `Ctrl+C` 停止。再次使用时进入项目目录、激活虚拟环境并启动即可；不要重复复制 `.env`。Windows 的 `.bat` 启动器不适用于此环境。

## 语音功能与可选依赖

### 语音回答：两条转写路径

1. **浏览器实时转写**：浏览器支持且识别服务可达时，边说话边显示文本，并累计保留前面的句子。部分浏览器的识别依赖在线服务，仅授权麦克风不代表识别服务可用。
2. **停止后服务端转写**：浏览器无法实时识别时，可对录音进行服务端转写；需额外安装 `faster-whisper`。

Windows 安装服务端转写依赖：

```powershell
.\.venv\Scripts\python.exe -m pip install "faster-whisper>=1.0.0"
```

macOS / Linux 在已激活的虚拟环境中执行 `python -m pip install "faster-whisper>=1.0.0"`。

首次服务端转写需要下载 `WHISPER_MODEL` 指定的模型，网络不可达会导致失败；模型在本机 CPU 上运行，速度取决于电脑配置。默认是 `base`，可按需改为 `tiny` 减轻负载，精度可能降低。

录音权限、设备输入、浏览器识别服务和服务端模型是不同环节。先确认系统麦克风有输入，再确认网页录音状态；若只能录音但无文字，请检查识别服务或服务端日志。转写失败可重答，或返回准备流程改用文字方式。

### 面试官语音播报

默认通过在线 `edge-tts` 合成中文语音；失败时尝试浏览器自带语音合成。系统语音包、网络和自动播放策略都会影响效果。必要时点击「重播语音」；即使语音不可用，仍可阅读问题作答。

### PDF 导出

基础安装包含 ReportLab，无需额外安装 WeasyPrint 也会尝试导出 PDF。若需要 WeasyPrint 排版，可另外安装并按其平台要求配置系统依赖：

```powershell
.\.venv\Scripts\python.exe -m pip install "weasyprint>=60.0"
```

也可以一次安装所有 Python 依赖：

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

`requirements.txt` 包含基础依赖以及上述两项扩展，安装耗时和环境要求较高。PDF 中文显示异常时请检查系统中文字体；Markdown 报告仍可用于阅读和备份。

## 配置项说明

在项目根目录的 `.env` 中修改；修改后重启后端。

| 配置项 | 默认 / 示例 | 说明 |
| --- | --- | --- |
| `LLM_API_KEY` | 必填，自行申请 | 模型服务密钥，只保存在本地。 |
| `LLM_MODEL_ID` | 示例 `qwen-max` | 该账号可用的模型 ID。 |
| `LLM_BASE_URL` | 示例见上文 | OpenAI 兼容接口基础地址。 |
| `LLM_TIMEOUT` | `120` | 单次模型请求超时，单位秒，不是整场面试时长。 |
| `SERVER_PORT` | `8001` | 本地端口；占用时可改为空闲端口，如 `8002`。 |
| `TTS_VOICE` | `zh-CN-XiaoxiaoNeural` | 在线面试官语音角色。 |
| `WHISPER_MODEL` | `base` | 服务端转写模型，需额外依赖和模型下载。 |
| `MAX_RECORD_SECONDS` | `120` | 每次录音最长时长，单位秒；页面据此倒计时。 |
| `MAX_FOLLOW_UPS` | `3` | 面试追问上限配置。 |
| `FOLLOW_UP_QUESTION_COUNT` | `3` | 预选可展开追问的题目数。 |
| `REFLECTION_ROUNDS` | `2` | 评分反思校准轮数，增加会带来更多模型调用。 |

岗位模板位于 `templates/job_templates.json`。Mock 模式使用模板题目，但 JD 解析、追问和评分等环节仍可能调用模型，**不是完全离线或免密钥模式**。

## 数据保存与隐私

- 会话数据库：`data/interview.db`。
- 录音及语音合成缓存：`data/audio/`。
- 评估报告和问答实录：`data/reports/`。
- 后台启动日志：`data/logs/`。
- 其他运行数据也位于 `data/`；首次运行自动创建，无需从其他电脑复制。

`.gitignore` 排除 `.env`、运行数据、虚拟环境和缓存。备份时请保护 `.env` 和 `data/`；不要把真实简历、录音或报告提交到公开仓库。删除历史会话不应视为彻底擦除磁盘上的全部关联文件，分享电脑或清理数据前应另行检查备份、报告和音频。

**本地网页不等于全部离线**：JD、简历和回答的相关内容会发送给你配置的模型服务；在线语音合成会发送题目文本；浏览器语音识别也可能由浏览器服务商处理。服务端 Whisper 在模型下载后使用本机转写。上传他人材料前应取得授权，并按需去除姓名、电话、邮箱等信息。

当前版本没有多用户登录、权限隔离或生产环境防护，不要直接暴露到公网。手机布局可在电脑浏览器响应式视图预览；手机访问自身的 `localhost` 不会访问到你的电脑。跨设备和公网部署需要额外的网络、安全与 HTTPS 配置，不在本地快速启动范围内。

## 常见问题

### 网页打不开 / 重新开机后无法访问

先运行 `启动网页.bat`，等待服务就绪。检查地址与 `.env` 的 `SERVER_PORT` 是否一致；查看 `data/logs/` 最新错误日志。前台启动可直接看到缺少依赖或配置错误。

### 8001 端口被占用，或打开了另一个项目

不要结束不属于本项目的服务。将 `.env` 中 `SERVER_PORT` 改为另一个空闲端口（如 `8002`），重启本项目，然后访问 `http://localhost:8002/`。启动器遇到非本项目占用时会报错，不会自动杀掉进程。

### 网页能打开，但生成题目/评分失败

检查密钥是否仍为占位符、模型是否有调用权限、服务地址是否匹配、额度及网络是否正常。`401/403` 通常与鉴权或权限有关；模型不存在、限流和超时请结合服务商响应及后端日志判断。不要把密钥贴到 Issue。

### 生成或评分很慢

出题包含解析和规划，评分还会逐题评估并校准，需要多次请求，可能耗时数分钟。观察状态和日志；模型超时、网络失败时再重试。增大 `LLM_TIMEOUT` 不能解决错误密钥或网络不可达。

### 已授权麦克风，但没有文字 / 没有声音

确认使用 `localhost`，麦克风没有静音且设备正确；检查系统和浏览器是否都允许录音。实时识别失败与设备权限并非同一问题，见[语音功能与可选依赖](#语音功能与可选依赖)。面试官无声时检查页面音量、自动播放限制和网络，再点击重播。

### 上传文件后无法解析

建议使用可选中文字的 PDF、`.docx`、UTF-8 编码的 `.txt` / `.md`。扫描 PDF 或图片需要先做 OCR，本项目不内置 OCR；老式 `.doc` 请先转换为 `.docx`，不要只改扩展名。也可直接粘贴两份材料文本。建议两份均上传或两份均粘贴，不要一份文件加一份文本混用。

### 界面仍然是旧版 / 背景没有显示

确认下载的是完整项目且 `static/assets/backgrounds/` 存在，在浏览器按 `Ctrl+F5` 强制刷新。正式入口是 `/`；`/static/design-gallery.html` 仅为视觉方案对比，不是面试入口。

## 更新与开发

### 更新本地版本

Git 克隆用户先备份 `.env` 和 `data/`，确认自己修改的代码已另行保存，再运行：

```bash
git pull --ff-only
```

按前文使用虚拟环境重新安装 `requirements-core.txt`，如用到扩展则更新 `requirements.txt`，然后重启服务。若 Git 提示本地改动或分支分叉，请先处理差异，不要用强制重置覆盖个人文件。

ZIP 用户建议解压到新目录，重新创建虚拟环境、安装依赖，谨慎迁移自己的 `.env` 和需要保留的 `data/`。不要复制旧虚拟环境，也不要将旧代码整包覆盖到新版。

### CLI 文字模式

在已激活虚拟环境或使用其 Python 路径的终端中执行：

```bash
python cli.py --jd samples/jd_sample.txt --resume samples/resume_sample.txt
python cli.py --jd samples/jd_sample.txt --resume samples/resume_sample.txt --mock --template bytedance_product_mock
```

### 检查与测试

前端流程回归测试需要 Node.js（普通使用网页不需要）：

```bash
node --test tests/frontend-flow.test.cjs
```

测试使用替身，不调用真实模型或麦克风；通过不代表你的 API Key、真实录音设备或外部语音服务已验证。接口文档可在服务启动后访问 `/docs`，健康检查为 `/api/health`。

### 项目结构

```text
Smart-interview-agent/
├── main.py                 # FastAPI 网页/API/WebSocket 入口
├── cli.py                  # 命令行文字面试
├── start_local.py           # 独立后台启动与端口检查
├── 启动网页.bat             # Windows 一键启动
├── config.py / llm_client.py
├── requirements-core.txt   # 基础运行依赖
├── requirements.txt        # 基础依赖 + 服务端转写 / WeasyPrint
├── .env.example            # 不含真实密钥的配置模板
├── agents/                 # 解析、出题、面试、评分、报告
├── services/               # 流程编排
├── models/ / storage/      # 数据模型与 SQLite 持久化
├── parsers/ / voice/       # 文档解析和语音处理
├── prompts/ / templates/   # 提示词与岗位题目模板
├── static/                 # HTML、CSS、JavaScript 和本地背景图片
├── samples/                # 虚构示例 JD / 简历
├── tests/                  # 前端流程回归测试
└── data/                   # 运行时自动生成，不纳入 Git
```

背景图片位于 `static/assets/backgrounds/`，办公蓝调样式位于 `static/office-theme.css`。UI 调整无需前端打包步骤。

采用 [MIT License](LICENSE)。贡献方式见 [CONTRIBUTING.md](CONTRIBUTING.md)，安全和密钥处理见 [SECURITY.md](SECURITY.md)。反馈问题时请说明系统、Python 版本、操作步骤和脱敏后的日志，勿附真实密钥或未经授权的个人材料。
