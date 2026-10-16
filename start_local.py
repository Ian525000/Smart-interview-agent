"""启动独立的本地网页服务；关闭启动窗口不会结束后台服务。"""

import argparse
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import time
from datetime import datetime
from urllib.request import ProxyHandler, build_opener
import webbrowser


PROJECT_DIR = Path(__file__).resolve().parent
LOCAL_HTTP = build_opener(ProxyHandler({}))


def service_ready(url: str) -> bool:
    try:
        with LOCAL_HTTP.open(f"{url}/api/health", timeout=1) as response:
            data = json.load(response)
        return isinstance(data, dict) and data.get("service") == "interview-agent" and data.get("status") == "ok"
    except (OSError, ValueError):
        return False


def port_in_use(port: int) -> bool:
    try:
        with socket.create_connection(("127.0.0.1", port), timeout=1):
            return True
    except OSError:
        return False


def python_executable() -> str:
    for folder in (".venv", "venv"):
        candidate = PROJECT_DIR / folder / "Scripts" / "python.exe"
        if candidate.is_file():
            return str(candidate)
    return sys.executable


def start(open_browser: bool = True) -> str:
    python = python_executable()
    config = subprocess.run(
        [python, "-c", "from config import SERVER_PORT; print(SERVER_PORT)"],
        cwd=PROJECT_DIR,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=15,
    )
    if config.returncode:
        raise RuntimeError("无法读取配置。请先安装 requirements.txt 中的依赖。\n" + config.stderr.strip())
    port = int(config.stdout.strip())
    if not 1 <= port <= 65535:
        raise RuntimeError("SERVER_PORT 必须在 1 到 65535 之间。")
    url = f"http://localhost:{port}"
    probe_url = f"http://127.0.0.1:{port}"

    if not service_ready(probe_url):
        if port_in_use(port):
            raise RuntimeError(f"端口 {port} 已被占用，且未返回本项目的健康标记。请检查占用情况；启动器不会结束其他服务。")

        log_dir = PROJECT_DIR / "data" / "logs"
        log_dir.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S-%f")
        out_path = log_dir / f"web-{stamp}.out.log"
        err_path = log_dir / f"web-{stamp}.err.log"
        environment = os.environ.copy()
        environment["PYTHONUNBUFFERED"] = "1"
        environment["PYTHONIOENCODING"] = "utf-8"
        options = {}
        if os.name == "nt":
            options["creationflags"] = subprocess.CREATE_NO_WINDOW | subprocess.CREATE_NEW_PROCESS_GROUP
        else:
            options["start_new_session"] = True

        with out_path.open("ab") as output, err_path.open("ab") as error:
            process = subprocess.Popen(
                [python, "-u", "-m", "uvicorn", "main:app", "--host", "127.0.0.1", "--port", str(port)],
                cwd=PROJECT_DIR,
                stdin=subprocess.DEVNULL,
                stdout=output,
                stderr=error,
                env=environment,
                close_fds=True,
                **options,
            )
        deadline = time.monotonic() + 30
        while time.monotonic() < deadline:
            if service_ready(probe_url):
                break
            if process.poll() is not None:
                raise RuntimeError(f"服务启动失败，错误日志：{err_path}")
            time.sleep(0.3)
        else:
            raise RuntimeError(f"服务尚未就绪，请检查日志：{err_path}")

    print(f"面试网页已就绪：{url}")
    print("服务在后台独立运行，关闭此窗口后仍可访问。电脑重启后请再次运行启动器。")
    if open_browser:
        webbrowser.open(url)
    return url


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    parser = argparse.ArgumentParser(description="启动智能面试 Agent 本地网页")
    parser.add_argument("--no-browser", action="store_true", help="只启动后台服务，不打开默认浏览器")
    args = parser.parse_args()
    try:
        start(open_browser=not args.no_browser)
    except (OSError, ValueError, RuntimeError, subprocess.TimeoutExpired) as exc:
        print(f"启动失败：{exc}", file=sys.stderr)
        sys.exit(1)
