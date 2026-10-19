#!/usr/bin/env python3
"""Small authenticated tus 1.0 receiver. Python 3.9+, optional FFmpeg for HLS."""

import argparse
import base64
import hashlib
import hmac
import json
import os
from pathlib import Path
import re
import secrets
import shutil
import socket
import sqlite3
import subprocess
import threading
import time
from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlsplit
from uuid import UUID, uuid4

MAX_SIZE = 32 * 1024 * 1024
MAX_DURATION_US = 6_000_000
VERSION = "1.0.0"
FIELDS = {"session", "sequence", "startUs", "endUs", "captureEpochMs", "sha256", "final"}
UPLOAD_PATH = re.compile(r"/files/([0-9a-f]{32})(/raw\.mp4)?")
SESSION_PATH = re.compile(r"/sessions/([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})/(segments|segments\.jsonl|index\.m3u8)")
TS_PATH = re.compile(r"/hls/([0-9a-f]{32})\.ts")


def now_ms():
    return time.time_ns() // 1_000_000


def sync_dir(path):
    fd = os.open(path, os.O_RDONLY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def uint(value, name):
    if not re.fullmatch(r"[0-9]{1,18}", value or ""):
        raise RequestError(400, f"invalid {name}")
    return int(value)


class RequestError(Exception):
    def __init__(self, status, message):
        self.status, self.message = status, message


def metadata(header):
    if not header or len(header) > 4096:
        raise RequestError(400, "missing or oversized Upload-Metadata")
    result = {}
    try:
        for item in header.split(","):
            key, encoded = item.strip().split(" ", 1)
            if key in result or key not in FIELDS:
                raise ValueError("duplicate or unknown metadata")
            result[key] = base64.b64decode(encoded, validate=True).decode("utf-8")
        if result.keys() != FIELDS:
            raise ValueError("metadata fields")
        if str(UUID(result["session"])) != result["session"]:
            raise ValueError("canonical UUID required")
        for key in ("sequence", "startUs", "endUs", "captureEpochMs"):
            result[key] = uint(result[key], key)
        if not 0 < result["endUs"] - result["startUs"] <= MAX_DURATION_US:
            raise ValueError("segment video duration must be in (0, 6 seconds]")
        if result["sequence"] > 1_000_000 or result["endUs"] > 31 * 86400 * 1_000_000:
            raise ValueError("session exceeds 31 days or 1000001 segments")
        if result["sequence"] == 0 and result["startUs"] != 0:
            raise ValueError("sequence 0 must start at source time 0")
        if not re.fullmatch(r"[0-9a-f]{64}", result["sha256"]):
            raise ValueError("sha256 must be lowercase hex")
        if result["final"] not in ("true", "false"):
            raise ValueError("final must be true/false")
        result["final"] = result["final"] == "true"
    except (ValueError, UnicodeError) as error:
        raise RequestError(400, f"invalid metadata: {error}") from error
    return result


class Store:
    def __init__(self, root, ffmpeg=None):
        self.root = Path(root).resolve()
        for name in ("raw", "hls", "analysis"):
            (self.root / name).mkdir(parents=True, exist_ok=True)
        self.ffmpeg = ffmpeg
        self.lock = threading.RLock()
        self.upload_locks = {}
        self.db = sqlite3.connect(self.root / "state.sqlite3", check_same_thread=False)
        self.db.row_factory = sqlite3.Row
        self.db.execute("PRAGMA journal_mode=WAL")
        self.db.execute("PRAGMA synchronous=FULL")
        self.db.execute("""CREATE TABLE IF NOT EXISTS uploads (
            id TEXT PRIMARY KEY, session TEXT NOT NULL, sequence INTEGER NOT NULL,
            start_us INTEGER NOT NULL, end_us INTEGER NOT NULL, epoch_ms INTEGER NOT NULL,
            sha256 TEXT NOT NULL, final INTEGER NOT NULL, length INTEGER NOT NULL,
            offset INTEGER NOT NULL DEFAULT 0, complete INTEGER NOT NULL DEFAULT 0,
            received_ms INTEGER, ts_ready INTEGER NOT NULL DEFAULT 0, error TEXT,
            UNIQUE(session, sequence))""")
        self.db.commit()
        # File length is authoritative after an interrupted fsync -> DB commit window.
        for row in self.rows():
            path = self.raw(row["id"])
            actual = path.stat().st_size if path.exists() else 0
            if actual > row["length"]:
                raise RuntimeError(f"oversized persisted upload: {row['id']}")
            if row["complete"] and (actual != row["length"] or self.digest(path) != row["sha256"]):
                raise RuntimeError(f"verified upload missing or corrupt: {row['id']}")
            self.db.execute("UPDATE uploads SET offset=?, ts_ready=? WHERE id=?",
                            (actual, int(bool(row["ts_ready"] and self.ts(row["id"]).exists())), row["id"]))
            if actual == row["length"] and not row["complete"]:
                try:
                    self.verify(row["id"])
                except RequestError as error:
                    if error.status != 460:
                        raise
        self.db.commit()
        for session in {row["session"] for row in self.rows()}:
            self.write_index(session)
        self.stop_event = threading.Event()
        self.work_event = threading.Event()
        self.worker = threading.Thread(target=self.work_loop, name="hls-remux", daemon=True)
        self.worker.start()

    def raw(self, upload_id):
        return self.root / "raw" / f"{upload_id}.mp4"

    def ts(self, upload_id):
        return self.root / "hls" / f"{upload_id}.ts"

    @staticmethod
    def digest(path):
        sha = hashlib.sha256()
        with path.open("rb") as stream:
            for chunk in iter(lambda: stream.read(256 * 1024), b""):
                sha.update(chunk)
        return sha.hexdigest()

    def rows(self, session=None):
        with self.lock:
            if session is None:
                return self.db.execute("SELECT * FROM uploads ORDER BY session, sequence").fetchall()
            return self.db.execute("SELECT * FROM uploads WHERE session=? ORDER BY sequence", (session,)).fetchall()

    def get(self, upload_id):
        with self.lock:
            row = self.db.execute("SELECT * FROM uploads WHERE id=?", (upload_id,)).fetchone()
            if row is None:
                raise RequestError(404, "unknown upload")
            return row

    def upload_lock(self, upload_id):
        with self.lock:
            return self.upload_locks.setdefault(upload_id, threading.Lock())

    def create(self, meta, length):
        if not 0 < length <= MAX_SIZE:
            raise RequestError(413 if length > MAX_SIZE else 400, "segment length must be 1..33554432")
        values = (meta["session"], meta["sequence"], meta["startUs"], meta["endUs"],
                  meta["captureEpochMs"], meta["sha256"], int(meta["final"]), length)
        with self.lock:
            rows = self.rows(meta["session"])
            existing = next((row for row in rows if row["sequence"] == meta["sequence"]), None)
            if existing:
                old = tuple(existing[k] for k in ("session", "sequence", "start_us", "end_us", "epoch_ms", "sha256", "final", "length"))
                if old != values:
                    raise RequestError(409, "session/sequence already has different content or metadata")
                return existing["id"]
            for row in rows:
                if row["epoch_ms"] != meta["captureEpochMs"]:
                    raise RequestError(409, "captureEpochMs changed within session")
                if (row["final"] and row["sequence"] < meta["sequence"]) or (meta["final"] and row["sequence"] > meta["sequence"]):
                    raise RequestError(409, "segment follows final segment")
                if row["sequence"] < meta["sequence"] and row["end_us"] > meta["startUs"]:
                    raise RequestError(409, "source intervals overlap or reverse")
                if row["sequence"] > meta["sequence"] and row["start_us"] < meta["endUs"]:
                    raise RequestError(409, "source intervals overlap or reverse")
                if row["sequence"] + 1 == meta["sequence"] and row["end_us"] != meta["startUs"]:
                    raise RequestError(409, "adjacent source intervals must be continuous")
                if row["sequence"] - 1 == meta["sequence"] and row["start_us"] != meta["endUs"]:
                    raise RequestError(409, "adjacent source intervals must be continuous")
            upload_id = uuid4().hex
            # Create before committing metadata; orphan zero-byte files are harmless.
            with self.raw(upload_id).open("xb") as stream:
                stream.flush()
                os.fsync(stream.fileno())
            sync_dir(self.root / "raw")
            self.db.execute("""INSERT INTO uploads
                (id,session,sequence,start_us,end_us,epoch_ms,sha256,final,length)
                VALUES (?,?,?,?,?,?,?,?,?)""", (upload_id, *values))
            self.db.commit()
            return upload_id

    def append(self, upload_id, offset, length, stream):
        with self.upload_lock(upload_id):
            row = self.get(upload_id)
            if offset != row["offset"]:
                raise RequestError(409, f"offset mismatch: expected {row['offset']}")
            if offset + length > row["length"]:
                raise RequestError(413, "PATCH exceeds declared upload length")
            left = length
            disconnected = False
            with self.raw(upload_id).open("r+b", buffering=0) as target:
                target.seek(offset)
                while left:
                    try:
                        # read1 returns received bytes without waiting to fill a large buffer.
                        chunk = stream.read1(min(left, 64 * 1024))
                    except (OSError, TimeoutError):
                        disconnected = True
                        break
                    if not chunk:
                        disconnected = True
                        break
                    target.write(chunk)
                    os.fsync(target.fileno())
                    offset += len(chunk)
                    left -= len(chunk)
                    with self.lock:
                        self.db.execute("UPDATE uploads SET offset=? WHERE id=?", (offset, upload_id))
                        self.db.commit()
            if offset == row["length"] and not row["complete"]:
                self.verify(upload_id)
            if disconnected:
                raise RequestError(400, "body interrupted; HEAD returns durable offset")
            return offset

    def verify(self, upload_id):
        row = self.get(upload_id)
        if self.digest(self.raw(upload_id)) != row["sha256"]:
            with self.raw(upload_id).open("wb") as stream:
                os.fsync(stream.fileno())
            with self.lock:
                self.db.execute("UPDATE uploads SET offset=0,error='SHA256 mismatch' WHERE id=?", (upload_id,))
                self.db.commit()
            raise RequestError(460, "SHA256 mismatch; upload reset to offset 0")
        with self.lock:
            self.db.execute("UPDATE uploads SET complete=1,received_ms=?,error=NULL WHERE id=?", (now_ms(), upload_id))
            self.db.commit()
            self.write_index(row["session"])
        if hasattr(self, "work_event"):
            self.work_event.set()

    def contiguous(self, session, hls=False):
        result = []
        for row in self.rows(session):
            if row["sequence"] != len(result) or not row["complete"] or (hls and not row["ts_ready"]):
                break
            result.append(row)
        return result

    def segment(self, row):
        return {"sequence": row["sequence"], "startUs": row["start_us"], "endUs": row["end_us"],
                "captureEpochMs": row["epoch_ms"], "sha256": row["sha256"], "final": bool(row["final"]),
                "receivedAtMs": row["received_ms"],
                "latencyMs": row["received_ms"] - row["epoch_ms"] - row["end_us"] / 1000,
                "rawPath": str(self.raw(row["id"])), "rawUrl": f"/files/{row['id']}/raw.mp4"}

    def analysis(self, session):
        rows = self.contiguous(session)
        if not self.rows(session):
            raise RequestError(404, "unknown session")
        return {"session": session, "complete": bool(rows and rows[-1]["final"]),
                "latencyNote": "receivedAtMs - (phone captureEpochMs + endUs/1000); includes phone/server clock skew",
                "segments": [self.segment(row) for row in rows]}

    def write_index(self, session):
        path = self.root / "analysis" / f"{session}.jsonl"
        temp = path.with_suffix(".tmp")
        with temp.open("w", encoding="utf-8") as stream:
            for row in self.contiguous(session):
                stream.write(json.dumps(self.segment(row), ensure_ascii=False) + "\n")
            stream.flush()
            os.fsync(stream.fileno())
        temp.replace(path)
        sync_dir(path.parent)

    def sessions(self):
        with self.lock:
            result = []
            for session in sorted({row["session"] for row in self.rows()}):
                rows = self.rows(session)
                prefix = self.contiguous(session)
                hls = self.contiguous(session, hls=True)
                result.append({"session": session, "uploads": len(rows),
                               "verified": sum(row["complete"] for row in rows),
                               "contiguous": len(prefix), "hlsSegments": len(hls),
                               "complete": bool(prefix and prefix[-1]["final"]),
                               "latestLatencyMs": self.segment(prefix[-1])["latencyMs"] if prefix else None,
                               "hlsUrl": f"/sessions/{session}/index.m3u8",
                               "errors": [{"sequence": r["sequence"], "message": r["error"]} for r in rows if r["error"]]})
            return result

    def playlist(self, session):
        if not self.rows(session):
            raise RequestError(404, "unknown session")
        rows = self.contiguous(session, hls=True)
        if not rows:
            raise RequestError(503, "HLS waiting for verified sequence 0 and successful FFmpeg remux")
        durations = [(r["end_us"] - r["start_us"]) / 1_000_000 for r in rows]
        lines = ["#EXTM3U", "#EXT-X-VERSION:3", f"#EXT-X-TARGETDURATION:{MAX_DURATION_US // 1_000_000}",
                 "#EXT-X-MEDIA-SEQUENCE:0", "#EXT-X-PLAYLIST-TYPE:EVENT"]
        for row, duration in zip(rows, durations):
            lines.extend(["#EXT-X-DISCONTINUITY", f"#EXTINF:{duration:.6f},", f"/hls/{row['id']}.ts"])
        if rows[-1]["final"]:
            lines.append("#EXT-X-ENDLIST")
        return "\n".join(lines) + "\n"

    def remux(self, row):
        if not self.ffmpeg:
            return
        temp = self.ts(row["id"]).with_suffix(".tmp")
        try:
            subprocess.run([self.ffmpeg, "-nostdin", "-hide_banner", "-loglevel", "error", "-y",
                            "-copyts", "-i", str(self.raw(row["id"])), "-map", "0:v:0", "-map", "0:a:0",
                            "-c", "copy", "-bsf:v", "h264_mp4toannexb", "-avoid_negative_ts", "disabled",
                            "-mpegts_copyts", "1", "-output_ts_offset", f"{row['start_us'] / 1_000_000:.6f}",
                            "-mpegts_flags", "+resend_headers", "-muxdelay", "0", "-muxpreload", "0",
                            "-f", "mpegts", str(temp)], check=True, capture_output=True, timeout=60)
            if temp.stat().st_size == 0:
                raise RuntimeError("FFmpeg produced empty transport stream")
            with temp.open("rb") as stream:
                os.fsync(stream.fileno())
            temp.replace(self.ts(row["id"]))
            sync_dir(self.root / "hls")
            with self.lock:
                self.db.execute("UPDATE uploads SET ts_ready=1,error=NULL WHERE id=?", (row["id"],))
                self.db.commit()
        except (OSError, subprocess.SubprocessError, RuntimeError) as error:
            detail = error.stderr.decode("utf-8", "replace")[-1000:] if isinstance(error, subprocess.CalledProcessError) else str(error)
            with self.lock:
                self.db.execute("UPDATE uploads SET error=? WHERE id=?", (f"HLS: {detail}", row["id"]))
                self.db.commit()
        finally:
            temp.unlink(missing_ok=True)

    def work_loop(self):
        while not self.stop_event.is_set():
            for row in self.rows():
                if self.stop_event.is_set():
                    return
                if row["complete"] and not row["ts_ready"]:
                    self.remux(row)
            self.work_event.wait(5)
            self.work_event.clear()

    def close(self):
        self.stop_event.set()
        self.work_event.set()
        self.worker.join(65)
        with self.lock:
            self.db.close()


HOME = '''<!doctype html><html lang="zh"><meta charset="utf-8"><meta name="viewport" content="width=device-width">
<title>Capture receiver</title><style>body{font:16px system-ui;max-width:900px;margin:40px auto;padding:0 20px}input{width:24em}pre{white-space:pre-wrap}video{width:100%}</style>
<h1>场边视频接收端</h1><p>输入令牌登录，浏览器会保存 12 小时的 HttpOnly 会话凭据。</p>
<input id="token" type="password" placeholder="Bearer token"><button id="load">登录 / 刷新会话</button><pre id="state"></pre><div id="links"></div>
<p>时延包含手机与服务端时钟差。原生播放需要浏览器支持 HLS（如 Safari）；其他播放器须携带 Bearer 令牌。无在线播放器依赖。</p>
<script>document.getElementById('load').onclick=async()=>{try{let t=document.getElementById('token');if(t.value){let a=await fetch('/auth',{method:'POST',headers:{Authorization:'Bearer '+t.value}});if(!a.ok)throw new Error('登录失败');t.value='';}let r=await fetch('/sessions');let data=await r.json();document.getElementById('state').textContent=JSON.stringify(data,null,2);let box=document.getElementById('links');box.replaceChildren();if(Array.isArray(data))for(let s of data){let p=document.createElement('p');p.textContent=s.session;let a=document.createElement('a');a.href=s.hlsUrl;a.textContent=' HLS 播放列表';let v=document.createElement('video');v.controls=true;v.preload='none';v.src=s.hlsUrl;box.append(p,a,v);}}catch(e){document.getElementById('state').textContent=e.message;}};</script></html>'''.encode("utf-8")


class Server(ThreadingHTTPServer):
    daemon_threads = False
    block_on_close = True

    def __init__(self, address, store, token):
        if not token:
            raise ValueError("token must not be empty")
        self.store, self.token = store, token
        super().__init__(address, Handler)


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def setup(self):
        super().setup()
        self.connection.settimeout(30)

    @property
    def store(self):
        return self.server.store

    def reply(self, status, data=b"", headers=None, content_type="application/json"):
        self.send_response(status)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Content-Type", content_type)
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        if self.path.startswith("/files"):
            self.send_header("Tus-Resumable", VERSION)
        for key, value in (headers or {}).items():
            self.send_header(key, str(value))
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(data)

    def json(self, status, data, headers=None):
        self.reply(status, json.dumps(data, ensure_ascii=False).encode(), headers)

    def checked(self, callback):
        try:
            callback()
        except RequestError as error:
            # Do not interpret an unconsumed PATCH body as another HTTP request.
            self.close_connection = True
            self.json(error.status, {"error": error.message}, {"Connection": "close"})
        except (BrokenPipeError, ConnectionResetError, socket.timeout):
            self.close_connection = True

    def authorize(self, cookie=False):
        supplied = self.headers.get("Authorization", "")
        if hmac.compare_digest(supplied.encode(), ("Bearer " + self.server.token).encode()):
            return
        if cookie:
            cookies = SimpleCookie()
            try:
                cookies.load(self.headers.get("Cookie", ""))
                value = cookies["capture_session"].value
                expiry, nonce, signature = value.split(".")
                expected = hmac.new(self.server.token.encode(), f"{expiry}.{nonce}".encode(), "sha256").hexdigest()
                if int(expiry) > time.time() and hmac.compare_digest(signature, expected):
                    return
            except (KeyError, ValueError):
                pass
        raise RequestError(401, "Bearer token required")

    def tus(self):
        self.authorize()
        if self.headers.get("Tus-Resumable") != VERSION:
            self.reply(412, headers={"Tus-Version": VERSION, "Connection": "close"})
            self.close_connection = True
            return False
        if self.headers.get("Transfer-Encoding"):
            raise RequestError(400, "use Content-Length, not Transfer-Encoding")
        return True

    def route(self):
        parsed = urlsplit(self.path)
        if parsed.query or parsed.fragment or "%" in parsed.path or ".." in parsed.path:
            raise RequestError(400, "invalid URL path")
        return parsed.path

    def upload_id(self):
        match = UPLOAD_PATH.fullmatch(self.route())
        if not match or match[2]:
            raise RequestError(404, "unknown upload URL")
        return match[1]

    def do_OPTIONS(self):
        self.checked(self.options)

    def options(self):
        self.authorize()
        if not self.route().startswith("/files"):
            raise RequestError(404, "unknown route")
        self.reply(204, headers={"Tus-Version": VERSION, "Tus-Extension": "creation", "Tus-Max-Size": MAX_SIZE})

    def do_POST(self):
        self.checked(self.post)

    def post(self):
        if self.route() == "/auth":
            self.authorize()
            if self.headers.get("Transfer-Encoding") or uint(self.headers.get("Content-Length", "0"), "Content-Length"):
                raise RequestError(400, "login body must be empty")
            value = f"{int(time.time()) + 43200}.{secrets.token_hex(12)}"
            signature = hmac.new(self.server.token.encode(), value.encode(), "sha256").hexdigest()
            secure = "; Secure" if self.headers.get("X-Forwarded-Proto") == "https" else ""
            self.json(200, {"authenticated": True},
                      {"Set-Cookie": f"capture_session={value}.{signature}; Path=/; HttpOnly; SameSite=Strict; Max-Age=43200{secure}"})
            return
        # tus requires honoring X-HTTP-Method-Override for constrained clients.
        override = self.headers.get("X-HTTP-Method-Override")
        if override == "PATCH":
            return self.patch()
        if override is not None:
            raise RequestError(405, "unsupported method override")
        if not self.tus():
            return
        if self.route() != "/files":
            raise RequestError(404, "unknown route")
        if uint(self.headers.get("Content-Length", "0"), "Content-Length") != 0:
            raise RequestError(400, "creation-with-upload is not supported")
        upload_id = self.store.create(metadata(self.headers.get("Upload-Metadata")),
                                      uint(self.headers.get("Upload-Length"), "Upload-Length"))
        self.reply(201, headers={"Location": f"/files/{upload_id}"})

    def do_HEAD(self):
        self.checked(self.head)

    def head(self):
        if not self.tus():
            return
        upload_id = self.upload_id()
        with self.store.upload_lock(upload_id):
            row = self.store.get(upload_id)
            self.reply(200, headers={"Upload-Offset": row["offset"], "Upload-Length": row["length"]})

    def do_PATCH(self):
        self.checked(self.patch)

    def patch(self):
        if not self.tus():
            return
        if self.headers.get("Content-Type") != "application/offset+octet-stream":
            raise RequestError(415, "Content-Type must be application/offset+octet-stream")
        offset = self.store.append(self.upload_id(), uint(self.headers.get("Upload-Offset"), "Upload-Offset"),
                                   uint(self.headers.get("Content-Length"), "Content-Length"), self.rfile)
        self.reply(204, headers={"Upload-Offset": offset})

    def do_GET(self):
        self.checked(self.get)

    def file(self, path, content_type):
        if not path.is_file():
            raise RequestError(404, "file not ready")
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(path.stat().st_size))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        with path.open("rb") as stream:
            shutil.copyfileobj(stream, self.wfile, 256 * 1024)

    def get(self):
        path = self.route()
        if path == "/":
            self.reply(200, HOME, content_type="text/html; charset=utf-8")
            return
        if path == "/health":
            self.json(200, {"status": "ok", "tus": VERSION, "hlsEnabled": bool(self.store.ffmpeg), "serverEpochMs": now_ms()})
            return
        self.authorize(cookie=True)
        if path == "/sessions":
            self.json(200, self.store.sessions())
            return
        match = UPLOAD_PATH.fullmatch(path)
        if match:
            row = self.store.get(match[1])
            if match[2]:
                if not row["complete"]:
                    raise RequestError(409, "upload not verified")
                self.file(self.store.raw(row["id"]), "video/mp4")
            else:
                self.json(200, {"complete": bool(row["complete"]), "sha256": row["sha256"],
                                "offset": row["offset"], "length": row["length"], "error": row["error"],
                                "receivedAtMs": row["received_ms"], "session": row["session"], "sequence": row["sequence"]})
            return
        match = SESSION_PATH.fullmatch(path)
        if match:
            session, resource = match.groups()
            if str(UUID(session)) != session:
                raise RequestError(400, "invalid session UUID")
            if resource == "segments":
                self.json(200, self.store.analysis(session))
            elif resource == "segments.jsonl":
                self.store.analysis(session)
                self.file(self.store.root / "analysis" / f"{session}.jsonl", "application/x-ndjson")
            else:
                self.reply(200, self.store.playlist(session).encode(), content_type="application/vnd.apple.mpegurl")
            return
        match = TS_PATH.fullmatch(path)
        if match:
            if not self.store.get(match[1])["ts_ready"]:
                raise RequestError(404, "HLS segment not ready")
            self.file(self.store.ts(match[1]), "video/mp2t")
            return
        raise RequestError(404, "unknown route")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8787)
    parser.add_argument("--data", type=Path, default=Path(".runtime/receiver"))
    parser.add_argument("--token", default=os.environ.get("CAPTURE_TOKEN"))
    parser.add_argument("--ffmpeg", default=shutil.which("ffmpeg"), help="FFmpeg executable; HLS disabled if absent")
    args = parser.parse_args()
    token = args.token or secrets.token_urlsafe(24)
    if not args.token:
        print(f"Generated token (set CAPTURE_TOKEN to reuse): {token}", flush=True)
    if len(token) < 16:
        parser.error("token must be at least 16 characters")
    if args.ffmpeg and not (Path(args.ffmpeg).is_file() or shutil.which(args.ffmpeg)):
        parser.error("FFmpeg executable not found")
    store = Store(args.data, args.ffmpeg)
    server = Server((args.host, args.port), store, token)
    print(f"Receiver: http://{args.host}:{server.server_port} | data: {store.root} | HLS: {bool(args.ffmpeg)}", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
        store.close()


if __name__ == "__main__":
    main()
