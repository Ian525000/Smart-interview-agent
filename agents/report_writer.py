"""面试报告生成。"""

import re
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Tuple

from config import REPORTS_DIR
from models.schemas import InterviewSession, QuestionScore
from agents.interviewer import SKIP_PLACEHOLDER


class ReportWriter:
    """生成 Markdown 与 PDF 面试报告。"""

    TYPE_LABELS = {
        "intro": "自我介绍",
        "project": "项目深挖",
        "case": "产品 Case",
        "behavior": "行为面试",
        "open": "开放题",
        "reverse": "反问环节",
    }

    def write_markdown(self, session: InterviewSession) -> str:
        """
        生成评估报告 Markdown（不含完整问答实录）。

        @param session - 面试会话
        @returns 报告文件路径
        """
        content = self._build_eval_markdown(session)
        filename = f"report_{session.session_id}_{datetime.now():%Y%m%d_%H%M%S}.md"
        path = REPORTS_DIR / filename
        path.write_text(content, encoding="utf-8")
        session.report_path = str(path)
        return str(path)

    def write_qa_markdown(self, session: InterviewSession) -> str:
        """
        生成候选人问答实录 Markdown。

        @param session - 面试会话
        @returns 问答文件路径
        """
        content = self._build_qa_markdown(session)
        filename = f"qa_{session.session_id}_{datetime.now():%Y%m%d_%H%M%S}.md"
        path = REPORTS_DIR / filename
        path.write_text(content, encoding="utf-8")
        session.metadata["qa_path"] = str(path)
        return str(path)

    def write_eval_pdf(self, session: InterviewSession) -> Optional[str]:
        """
        生成评估报告 PDF（优先按会话数据排版，不打印 Markdown 原文）。

        @param session - 面试会话
        @returns PDF 路径或 None
        """
        if not session.report_path:
            self.write_markdown(session)
        pdf_path = Path(session.report_path).with_suffix(".pdf")
        html = self._html_eval_report(session)
        rendered = self._weasyprint_html(html, pdf_path)
        if rendered:
            return rendered
        return self._reportlab_eval_pdf(session, pdf_path)

    def write_qa_pdf(self, session: InterviewSession) -> Optional[str]:
        """
        生成问答实录 PDF。

        @param session - 面试会话
        @returns PDF 路径或 None
        """
        if not session.metadata.get("qa_path"):
            self.write_qa_markdown(session)
        pdf_path = Path(session.metadata["qa_path"]).with_suffix(".pdf")
        html = self._html_qa_report(session)
        rendered = self._weasyprint_html(html, pdf_path)
        if rendered:
            return rendered
        return self._reportlab_qa_pdf(session, pdf_path)

    def write_pdf(self, session: InterviewSession, md_path: Optional[str] = None) -> Optional[str]:
        """
        将评估报告转为 PDF。

        @param session - 面试会话
        @param md_path - 兼容旧调用，实际按会话数据排版
        @returns PDF 路径或 None
        """
        _ = md_path
        return self.write_eval_pdf(session)

    def markdown_to_pdf(self, md_path: str, title: str = "面试报告") -> Optional[str]:
        """
        将任意 Markdown 转为 PDF。优先使用结构化排版；否则降级。

        @param md_path - Markdown 路径
        @param title - HTML 标题
        @returns PDF 路径或 None
        """
        source = Path(md_path)
        if not source.exists():
            return None
        pdf_path = source.with_suffix(".pdf")
        md_text = source.read_text(encoding="utf-8")
        html = self._wrap_html(title, self._md_to_html(md_text))
        rendered = self._weasyprint_html(html, pdf_path)
        if rendered:
            return rendered
        dummy = InterviewSession(session_id="pdf")
        return self._fallback_pdf(dummy, source, pdf_path)

    def _weasyprint_html(self, html: str, pdf_path: Path) -> Optional[str]:
        """
        尝试用 WeasyPrint 输出 PDF。

        @param html - 完整 HTML
        @param pdf_path - 输出路径
        @returns 成功时的 PDF 路径
        """
        try:
            from weasyprint import HTML

            HTML(string=html).write_pdf(str(pdf_path))
            return str(pdf_path)
        except Exception as exc:
            print(f"[报告] WeasyPrint 不可用，改用排版 PDF：{exc}")
            return None

    @staticmethod
    def _esc(text: object) -> str:
        """
        转义 HTML / ReportLab 特殊字符。

        @param text - 原始文本
        @returns 转义后字符串
        """
        return (
            str(text or "")
            .replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
            .replace('"', "&quot;")
        )

    @classmethod
    def _rich(cls, text: object) -> str:
        """
        将纯文本转为可换行的富文本（支持 **加粗**）。

        @param text - 原始文本
        @returns 富文本
        """
        escaped = cls._esc(text).replace("\n", "<br/>")
        return re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", escaped)

    @staticmethod
    def _score_hex(score: float) -> str:
        """
        按分数返回强调色。

        @param score - 1-5 分
        @returns 十六进制颜色
        """
        if score >= 4:
            return "#1a9d5a"
        if score >= 3:
            return "#c48a00"
        return "#c0392b"

    def _question_type(self, question) -> str:
        """
        题型中文名。

        @param question - 问题对象
        @returns 中文题型
        """
        if not question:
            return ""
        value = question.type.value if hasattr(question.type, "value") else str(question.type)
        return self.TYPE_LABELS.get(value, value)

    def _build_eval_markdown(self, session: InterviewSession) -> str:
        """
        构建评估报告 Markdown（评分与建议，不含完整问答）。

        @param session - 面试会话
        @returns Markdown 字符串
        """
        jd = session.jd_profile
        resume = session.resume_profile
        summary = session.summary
        avg = summary.average_score if summary else 0.0
        name = resume.name if resume else "未知"
        job = f"{jd.title if jd else '未知'} @ {jd.company if jd else '互联网大厂'}"
        lines = [
            "# 面试评估报告",
            "",
            f"- **候选人**：{name}",
            f"- **应聘岗位**：{job}",
            f"- **面试日期**：{session.created_at:%Y-%m-%d %H:%M}",
            f"- **综合评分**：{avg:.1f} / 5.0",
            f"- **建议结论**：{summary.recommendation if summary else '待定'}",
            "",
            "> 完整问答请下载「问答实录」。",
            "",
            "## 一、总评速览",
            "",
        ]
        if summary:
            lines.extend([
                f"**一句话建议**：{summary.recommendation}",
                "",
                "### 优势",
                *[f"- {s}" for s in (summary.strengths or ["（暂无）"])],
                "",
                "### 风险",
                *[f"- {r}" for r in (summary.risks or ["（暂无）"])],
                "",
                f"**下一步建议**：{summary.next_steps or '—'}",
                "",
            ])
        else:
            lines.append("（评分尚未生成）\n")

        lines.extend(["## 二、JD 匹配分析", ""])
        if session.match_analysis:
            m = session.match_analysis
            lines.extend([
                f"**匹配度**：{m.overall_match_score:.0f} / 100",
                "",
                "### 匹配点",
                *[f"- {p}" for p in (m.match_points or ["（暂无）"])],
                "",
                "### 风险点",
                *[f"- {p}" for p in (m.risk_points or ["（暂无）"])],
                "",
            ])
        else:
            lines.append("（无匹配分析）\n")

        qmap = {q.id: q for q in session.questions}
        lines.extend(["## 三、逐题评估", ""])
        for i, score in enumerate(session.scores, 1):
            q = qmap.get(score.question_id)
            qtype = self._question_type(q)
            qtext = q.text if q else score.question_text
            lines.append(f"## 第 {i} 题 · {qtype}")
            lines.append("")
            lines.append(f"**本题得分：{score.total_score:.1f} / 5.0**")
            lines.append("")
            lines.append("**题目**")
            lines.append("")
            lines.append(qtext)
            lines.append("")
            lines.append("**维度评分**")
            lines.append("")
            for dim in score.dimensions:
                comment = (dim.comment or "—").replace("\n", " ")
                lines.append(f"- **{dim.dimension}（{dim.score}/5）**：{comment}")
            lines.append("")
            if score.evidence_quotes:
                lines.append("**作答证据**")
                lines.append("")
                for quote in score.evidence_quotes:
                    lines.append(f"> {quote}")
                lines.append("")
            lines.append("**反馈**")
            lines.append("")
            lines.append(score.feedback or "—")
            lines.append("")
            lines.append("**高分作答框架**")
            lines.append("")
            lines.append(score.high_score_framework or "—")
            lines.append("")
            if score.resume_inconsistency:
                lines.append(f"**简历一致性提醒**：{score.resume_inconsistency}")
                lines.append("")
            lines.append("---")
            lines.append("")

        lines.extend([
            "## 四、附录",
            "",
            f"- 报告生成时间：{datetime.now():%Y-%m-%d %H:%M:%S}",
            f"- 问题总数：{len(session.questions)}",
            f"- 对话轮次：{len(session.turns)}",
            f"- 会话 ID：{session.session_id}",
        ])
        return "\n".join(lines)

    def _build_qa_markdown(self, session: InterviewSession) -> str:
        """
        构建候选人问答实录。

        @param session - 面试会话
        @returns Markdown 字符串
        """
        jd = session.jd_profile
        resume = session.resume_profile
        skip_mark = SKIP_PLACEHOLDER
        lines = [
            "# 面试问答实录",
            "",
            f"- **候选人**：{resume.name if resume else '未知'}",
            f"- **岗位**：{jd.title if jd else '未知'} @ {jd.company if jd else '互联网大厂'}",
            f"- **日期**：{session.created_at:%Y-%m-%d %H:%M}",
            "",
            "---",
            "",
        ]
        for i, question in enumerate(session.questions, 1):
            qtype = self._question_type(question)
            lines.append(f"## 第 {i} 题 · {qtype}")
            lines.append("")
            lines.append(f"**题目**：{question.text}")
            lines.append("")
            q_turns = [t for t in session.turns if t.question_id == question.id]
            if not q_turns:
                lines.append("*本题未作答。*")
                lines.append("")
                continue
            fu_n = 0
            for turn in q_turns:
                if turn.is_follow_up:
                    fu_n += 1
                    lines.append(f"### 追问 {i}.{fu_n}")
                    lines.append("")
                lines.append(f"**面试官**")
                lines.append("")
                lines.append(turn.agent_text)
                lines.append("")
                answer = (turn.user_transcript or "").strip()
                lines.append("**候选人**")
                lines.append("")
                if not answer:
                    lines.append("*（未作答）*")
                elif answer == skip_mark:
                    lines.append("*（已跳过本题）*")
                else:
                    lines.append(answer)
                lines.append("")
            lines.append("---")
            lines.append("")
        return "\n".join(lines)

    def _html_eval_report(self, session: InterviewSession) -> str:
        """
        构建评估报告 HTML，供 WeasyPrint 使用。

        @param session - 面试会话
        @returns HTML 字符串
        """
        jd = session.jd_profile
        resume = session.resume_profile
        summary = session.summary
        match = session.match_analysis
        avg = summary.average_score if summary else 0.0
        name = self._esc(resume.name if resume else "未知")
        job = self._esc(f"{jd.title if jd else '未知'} @ {jd.company if jd else '互联网大厂'}")
        rec = self._esc(summary.recommendation if summary else "待定")
        match_score = f"{match.overall_match_score:.0f}" if match else "—"
        strength_html = "".join(f"<li>{self._esc(s)}</li>" for s in (summary.strengths if summary else []))
        risk_html = "".join(f"<li>{self._esc(r)}</li>" for r in (summary.risks if summary else []))
        match_html = "".join(f"<li>{self._esc(p)}</li>" for p in (match.match_points if match else []))
        riskp_html = "".join(f"<li>{self._esc(p)}</li>" for p in (match.risk_points if match else []))
        qmap = {q.id: q for q in session.questions}
        cards = []
        for i, score in enumerate(session.scores, 1):
            cards.append(self._html_question_card(i, score, qmap.get(score.question_id)))
        return self._wrap_html("面试评估报告", f"""
<div class="cover">
  <h1>面试评估报告</h1>
  <p>{name} · {job}</p>
  <p>{session.created_at:%Y-%m-%d %H:%M}</p>
</div>
<div class="kpi">
  <div class="kpi-item"><span>综合评分</span><strong>{avg:.1f}</strong><em>/ 5.0</em></div>
  <div class="kpi-item"><span>建议结论</span><strong class="kpi-rec">{rec}</strong></div>
  <div class="kpi-item"><span>JD 匹配</span><strong>{match_score}</strong><em>/ 100</em></div>
</div>
<h2>总评速览</h2>
<div class="two">
  <div class="box good"><h3>优势</h3><ul>{strength_html or "<li>暂无</li>"}</ul></div>
  <div class="box warn"><h3>风险</h3><ul>{risk_html or "<li>暂无</li>"}</ul></div>
</div>
<p class="next"><b>下一步：</b>{self._rich(summary.next_steps if summary else "—")}</p>
<h2>JD 匹配分析</h2>
<div class="two">
  <div class="box good"><h3>匹配点</h3><ul>{match_html or "<li>暂无</li>"}</ul></div>
  <div class="box warn"><h3>风险点</h3><ul>{riskp_html or "<li>暂无</li>"}</ul></div>
</div>
<h2>逐题评估</h2>
{"".join(cards)}
<p class="foot">生成时间 {datetime.now():%Y-%m-%d %H:%M} · 共 {len(session.questions)} 题 · {len(session.turns)} 轮对话</p>
""")

    def _html_question_card(self, index: int, score: QuestionScore, question) -> str:
        """
        单题评估 HTML 卡片。

        @param index - 题号
        @param score - 评分
        @param question - 问题
        @returns HTML
        """
        qtype = self._esc(self._question_type(question))
        qtext = self._esc(question.text if question else score.question_text)
        color = self._score_hex(score.total_score)
        dims = []
        for dim in score.dimensions:
            pct = max(0, min(100, int(dim.score) * 20))
            dims.append(f"""
            <div class="dim">
              <div class="dim-top"><b>{self._esc(dim.dimension)}</b><span style="color:{self._score_hex(dim.score)}">{dim.score}/5</span></div>
              <div class="bar"><i style="width:{pct}%;background:{self._score_hex(dim.score)}"></i></div>
              <p>{self._esc(dim.comment or "—")}</p>
            </div>""")
        quotes = "".join(f"<blockquote>{self._esc(q)}</blockquote>" for q in (score.evidence_quotes or []))
        alert = (
            f'<div class="alert">简历一致性提醒：{self._esc(score.resume_inconsistency)}</div>'
            if score.resume_inconsistency else ""
        )
        return f"""
<article class="qcard">
  <header>
    <div>第 {index} 题 · {qtype}</div>
    <strong style="color:{color}">{score.total_score:.1f} <small>/ 5.0</small></strong>
  </header>
  <p class="qtext">{qtext}</p>
  <div class="dims">{"".join(dims)}</div>
  <div class="panel"><h4>反馈</h4><p>{self._rich(score.feedback)}</p></div>
  {f'<div class="panel"><h4>作答证据</h4>{quotes}</div>' if quotes else ""}
  <div class="panel star"><h4>高分作答框架</h4><p>{self._rich(score.high_score_framework)}</p></div>
  {alert}
</article>
"""

    def _html_qa_report(self, session: InterviewSession) -> str:
        """
        构建问答实录 HTML。

        @param session - 面试会话
        @returns HTML
        """
        jd = session.jd_profile
        resume = session.resume_profile
        name = self._esc(resume.name if resume else "未知")
        job = self._esc(f"{jd.title if jd else '未知'} @ {jd.company if jd else '互联网大厂'}")
        blocks = []
        for i, question in enumerate(session.questions, 1):
            qtype = self._esc(self._question_type(question))
            turns_html = []
            q_turns = [t for t in session.turns if t.question_id == question.id]
            fu_n = 0
            if not q_turns:
                turns_html.append("<p class='muted'>本题未作答。</p>")
            for turn in q_turns:
                if turn.is_follow_up:
                    fu_n += 1
                    turns_html.append(f"<h4>追问 {i}.{fu_n}</h4>")
                turns_html.append(f'<div class="bubble iv"><b>面试官</b><p>{self._rich(turn.agent_text)}</p></div>')
                answer = (turn.user_transcript or "").strip()
                if not answer:
                    body = "（未作答）"
                elif answer == SKIP_PLACEHOLDER:
                    body = "（已跳过本题）"
                else:
                    body = answer
                turns_html.append(f'<div class="bubble cand"><b>候选人</b><p>{self._rich(body)}</p></div>')
            blocks.append(f"""
            <article class="qcard">
              <header><div>第 {i} 题 · {qtype}</div></header>
              <p class="qtext">{self._esc(question.text)}</p>
              {"".join(turns_html)}
            </article>
            """)
        return self._wrap_html("面试问答实录", f"""
<div class="cover">
  <h1>面试问答实录</h1>
  <p>{name} · {job}</p>
  <p>{session.created_at:%Y-%m-%d %H:%M}</p>
</div>
{"".join(blocks)}
""")

    def _wrap_html(self, title: str, body: str) -> str:
        """
        包裹报告 HTML 与打印样式。

        @param title - 文档标题
        @param body - 主体
        @returns 完整 HTML
        """
        return f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"><title>{self._esc(title)}</title>
