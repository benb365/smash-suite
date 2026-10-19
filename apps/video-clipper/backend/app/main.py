from __future__ import annotations

import asyncio
import secrets
from contextlib import asynccontextmanager
from pathlib import Path
from urllib.parse import unquote

from fastapi import FastAPI, HTTPException, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from modules.media.video import thumbnail
from app.input_policy import probe
from app.product_types import ProcessRequest
from app.runtime import Runtime, web_dir
from app.sessions import Sessions


def create_app(home: Path | None = None, *, lease_s: float = 60, frontend: Path | None = None):
    @asynccontextmanager
    async def lifespan(app):
        runtime = Runtime(home)
        app.state.sessions = Sessions(runtime, lease_s)
        sweeper = asyncio.create_task(app.state.sessions.sweep())
        try:
            yield
        finally:
            sweeper.cancel()
            await asyncio.gather(sweeper, return_exceptions=True)
            for session in list(app.state.sessions.items.values()):
                await app.state.sessions.close(session)
            runtime.close()

    app = FastAPI(title="Smash Suite", version="0.2.0", lifespan=lifespan,
                  docs_url=None, redoc_url=None, openapi_url=None)

    @app.middleware("http")
    async def local_only(request: Request, call_next):
        if request.url.hostname not in ("localhost", "127.0.0.1", "testserver"):
            return JSONResponse({"detail": "只允许本机访问。"}, status_code=403)
        origin = request.headers.get("origin")
        if origin and origin != f"{request.url.scheme}://{request.headers.get('host')}":
            return JSONResponse({"detail": "拒绝跨站请求。"}, status_code=403)
        response = await call_next(request)
        if request.url.path.startswith(("/api/", "/media/")):
            response.headers["Cache-Control"] = "no-store"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "no-referrer"
        return response

    def owner(request: Request, sid: str):
        token = request.headers.get("authorization", "").removeprefix("Bearer ")
        session = request.app.state.sessions.authenticated(sid, token)
        if not session:
            raise HTTPException(404, "页面会话已过期，请重新导入录像。")
        return session

    @app.get("/api/health")
    async def health():
        return {"status": "ok", "version": "0.2.0"}

    @app.post("/api/sessions", status_code=201)
    async def create_session(request: Request):
        session = request.app.state.sessions.create()
        return {"id": session.id, "token": session.token, "state": session.public()}

    @app.get("/api/sessions/{sid}")
    async def state(sid: str, request: Request):
        return owner(request, sid).public()

    @app.delete("/api/sessions/{sid}", status_code=204)
    async def close(sid: str, request: Request):
        await request.app.state.sessions.close(owner(request, sid))

    @app.post("/api/sessions/{sid}/video")
    async def upload(sid: str, request: Request):
        session = owner(request, sid)
        if session.state.status in ("running", "uploading"):
            raise HTTPException(409, "请先完成或取消当前操作。")
        name = Path(unquote(request.headers.get("x-file-name", "video.mp4"))).name[:200]
        if not name.lower().endswith(".mp4"):
            raise HTTPException(415, "请选择 MP4 文件。")
        session.upload_task = asyncio.current_task()
        temporary = session.directory / "upload.part"
        try:
            await request.app.state.sessions.publish(session, status="uploading", stage="正在导入录像", error=None,
                                                     output_url=None, output_bytes=None, elapsed_s=None, timings=None)
            with temporary.open("wb") as stream:
                async for chunk in request.stream():
                    if session.closed:
                        raise HTTPException(410, "页面会话已过期。")
                    stream.write(chunk)
            with temporary.open("rb") as stream:
                if stream.read(8)[4:] != b"ftyp":
                    raise ValueError("文件不是有效的 MP4。")
            info = await asyncio.to_thread(probe, temporary, name)
            await asyncio.to_thread(thumbnail, temporary, session.directory / "frame.jpg")
            temporary.replace(session.directory / "source.mp4")
            for old in ("output.mp4", "result.json"):
                (session.directory / old).unlink(missing_ok=True)
            session.media_key = secrets.token_urlsafe(32)
            await request.app.state.sessions.publish(session, status="ready", stage="录像已就绪，选择拍摄类型后开始",
                                                     progress=0, video=info, error=None, rally_count=0)
        except asyncio.CancelledError:
            raise HTTPException(409, "录像导入已取消。") from None
        except HTTPException:
            raise
        except Exception as exc:
            await request.app.state.sessions.publish(session, status="failed", stage="录像导入失败", error=str(exc), video=None)
            raise HTTPException(400, str(exc)) from exc
        finally:
            temporary.unlink(missing_ok=True)
            if session.upload_task is asyncio.current_task():
                session.upload_task = None
        return session.public()

    @app.get("/api/sessions/{sid}/frame.jpg")
    async def first_frame(sid: str, request: Request):
        session = owner(request, sid)
        path = session.directory / "frame.jpg"
        if not path.is_file():
            raise HTTPException(404, "请先导入录像。")
        return FileResponse(path, media_type="image/jpeg")

    @app.post("/api/sessions/{sid}/run", status_code=202)
    async def run(sid: str, options: ProcessRequest, request: Request):
        session = owner(request, sid)
        try:
            await request.app.state.sessions.start(session, options)
        except ValueError as exc:
            raise HTTPException(409, str(exc)) from exc
        return session.public()

    @app.post("/api/sessions/{sid}/cancel")
    async def cancel(sid: str, request: Request):
        session = owner(request, sid)
        await request.app.state.sessions.cancel(session)
        return session.public()

    @app.get("/api/sessions/{sid}/output.mp4")
    async def download(sid: str, request: Request):
        session = owner(request, sid)
        if session.state.status != "completed":
            raise HTTPException(409, "成片尚未生成。")
        return FileResponse(session.directory / "output.mp4", media_type="video/mp4")

    @app.get("/media/{key}/output.mp4")
    async def preview(key: str, request: Request):
        # A video element cannot attach Authorization. This random capability
        # grants access only to one completed output until its session expires.
        session = next((s for s in request.app.state.sessions.items.values()
                        if secrets.compare_digest(s.media_key, key) and not s.closed), None)
        if not session or session.state.status != "completed":
            raise HTTPException(404, "成片已过期。")
        return FileResponse(session.directory / "output.mp4", media_type="video/mp4")

    @app.websocket("/ws/sessions/{sid}")
    async def connection(websocket: WebSocket, sid: str):
        origin = websocket.headers.get("origin")
        if origin and origin not in (f"http://{websocket.headers.get('host')}", f"https://{websocket.headers.get('host')}"):
            await websocket.close(code=1008)
            return
        await websocket.accept()
        session = None
        try:
            hello = await asyncio.wait_for(websocket.receive_json(), timeout=5)
            sessions = websocket.app.state.sessions
            session = sessions.authenticated(sid, hello.get("token", ""))
            if not session:
                await websocket.close(code=4404)
                return
            if session.socket:
                await websocket.close(code=4409)
                return
            session.socket = websocket
            sessions.renew(session)
            await websocket.send_json(session.public())
            while True:
                await asyncio.wait_for(websocket.receive_text(), timeout=30)
                sessions.renew(session)
                await websocket.send_json(session.public())
        except (WebSocketDisconnect, asyncio.TimeoutError, ValueError):
            pass
        finally:
            if session and session.socket is websocket:
                session.socket = None
                websocket.app.state.sessions.renew(session)

    static = frontend or web_dir()
    if static.is_dir():
        app.mount("/", StaticFiles(directory=static, html=True), name="web")
    return app


app = create_app()
