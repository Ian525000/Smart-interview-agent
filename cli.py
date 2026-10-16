"""CLI 文字模式入口。"""

import argparse
import sys
from pathlib import Path

from services.interview_service import InterviewService


def run_cli(jd_path: str, resume_path: str, mock: bool = False, template_id: str = None) -> None:
    """
    运行文字版面试全流程。

    @param jd_path - JD 文件路径
    @param resume_path - 简历文件路径
    @param mock - Mock 模式
    @param template_id - 模板 ID
    """
    service = InterviewService()
    jd_text = service.parse_file_path(jd_path)
    resume_text = service.parse_file_path(resume_path)

    print("\n=== 智能面试 Agent（文字模式）===\n")
    print("正在解析 JD 与简历，生成面试题...")

    session = service.create_session_from_text(
        jd_text, resume_text, mode="text", template_id=template_id, mock_mode=mock
    )

    print(f"\n会话 ID: {session.session_id}")
    print(f"候选人: {session.resume_profile.name if session.resume_profile else '未知'}")
    print(f"岗位: {session.jd_profile.title if session.jd_profile else '产品岗'}")
    print("\n--- 生成的 10 道面试题 ---")
    for i, q in enumerate(session.questions, 1):
        mark = " [可追问]" if q.id in session.follow_up_targets else ""
        print(f"{i}. [{q.type.value}]{mark} {q.text}")

    confirm = input("\n确认开始面试？(y/n，输入 edit 可编辑某题): ").strip().lower()
    if confirm == "edit":
        idx = int(input("输入要编辑的题号 (1-10): ")) - 1
        new_text = input("输入新问题: ").strip()
        if 0 <= idx < len(session.questions):
            session.questions[idx].text = new_text
            service.update_questions(session.session_id, session.questions)
    elif confirm != "y":
        print("已取消。")
        return

    result = service.lock_questions_and_start(session.session_id)
    while not result.get("done") and result.get("action") != "complete":
        print(f"\n面试官: {result.get('agent_text', '')}")
        answer = input("你的回答 (输入 skip 跳过, retry 重答): ").strip()
        skip = answer.lower() == "skip"
        retry = answer.lower() == "retry"
        if not skip and not retry and not answer:
            print("回答不能为空。")
            continue
        result = service.submit_answer(
            session.session_id,
            answer if not skip and not retry else "",
            skip=skip,
            retry=retry,
        )

    print("\n=== 面试完成，正在生成报告 ===")
    if result.get("scoring"):
        scoring = result["scoring"]
        print(f"Markdown 报告: {scoring.get('markdown')}")
        if scoring.get("pdf"):
            print(f"PDF 报告: {scoring.get('pdf')}")
        if scoring.get("summary"):
            s = scoring["summary"]
            print(f"\n总评: {s.get('recommendation')}")
            print(f"平均分: {s.get('average_score'):.1f}")


def main() -> None:
    """CLI 入口。"""
    parser = argparse.ArgumentParser(description="智能面试 Agent CLI")
    parser.add_argument("--jd", required=True, help="JD 文件路径")
    parser.add_argument("--resume", required=True, help="简历文件路径")
    parser.add_argument("--mock", action="store_true", help="Mock 练习模式")
    parser.add_argument("--template", default=None, help="岗位模板 ID")
    args = parser.parse_args()

    if not Path(args.jd).exists():
        print(f"JD 文件不存在: {args.jd}")
        sys.exit(1)
    if not Path(args.resume).exists():
        print(f"简历文件不存在: {args.resume}")
        sys.exit(1)

    run_cli(args.jd, args.resume, mock=args.mock, template_id=args.template)


if __name__ == "__main__":
    main()