<style>
@page {{ size: A4; margin: 14mm 14mm 16mm; }}
body {{ font-family: "Microsoft YaHei", "PingFang SC", sans-serif; color: #1f2430; line-height: 1.65; font-size: 12.5px; }}
.cover {{ background: linear-gradient(90deg,#5b6ee1,#7b5ea7); color: #fff; padding: 20px 22px; border-radius: 12px; margin-bottom: 16px; }}
.cover h1 {{ margin: 0 0 8px; font-size: 22px; }}
.cover p {{ margin: 0; opacity: .92; }}
.kpi {{ display: table; width: 100%; margin: 0 0 18px; border: 1px solid #e6e4f5; border-radius: 10px; overflow: hidden; }}
.kpi-item {{ display: table-cell; width: 33%; padding: 12px 14px; background: #f7f6ff; vertical-align: top; }}
.kpi-item span {{ display: block; color: #6b6f88; font-size: 11px; }}
.kpi-item strong {{ font-size: 22px; color: #3d3a8a; }}
.kpi-item em {{ color: #888; font-style: normal; font-size: 12px; }}
.kpi-rec {{ font-size: 14px !important; }}
h2 {{ color: #2b2f55; border-bottom: 2px solid #ece8ff; padding-bottom: 6px; margin: 22px 0 10px; font-size: 15px; }}
.two {{ display: table; width: 100%; border-spacing: 10px 0; margin: 0 -10px 12px; }}
.two .box {{ display: table-cell; width: 50%; }}
.box {{ background: #fbfbfe; border: 1px solid #eceaf6; border-radius: 10px; padding: 10px 12px; }}
.box h3 {{ margin: 0 0 6px; font-size: 13px; }}
.box.good {{ border-color: #c8ecd6; }}
.box.good h3 {{ color: #1a9d5a; }}
.box.warn {{ border-color: #f3e0a8; }}
.box.warn h3 {{ color: #c48a00; }}
.box ul {{ margin: 0; padding-left: 18px; }}
.next {{ background: #f5f4ff; border-left: 3px solid #7b6cff; padding: 8px 12px; }}
.qcard {{ border: 1px solid #e4e1f2; border-radius: 12px; padding: 12px 14px; margin: 0 0 14px; page-break-inside: avoid; }}
.qcard header {{ display: table; width: 100%; margin-bottom: 8px; }}
.qcard header div, .qcard header strong {{ display: table-cell; vertical-align: middle; }}
.qcard header div {{ color: #5b5f8a; font-size: 12px; }}
.qcard header strong {{ text-align: right; font-size: 20px; }}
.qcard header small {{ font-size: 12px; color: #888; font-weight: 500; }}
.qtext {{ background: #f5f4ff; border-left: 3px solid #7b6cff; padding: 8px 10px; color: #3d3a6b; }}
.dims {{ margin: 8px 0; }}
.dim {{ margin: 0 0 8px; padding: 8px 10px; background: #fafafe; border-radius: 8px; }}
.dim-top {{ display: table; width: 100%; }}
.dim-top b, .dim-top span {{ display: table-cell; }}
.dim-top span {{ text-align: right; font-weight: 700; }}
.bar {{ height: 6px; background: #eceaf6; border-radius: 99px; margin: 6px 0; overflow: hidden; }}
.bar i {{ display: block; height: 100%; }}
.dim p {{ margin: 0; color: #5a5e73; font-size: 12px; }}
.panel {{ background: #fbfbfe; border-radius: 8px; padding: 8px 10px; margin-top: 8px; }}
.panel h4 {{ margin: 0 0 4px; color: #5b5f8a; font-size: 12px; }}
.panel.star {{ border: 1px solid #ddd7ff; }}
blockquote {{ margin: 6px 0; padding: 6px 10px; border-left: 3px solid #7b6cff; background: #f7f6ff; color: #444; }}
.alert {{ background: #fdeeee; border: 1px solid #f5c6c6; color: #a94442; padding: 8px 10px; border-radius: 8px; margin-top: 8px; }}
.bubble {{ border-radius: 8px; padding: 8px 10px; margin: 8px 0; }}
.bubble.iv {{ background: #f3f0ff; border-left: 3px solid #7b6cff; }}
.bubble.cand {{ background: #eef8f2; border-left: 3px solid #2ecc71; }}
.muted {{ color: #888; }}
.foot {{ color: #888; font-size: 11px; margin-top: 18px; }}
</style></head><body>{body}</body></html>"""

    @staticmethod
    def _md_to_html(md_text: str) -> str:
        """
        将 Markdown 转为 HTML。

        @param md_text - Markdown
        @returns HTML 片段
        """
        try:
            import markdown
            return markdown.markdown(md_text, extensions=["tables", "fenced_code"])
        except Exception:
            return f"<pre>{md_text}</pre>"

    def _reportlab_eval_pdf(self, session: InterviewSession, pdf_path: Path) -> Optional[str]:
        """
        用 reportlab 按会话数据生成评估 PDF。

        @param session - 面试会话
        @param pdf_path - 输出路径
        @returns PDF 路径或 None
        """
        try:
            from reportlab.lib.colors import HexColor, white
            from reportlab.lib.enums import TA_CENTER, TA_RIGHT
            from reportlab.lib.pagesizes import A4
            from reportlab.lib.styles import ParagraphStyle
            from reportlab.lib.units import mm
            from reportlab.platypus import (
                KeepTogether,
                Paragraph,
                SimpleDocTemplate,
                Spacer,
                Table,
                TableStyle,
            )
        except ImportError:
            print("[报告] 未安装 reportlab，跳过 PDF")
            return None

        try:
            regular, bold = self._register_cjk_fonts()
            page_w, page_h = A4
            margin = 16 * mm
            width = page_w - 2 * margin
            styles = self._pdf_styles(regular, bold)
            jd = session.jd_profile
            resume = session.resume_profile
            summary = session.summary
            match = session.match_analysis
            avg = summary.average_score if summary else 0.0
            name = resume.name if resume else "未知"
            job = f"{jd.title if jd else '未知'} @ {jd.company if jd else '互联网大厂'}"
            rec = summary.recommendation if summary else "待定"

            story = []
            cover = Table(
                [
                    [Paragraph("面试评估报告", styles["cover_title"])],
                    [Paragraph(self._esc(f"{name}  ·  {job}"), styles["cover_sub"])],
                    [Paragraph(f"{session.created_at:%Y-%m-%d %H:%M}", styles["cover_sub"])],
                ],
                colWidths=[width],
            )
            cover.setStyle(TableStyle([
                ("BACKGROUND", (0, 0), (-1, -1), HexColor("#5b6ee1")),
                ("LEFTPADDING", (0, 0), (-1, -1), 14),
                ("RIGHTPADDING", (0, 0), (-1, -1), 14),
                ("TOPPADDING", (0, 0), (0, 0), 14),
                ("BOTTOMPADDING", (0, -1), (-1, -1), 12),
                ("TOPPADDING", (0, 1), (-1, -1), 2),
                ("BOTTOMPADDING", (0, 0), (0, 0), 6),
            ]))
            story.append(cover)
            story.append(Spacer(1, 10))

            kpi = Table(
                [[
                    Paragraph(f"综合评分<br/><font color='#3d3a8a' size='16'><b>{avg:.1f}</b></font> / 5.0", styles["kpi"]),
                    Paragraph(f"建议结论<br/><b>{self._esc(rec)}</b>", styles["kpi"]),
                    Paragraph(
                        f"JD 匹配<br/><font color='#3d3a8a' size='16'><b>{match.overall_match_score:.0f}</b></font> / 100"
                        if match else "JD 匹配<br/>—",
                        styles["kpi"],
                    ),
                ]],
                colWidths=[width / 3.0] * 3,
            )
            kpi.setStyle(TableStyle([
                ("BACKGROUND", (0, 0), (-1, -1), HexColor("#f7f6ff")),
                ("BOX", (0, 0), (-1, -1), 0.6, HexColor("#e0def2")),
                ("INNERGRID", (0, 0), (-1, -1), 0.4, HexColor("#e0def2")),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 10),
                ("RIGHTPADDING", (0, 0), (-1, -1), 10),
                ("TOPPADDING", (0, 0), (-1, -1), 8),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
            ]))
            story.append(kpi)
            story.append(Paragraph("一、总评速览", styles["h1"]))
            story.append(self._two_list_table(
                "优势",
                summary.strengths if summary else [],
                "风险",
                summary.risks if summary else [],
                width,
                styles,
            ))
            if summary and summary.next_steps:
                story.append(self._quote_table(f"<b>下一步：</b>{self._rich(summary.next_steps)}", width, styles))
            story.append(Paragraph("二、JD 匹配分析", styles["h1"]))
            if match:
                story.append(self._two_list_table("匹配点", match.match_points, "风险点", match.risk_points, width, styles))
            else:
                story.append(Paragraph("（无匹配分析）", styles["body"]))

            story.append(Paragraph("三、逐题评估", styles["h1"]))
            qmap = {q.id: q for q in session.questions}
            for i, score in enumerate(session.scores, 1):
                story.extend(self._pdf_question_block(i, score, qmap.get(score.question_id), width, styles))

            story.append(Paragraph("四、附录", styles["h1"]))
            story.append(Paragraph(
                f"报告生成时间：{datetime.now():%Y-%m-%d %H:%M:%S}　"
                f"问题总数：{len(session.questions)}　对话轮次：{len(session.turns)}",
                styles["muted"],
            ))

            def _on_page(canvas, doc):
                canvas.saveState()
                if doc.page > 1:
                    canvas.setFillColor(HexColor("#5b6ee1"))
                    canvas.rect(0, page_h - 10 * mm, page_w, 10 * mm, fill=1, stroke=0)
                    canvas.setFillColor(white)
                    canvas.setFont(regular, 8)
                    canvas.drawString(margin, page_h - 6.5 * mm, "智能面试 Agent  ·  评估报告")
                    canvas.drawRightString(page_w - margin, page_h - 6.5 * mm, f"{doc.page}")
                canvas.setFillColor(HexColor("#d9d6ee"))
                canvas.rect(margin, 10 * mm, width, 0.4, fill=1, stroke=0)
                canvas.setFillColor(HexColor("#8b8eae"))
                canvas.drawCentredString(page_w / 2, 6 * mm, f"{name}  |  {job}")
                canvas.restoreState()

            doc = SimpleDocTemplate(
                str(pdf_path),
                pagesize=A4,
                leftMargin=margin,
                rightMargin=margin,
                topMargin=16 * mm,
                bottomMargin=16 * mm,
                title="面试评估报告",
            )
            doc.build(story, onFirstPage=_on_page, onLaterPages=_on_page)
            return str(pdf_path)
        except Exception as exc:
            print(f"[报告] 评估 PDF 排版失败：{exc}")
            return None

    def _reportlab_qa_pdf(self, session: InterviewSession, pdf_path: Path) -> Optional[str]:
        """
        用 reportlab 生成问答实录 PDF。

        @param session - 面试会话
        @param pdf_path - 输出路径
        @returns PDF 路径或 None
        """
        try:
            from reportlab.lib.colors import HexColor, white
            from reportlab.lib.pagesizes import A4
            from reportlab.lib.units import mm
            from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
        except ImportError:
            print("[报告] 未安装 reportlab，跳过 PDF")
            return None

        try:
            regular, bold = self._register_cjk_fonts()
            page_w, page_h = A4
            margin = 16 * mm
            width = page_w - 2 * margin
            styles = self._pdf_styles(regular, bold)
            jd = session.jd_profile
            resume = session.resume_profile
            name = resume.name if resume else "未知"
            job = f"{jd.title if jd else '未知'} @ {jd.company if jd else '互联网大厂'}"
            story = []
            cover = Table(
                [
                    [Paragraph("面试问答实录", styles["cover_title"])],
                    [Paragraph(self._esc(f"{name}  ·  {job}"), styles["cover_sub"])],
                    [Paragraph(f"{session.created_at:%Y-%m-%d %H:%M}", styles["cover_sub"])],
                ],
                colWidths=[width],
            )
            cover.setStyle(TableStyle([
                ("BACKGROUND", (0, 0), (-1, -1), HexColor("#5b6ee1")),
                ("LEFTPADDING", (0, 0), (-1, -1), 14),
                ("RIGHTPADDING", (0, 0), (-1, -1), 14),
                ("TOPPADDING", (0, 0), (0, 0), 14),
                ("BOTTOMPADDING", (0, -1), (-1, -1), 12),
                ("TOPPADDING", (0, 1), (-1, -1), 2),
                ("BOTTOMPADDING", (0, 0), (0, 0), 6),
            ]))
            story.append(cover)
            story.append(Spacer(1, 12))

            for i, question in enumerate(session.questions, 1):
                qtype = self._question_type(question)
                story.append(Paragraph(f"第 {i} 题 · {self._esc(qtype)}", styles["h2"]))
                story.append(self._quote_table(self._rich(question.text), width, styles))
                q_turns = [t for t in session.turns if t.question_id == question.id]
                if not q_turns:
                    story.append(Paragraph("本题未作答。", styles["muted"]))
                    continue
                fu_n = 0
                for turn in q_turns:
                    if turn.is_follow_up:
                        fu_n += 1
                        story.append(Paragraph(f"追问 {i}.{fu_n}", styles["h3"]))
                    story.append(self._bubble_table("面试官", turn.agent_text, width, styles, interviewer=True))
                    answer = (turn.user_transcript or "").strip()
                    if not answer:
                        body = "（未作答）"
                    elif answer == SKIP_PLACEHOLDER:
                        body = "（已跳过本题）"
                    else:
                        body = answer
                    story.append(self._bubble_table("候选人", body, width, styles, interviewer=False))
                story.append(Spacer(1, 8))

            def _on_page(canvas, doc):
                canvas.saveState()
                canvas.setFillColor(HexColor("#5b6ee1"))
                canvas.rect(0, page_h - 10 * mm, page_w, 10 * mm, fill=1, stroke=0)
                canvas.setFillColor(white)
                canvas.setFont(regular, 8)
                canvas.drawString(margin, page_h - 6.5 * mm, "智能面试 Agent  ·  问答实录")
                canvas.drawRightString(page_w - margin, page_h - 6.5 * mm, f"{doc.page}")
                canvas.restoreState()

            doc = SimpleDocTemplate(
                str(pdf_path),
                pagesize=A4,
                leftMargin=margin,
                rightMargin=margin,
                topMargin=16 * mm,
                bottomMargin=16 * mm,
                title="面试问答实录",
            )
            doc.build(story, onFirstPage=_on_page, onLaterPages=_on_page)
            return str(pdf_path)
        except Exception as exc:
            print(f"[报告] 问答 PDF 排版失败：{exc}")
            return None

    def _pdf_question_block(self, index: int, score: QuestionScore, question, width: float, styles) -> list:
        """
        构建单题 PDF 内容块。

        @param index - 题号
        @param score - 评分
        @param question - 问题
        @param width - 可用宽度
        @param styles - 段落样式
        @returns flowable 列表
        """
        from reportlab.lib.colors import HexColor
        from reportlab.lib.enums import TA_RIGHT
        from reportlab.lib.styles import ParagraphStyle
        from reportlab.platypus import Paragraph, Spacer, Table, TableStyle

        qtype = self._question_type(question)
        qtext = question.text if question else score.question_text
        color = self._score_hex(score.total_score)
        right = ParagraphStyle(
            f"score_{index}",
            parent=styles["score"],
            textColor=HexColor(color),
            alignment=TA_RIGHT,
        )
        head = Table(
            [[
                Paragraph(f"第 {index} 题 · {self._esc(qtype)}", styles["qtitle"]),
                Paragraph(f"{score.total_score:.1f} <font size='9' color='#888'>/ 5.0</font>", right),
            ]],
            colWidths=[width * 0.72, width * 0.28],
        )
        head.setStyle(TableStyle([
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("LEFTPADDING", (0, 0), (-1, -1), 0),
            ("RIGHTPADDING", (0, 0), (-1, -1), 0),
        ]))
        items = [head, Spacer(1, 4), self._quote_table(self._rich(qtext), width, styles), Spacer(1, 6)]
        items.append(self._dim_table(score.dimensions, width, styles))
        items.append(Spacer(1, 6))
        items.append(Paragraph("反馈", styles["h3"]))
        items.append(Paragraph(self._rich(score.feedback or "—"), styles["body"]))
        if score.evidence_quotes:
            items.append(Paragraph("作答证据", styles["h3"]))
            for quote in score.evidence_quotes:
                items.append(self._quote_table(self._rich(quote), width, styles))
        items.append(Paragraph("高分作答框架", styles["h3"]))
        items.append(self._framework_table(score.high_score_framework or "—", width, styles))
        if score.resume_inconsistency:
            items.append(self._alert_table(f"简历一致性提醒：{score.resume_inconsistency}", width, styles))
        from reportlab.lib.colors import HexColor as _Hex
        from reportlab.platypus import HRFlowable
        items.append(HRFlowable(width="100%", thickness=0.8, color=_Hex("#e0def2"), spaceBefore=10, spaceAfter=12))
        return items

    def _dim_table(self, dimensions, width: float, styles):
        """
        维度评分表。

        @param dimensions - 维度列表
        @param width - 宽度
        @param styles - 样式
        @returns Table
        """
        from reportlab.lib.colors import HexColor
        from reportlab.lib.enums import TA_CENTER
        from reportlab.lib.styles import ParagraphStyle
        from reportlab.platypus import Paragraph, Table, TableStyle

        if not dimensions:
            return Paragraph("（无维度评分）", styles["muted"])
        score_style = ParagraphStyle("dim_score", parent=styles["body"], alignment=TA_CENTER, fontName=styles["body"].fontName)
        header = [
            Paragraph("<b>评分维度</b>", styles["th"]),
            Paragraph("<b>分数</b>", styles["th"]),
            Paragraph("<b>评语</b>", styles["th"]),
        ]
        rows = [header]
        extra = []
        for i, dim in enumerate(dimensions, 1):
            color = self._score_hex(dim.score)
            score_cell = Table(
                [[
                    Paragraph(f"<font color='{color}'><b>{dim.score}</b></font> / 5", score_style),
                ], [
                    self._score_bar(dim.score),
                ]],
                colWidths=[52],
            )
            score_cell.setStyle(TableStyle([
                ("LEFTPADDING", (0, 0), (-1, -1), 2),
                ("RIGHTPADDING", (0, 0), (-1, -1), 2),
                ("TOPPADDING", (0, 0), (-1, -1), 1),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 1),
                ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ]))
            rows.append([
                Paragraph(self._esc(dim.dimension), styles["body"]),
                score_cell,
                Paragraph(self._rich(dim.comment or "—"), styles["comment"]),
            ])
            bg = "#eaf8f0" if dim.score >= 4 else ("#fff7e0" if dim.score >= 3 else "#fdeeee")
            extra.append(("BACKGROUND", (1, i), (1, i), HexColor(bg)))
        table = Table(rows, colWidths=[78, 58, width - 136])
        table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), HexColor("#eef0fb")),
            ("BACKGROUND", (0, 1), (0, -1), HexColor("#fbfbfe")),
            ("BACKGROUND", (2, 1), (2, -1), HexColor("#fbfbfe")),
            ("GRID", (0, 0), (-1, -1), 0.4, HexColor("#e0e2f0")),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("LEFTPADDING", (0, 0), (-1, -1), 8),
            ("RIGHTPADDING", (0, 0), (-1, -1), 8),
            ("TOPPADDING", (0, 0), (-1, -1), 6),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
            *extra,
        ]))
        return table

    def _score_bar(self, score: int):
        """
        五段分数条。

        @param score - 1-5 分
        @returns 分数条 Table
        """
        from reportlab.lib.colors import HexColor
        from reportlab.platypus import Table, TableStyle

        fill = HexColor(self._score_hex(score))
        empty = HexColor("#e4e1f2")
        table = Table([[""] * 5], colWidths=[10] * 5, rowHeights=[7])
        cmds = [
            ("LEFTPADDING", (0, 0), (-1, -1), 0.6),
            ("RIGHTPADDING", (0, 0), (-1, -1), 0.6),
            ("TOPPADDING", (0, 0), (-1, -1), 0),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
        ]
        for idx in range(5):
            cmds.append(("BACKGROUND", (idx, 0), (idx, 0), fill if idx < int(score) else empty))
        table.setStyle(TableStyle(cmds))
        return table


    def _two_list_table(self, left_title: str, left_items, right_title: str, right_items, width: float, styles):
        """
        左右两列要点表。

        @param left_title - 左标题
        @param left_items - 左列表
        @param right_title - 右标题
        @param right_items - 右列表
        @param width - 宽度
        @param styles - 样式
        @returns Table
        """
        from reportlab.lib.colors import HexColor
        from reportlab.platypus import Paragraph, Table, TableStyle

        def _cell(title: str, items, color: str) -> List:
            bullets = items or ["（暂无）"]
            html = f"<font color='{color}'><b>{self._esc(title)}</b></font><br/>" + "<br/>".join(
                f"• {self._esc(item)}" for item in bullets
            )
            return [Paragraph(html, styles["body"])]

        table = Table(
            [[_cell(left_title, left_items, "#1a9d5a")[0], _cell(right_title, right_items, "#c48a00")[0]]],
            colWidths=[width / 2 - 4, width / 2 - 4],
        )
        table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (0, 0), HexColor("#f3fbf6")),
            ("BACKGROUND", (1, 0), (1, 0), HexColor("#fff9eb")),
            ("BOX", (0, 0), (0, 0), 0.6, HexColor("#c8ecd6")),
            ("BOX", (1, 0), (1, 0), 0.6, HexColor("#f3e0a8")),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("LEFTPADDING", (0, 0), (-1, -1), 8),
            ("RIGHTPADDING", (0, 0), (-1, -1), 8),
            ("TOPPADDING", (0, 0), (-1, -1), 8),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
            ("RIGHTPADDING", (0, 0), (0, 0), 10),
            ("LEFTPADDING", (1, 0), (1, 0), 10),
        ]))
        return table

    def _quote_table(self, html: str, width: float, styles):
        """
        引用块。

        @param html - 已转义富文本
        @param width - 宽度
        @param styles - 样式
        @returns Table
        """
        from reportlab.lib.colors import HexColor
        from reportlab.platypus import Paragraph, Table, TableStyle

        table = Table([[Paragraph(html, styles["quote"])]], colWidths=[width])
        table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), HexColor("#f5f4ff")),
            ("LINEBEFORE", (0, 0), (0, -1), 3, HexColor("#7b6cff")),
            ("LEFTPADDING", (0, 0), (-1, -1), 10),
            ("RIGHTPADDING", (0, 0), (-1, -1), 8),
            ("TOPPADDING", (0, 0), (-1, -1), 7),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
        ]))
        return table

    def _framework_table(self, text: str, width: float, styles):
        """
        高分框架块。

        @param text - 框架文本
        @param width - 宽度
        @param styles - 样式
        @returns Table
        """
        from reportlab.lib.colors import HexColor
        from reportlab.platypus import Paragraph, Table, TableStyle

        table = Table([[Paragraph(self._rich(text), styles["body"])]], colWidths=[width])
        table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), HexColor("#f8f7ff")),
            ("BOX", (0, 0), (-1, -1), 0.6, HexColor("#ddd7ff")),
            ("LEFTPADDING", (0, 0), (-1, -1), 10),
            ("RIGHTPADDING", (0, 0), (-1, -1), 8),
            ("TOPPADDING", (0, 0), (-1, -1), 8),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
        ]))
        return table

    def _alert_table(self, text: str, width: float, styles):
        """
        警告提示块。

        @param text - 文本
        @param width - 宽度
        @param styles - 样式
        @returns Table
        """
        from reportlab.lib.colors import HexColor
        from reportlab.platypus import Paragraph, Table, TableStyle

        table = Table([[Paragraph(self._esc(text), styles["body"])]], colWidths=[width])
        table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), HexColor("#fdeeee")),
            ("BOX", (0, 0), (-1, -1), 0.6, HexColor("#f5c6c6")),
            ("LEFTPADDING", (0, 0), (-1, -1), 8),
            ("RIGHTPADDING", (0, 0), (-1, -1), 8),
            ("TOPPADDING", (0, 0), (-1, -1), 6),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ]))
        return table

    def _bubble_table(self, speaker: str, text: str, width: float, styles, interviewer: bool):
        """
        对话气泡。

        @param speaker - 说话人
        @param text - 内容
        @param width - 宽度
        @param styles - 样式
        @param interviewer - 是否面试官
        @returns Table
        """
        from reportlab.lib.colors import HexColor
        from reportlab.platypus import Paragraph, Spacer, Table, TableStyle

        bg = HexColor("#f3f0ff") if interviewer else HexColor("#eef8f2")
        bar = HexColor("#7b6cff") if interviewer else HexColor("#2ecc71")
        table = Table(
            [[Paragraph(f"<b>{self._esc(speaker)}</b><br/>{self._rich(text)}", styles["body"])]],
            colWidths=[width],
        )
        table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), bg),
            ("LINEBEFORE", (0, 0), (0, -1), 3, bar),
            ("LEFTPADDING", (0, 0), (-1, -1), 10),
            ("RIGHTPADDING", (0, 0), (-1, -1), 8),
            ("TOPPADDING", (0, 0), (-1, -1), 7),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
        ]))
        wrap = Table([[table], [Spacer(1, 4)]], colWidths=[width])
        wrap.setStyle(TableStyle([
            ("LEFTPADDING", (0, 0), (-1, -1), 0),
            ("RIGHTPADDING", (0, 0), (-1, -1), 0),
            ("TOPPADDING", (0, 0), (-1, -1), 0),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
        ]))
        return wrap

    @staticmethod
    def _pdf_styles(regular: str, bold: str) -> dict:
        """
        构建 PDF 段落样式。

        @param regular - 常规字体名
        @param bold - 粗体字体名
        @returns 样式字典
        """
        from reportlab.lib.colors import HexColor, white
        from reportlab.lib.styles import ParagraphStyle

        body = ParagraphStyle(
            "body",
            fontName=regular,
            fontSize=9.5,
            leading=15,
            textColor=HexColor("#2c3140"),
        )
        return {
            "cover_title": ParagraphStyle("cover_title", fontName=bold, fontSize=20, leading=26, textColor=white),
            "cover_sub": ParagraphStyle("cover_sub", fontName=regular, fontSize=10, leading=14, textColor=white),
            "h1": ParagraphStyle("h1", fontName=bold, fontSize=13, leading=18, textColor=HexColor("#2b2f55"), spaceBefore=12, spaceAfter=8),
            "h2": ParagraphStyle("h2", fontName=bold, fontSize=12, leading=16, textColor=HexColor("#4e57c5"), spaceBefore=10, spaceAfter=6),
            "h3": ParagraphStyle("h3", fontName=bold, fontSize=10, leading=14, textColor=HexColor("#5b5f8a"), spaceBefore=8, spaceAfter=4),
            "body": body,
            "comment": ParagraphStyle("comment", parent=body, fontSize=9, leading=13.5, textColor=HexColor("#4a4f63")),
            "quote": ParagraphStyle("quote", parent=body, textColor=HexColor("#3d3a6b"), fontSize=9, leading=14),
            "muted": ParagraphStyle("muted", parent=body, textColor=HexColor("#8b8eae"), fontSize=9),
            "th": ParagraphStyle("th", fontName=bold, fontSize=9, leading=13, textColor=HexColor("#3d3a8a")),
            "qtitle": ParagraphStyle("qtitle", fontName=bold, fontSize=11, leading=15, textColor=HexColor("#2b2f55")),
            "score": ParagraphStyle("score", fontName=bold, fontSize=16, leading=20),
            "kpi": ParagraphStyle("kpi", fontName=regular, fontSize=9, leading=14, textColor=HexColor("#5a5e73")),
        }

    def _register_cjk_fonts(self) -> Tuple[str, str]:
        """
        注册中文常规/粗体字体。

        @returns (常规字体名, 粗体字体名)
        """
        from reportlab.pdfbase import pdfmetrics
        from reportlab.pdfbase.ttfonts import TTFont

        regular_name = "ReportCJK"
        bold_name = "ReportCJK-Bold"
        if regular_name in pdfmetrics.getRegisteredFontNames():
            bold_ok = bold_name in pdfmetrics.getRegisteredFontNames()
            try:
                from reportlab.pdfbase.pdfmetrics import registerFontFamily
                registerFontFamily(
                    regular_name,
                    normal=regular_name,
                    bold=bold_name if bold_ok else regular_name,
                )
            except Exception:
                pass
            return regular_name, bold_name if bold_ok else regular_name

        from reportlab.pdfbase.pdfmetrics import registerFontFamily

        regular_candidates = [
            Path(r"C:\Windows\Fonts\msyh.ttc"),
            Path(r"C:\Windows\Fonts\msyh.ttf"),
            Path(r"C:\Windows\Fonts\simhei.ttf"),
            Path(r"C:\Windows\Fonts\simsun.ttc"),
            Path("/usr/share/fonts/truetype/wqy/wqy-microhei.ttc"),
            Path("/System/Library/Fonts/STHeiti Light.ttc"),
        ]
        bold_candidates = [
            Path(r"C:\Windows\Fonts\msyhbd.ttc"),
            Path(r"C:\Windows\Fonts\msyhbd.ttf"),
            Path(r"C:\Windows\Fonts\simhei.ttf"),
        ]
        registered = False
        for font_path in regular_candidates:
            if not font_path.exists():
                continue
            try:
                if font_path.suffix.lower() == ".ttc":
                    pdfmetrics.registerFont(TTFont(regular_name, str(font_path), subfontIndex=0))
                else:
                    pdfmetrics.registerFont(TTFont(regular_name, str(font_path)))
                registered = True
                break
            except Exception:
                continue
        if not registered:
            return "Helvetica", "Helvetica-Bold"

        for font_path in bold_candidates:
            if not font_path.exists():
                continue
            try:
                if font_path.suffix.lower() == ".ttc":
                    pdfmetrics.registerFont(TTFont(bold_name, str(font_path), subfontIndex=0))
                else:
                    pdfmetrics.registerFont(TTFont(bold_name, str(font_path)))
                registerFontFamily(regular_name, normal=regular_name, bold=bold_name)
                return regular_name, bold_name
            except Exception:
                continue
        return regular_name, regular_name

    def _fallback_pdf(self, session: InterviewSession, md_path: Path, pdf_path: Path) -> Optional[str]:
        """
        无会话结构时，尽量解析 Markdown 再输出 PDF（跳过表格分隔线）。

        @param session - 占位会话
        @param md_path - Markdown 路径
        @param pdf_path - 输出 PDF 路径
        @returns PDF 路径或 None
        """
        _ = session
        try:
            from reportlab.lib.pagesizes import A4
            from reportlab.lib.units import mm
            from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer
        except ImportError:
            print("[报告] 未安装 reportlab，跳过 PDF")
            return None
        try:
            regular, bold = self._register_cjk_fonts()
            styles = self._pdf_styles(regular, bold)
            story = []
            for raw in md_path.read_text(encoding="utf-8").split("\n"):
                line = raw.strip()
                if not line or re.match(r"^\|?\s*:?-{3,}", line) or line.startswith("|---"):
                    continue
                if line.startswith("|") and line.endswith("|"):
                    cells = [c.strip() for c in line.strip("|").split("|")]
                    line = "　".join(cells)
                if line.startswith("### "):
                    story.append(Paragraph(self._esc(line[4:]), styles["h2"]))
                elif line.startswith("## "):
                    story.append(Paragraph(self._esc(line[3:]), styles["h1"]))
                elif line.startswith("# "):
                    story.append(Paragraph(self._esc(line[2:]), styles["h1"]))
                elif line.startswith(">"):
                    story.append(self._quote_table(self._rich(line.lstrip("> ").strip()), A4[0] - 32 * mm, styles))
                else:
                    story.append(Paragraph(self._rich(line), styles["body"]))
                story.append(Spacer(1, 4))
            doc = SimpleDocTemplate(str(pdf_path), pagesize=A4, leftMargin=16 * mm, rightMargin=16 * mm, topMargin=16 * mm, bottomMargin=16 * mm)
            doc.build(story)
            return str(pdf_path)
        except Exception as exc:
            print(f"[报告] 简易 PDF 生成失败，仅保留 Markdown：{exc}")
            return None
