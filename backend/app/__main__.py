from __future__ import annotations

import argparse
import socket
import sys
import threading
import webbrowser


def main():
    if len(sys.argv) > 1 and sys.argv[1] == "--worker":
        from app.worker import main as worker
        return worker(sys.argv[2])
    parser = argparse.ArgumentParser(description="Smash Suite 本机羽毛球录像剪辑")
    parser.add_argument("--port", type=int, default=18780)
    parser.add_argument("--no-browser", action="store_true")
    args = parser.parse_args()
    import uvicorn
    from app.main import app
    from app.runtime import web_dir
    if not web_dir().is_dir():
        parser.error("缺少网页资源；开发时请先构建 frontend，安装版请重新安装。")
    with socket.socket() as listener:
        listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            listener.bind(("127.0.0.1", args.port))
        except OSError:
            parser.error("端口已被使用，可用 --port 0 自动选择空闲端口。")
        listener.listen(128)
        url = f"http://127.0.0.1:{listener.getsockname()[1]}/"
        print(f"Smash Suite: {url}\n请使用 Chrome 或 Edge。关闭本程序会清理临时录像，已保存的成片保留。", flush=True)
        if not args.no_browser:
            opener = threading.Timer(1, webbrowser.open, args=(url,))
            opener.daemon = True
            opener.start()
        try:
            uvicorn.Server(uvicorn.Config(app, log_level="warning", access_log=False)).run(sockets=[listener])
        except KeyboardInterrupt:
            # Uvicorn re-raises SIGINT after its graceful cleanup.
            return 0


if __name__ == "__main__":
    raise SystemExit(main())
