# 贡献指南

感谢你考虑为智能面试 Agent 做贡献。

## 开始之前

1. Fork 本仓库并克隆到本地。
2. 使用 Python 3.10+ 创建虚拟环境并安装 `requirements-core.txt`；需要服务端转写与 WeasyPrint 时安装 `requirements.txt`。
3. 复制 `.env.example` 为 `.env`，填入**你自己的** `LLM_API_KEY`。
4. **不要**在代码、Issue、PR 或截图中粘贴真实密钥。

## 开发约定

- 源码注释使用 JSDoc 风格（`@param` / `@returns`）。
- 新增配置项通过环境变量读取，并同步更新 `.env.example`（只放占位符，不放真实值）。
- 不要提交 `data/` 下的运行时文件、本地报告或上传文档。
- 提交前确认 `git status` 中没有 `.env`。
- 修改网页流程后运行 `node --test tests/frontend-flow.test.cjs`（需 Node.js，测试不调用真实模型或麦克风）。
- 按 README 使用虚构示例检查流程，不要将真实简历或录音作为测试文件上传。

## Pull Request

1. 基于最新 `main` 开分支，分支名建议：`feat/...`、`fix/...`、`docs/...`。
2. 说明改了什么、为什么改，以及如何验证。
3. 若改动了用户可见行为，请在描述中写明测试步骤。

## Issue

提交 Bug 时请尽量包含：操作系统、Python 版本、复现步骤、期望行为、实际行为。请打码密钥、简历原文等敏感信息。
