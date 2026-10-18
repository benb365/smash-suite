"""Run: python3 -m unittest discover -s receiver -v (from android-capture)."""

import base64
import hashlib
import http.client
import json
import os
from pathlib import Path
import shutil
import socket
import subprocess
import tempfile
import threading
import time
import unittest
from uuid import uuid4

from server import MAX_SIZE, Server, Store

TOKEN = "receiver-test-token-0123456789"
REPO_FFMPEG = Path(__file__).resolve().parents[3] / ".agents/skills/curate-badminton-training-data/.venv/lib/python3.12/site-packages/imageio_ffmpeg/binaries/ffmpeg-macos-aarch64-v7.1"
FFMPEG = os.environ.get("FFMPEG") or shutil.which("ffmpeg") or (str(REPO_FFMPEG) if REPO_FFMPEG.is_file() else None)


class ReceiverTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.session = str(uuid4())
        self.store = Store(self.temp.name)
        self.start_server()

    def start_server(self):
        self.server = Server(("127.0.0.1", 0), self.store, TOKEN)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.port = self.server.server_port

    def stop_server(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join()

    def tearDown(self):
        self.stop_server()
        self.store.close()
        self.temp.cleanup()

    def request(self, method, path, body=None, headers=None, auth=True):
        connection = http.client.HTTPConnection("127.0.0.1", self.port, timeout=10)
        common = {"Connection": "close", "Tus-Resumable": "1.0.0"}
        if auth:
            common["Authorization"] = "Bearer " + TOKEN
        common.update(headers or {})
        connection.request(method, path, body, common)
        response = connection.getresponse()
        result = response.status, dict(response.getheaders()), response.read()
        connection.close()
        return result

    def meta(self, content, sequence=0, final=False, **changes):
        meta = {"session": self.session, "sequence": str(sequence), "startUs": str(sequence * 2_000_000),
                "endUs": str((sequence + 1) * 2_000_000), "captureEpochMs": "1700000000000",
                "sha256": hashlib.sha256(content).hexdigest(), "final": str(final).lower()}
        meta.update(changes)
        return ",".join(key + " " + base64.b64encode(str(value).encode()).decode() for key, value in meta.items())

    def create(self, content, **changes):
        status, headers, body = self.request("POST", "/files", headers={"Upload-Length": str(len(content)),
                                                            "Upload-Metadata": self.meta(content, **changes)})
        self.assertEqual(201, status, body)
        return headers["Location"]

    def patch(self, url, data, offset=0):
        return self.request("PATCH", url, data, {"Upload-Offset": str(offset), "Content-Type": "application/offset+octet-stream"})

    def upload(self, content, **changes):
        url = self.create(content, **changes)
        status, headers, body = self.patch(url, content)
        self.assertEqual(204, status, body)
        self.assertEqual(str(len(content)), headers["Upload-Offset"])
        return url

    def test_auth_version_and_validation(self):
        self.assertEqual(200, self.request("GET", "/health", auth=False)[0])
        self.assertEqual(401, self.request("GET", "/sessions", auth=False)[0])
        self.assertEqual(401, self.request("POST", "/files", auth=False)[0])
        status, headers, _ = self.request("OPTIONS", "/files", headers={"Tus-Resumable": "invalid"})
        self.assertEqual(204, status)
        self.assertEqual("creation", headers["Tus-Extension"])
        self.assertEqual(str(MAX_SIZE), headers["Tus-Max-Size"])
        status, headers, _ = self.request("POST", "/files", headers={"Tus-Resumable": "0.2.0"})
        self.assertEqual(412, status)
        self.assertEqual("1.0.0", headers["Tus-Version"])
        for changes in ({"session": "../../etc/passwd"}, {"sha256": "not-a-hash"}, {"final": "yes"},
                        {"endUs": "0"}, {"endUs": "6000001"}, {"sequence": -1}, {"startUs": "1"}):
            self.assertEqual(400, self.request("POST", "/files", headers={"Upload-Length": "10", "Upload-Metadata": self.meta(b"x", **changes)})[0])
        self.assertEqual(413, self.request("POST", "/files", headers={"Upload-Length": str(MAX_SIZE + 1), "Upload-Metadata": self.meta(b"x")})[0])
        self.assertEqual(400, self.request("GET", "/sessions/%2e%2e/segments")[0])
        self.assertEqual(400, self.request("GET", "/hls/../../etc/passwd")[0])

    def test_resume_offsets_hash_and_restart(self):
        content = b"video-and-audio-payload" * 100
        url = self.create(content, final=True)
        self.assertEqual(204, self.patch(url, content[:123])[0])
        self.assertEqual(409, self.patch(url, b"wrong", offset=0)[0])
        self.assertEqual("123", self.request("HEAD", url)[1]["Upload-Offset"])
        self.assertEqual(413, self.patch(url, content, offset=123)[0])
        self.assertFalse(json.loads(self.request("GET", url)[2])["complete"])
        self.assertEqual(409, self.request("GET", url + "/raw.mp4")[0])
        self.stop_server()
        self.store.close()
        self.store = Store(self.temp.name)
        self.start_server()
        self.assertEqual("123", self.request("HEAD", url)[1]["Upload-Offset"])
        self.assertEqual(204, self.patch(url, content[123:], offset=123)[0])
        confirmation = json.loads(self.request("GET", url)[2])
        self.assertTrue(confirmation["complete"])
        self.assertEqual(hashlib.sha256(content).hexdigest(), confirmation["sha256"])
        self.assertEqual(content, self.request("GET", url + "/raw.mp4")[2])
        self.stop_server()
        self.store.close()
        self.store = Store(self.temp.name)
        self.start_server()
        self.assertTrue(json.loads(self.request("GET", url)[2])["complete"])
        self.assertEqual(content, self.request("GET", url + "/raw.mp4")[2])

    def test_socket_disconnect_retains_received_bytes(self):
        content = b"v" * 100000
        url = self.create(content)
        sock = socket.create_connection(("127.0.0.1", self.port))
        sock.sendall((f"PATCH {url} HTTP/1.1\r\nHost: localhost\r\nAuthorization: Bearer {TOKEN}\r\n"
                      f"Tus-Resumable: 1.0.0\r\nUpload-Offset: 0\r\nContent-Length: {len(content)}\r\n"
                      "Content-Type: application/offset+octet-stream\r\nConnection: close\r\n\r\n").encode() + content[:17321])
        sock.shutdown(socket.SHUT_WR)
        while sock.recv(4096):
            pass
        sock.close()
        self.assertEqual("17321", self.request("HEAD", url)[1]["Upload-Offset"])
        self.assertEqual(204, self.patch(url, content[17321:], 17321)[0])
        self.assertTrue(json.loads(self.request("GET", url)[2])["complete"])

    def test_hash_mismatch_resets_without_confirmation(self):
        url = self.create(b"correct", final=True)
        self.assertEqual(460, self.patch(url, b"corrupt")[0])
        status, headers, _ = self.request("HEAD", url)
        self.assertEqual(200, status)
        self.assertEqual("0", headers["Upload-Offset"])
        self.assertFalse(json.loads(self.request("GET", url)[2])["complete"])
        self.assertEqual(204, self.patch(url, b"correct")[0])
        self.assertTrue(json.loads(self.request("GET", url)[2])["complete"])

    def test_idempotent_creation_and_contiguous_analysis(self):
        last = self.upload(b"second", sequence=1, final=True)
        self.assertEqual(last, self.create(b"second", sequence=1, final=True))
        self.assertEqual([], json.loads(self.request("GET", f"/sessions/{self.session}/segments")[2])["segments"])
        self.assertEqual(409, self.request("POST", "/files", headers={"Upload-Length": "6", "Upload-Metadata": self.meta(b"abcdef", sequence=1, final=True)})[0])
        self.assertEqual(409, self.request("POST", "/files", headers={"Upload-Length": "3", "Upload-Metadata": self.meta(b"abc", sequence=2)})[0])
        self.upload(b"first", sequence=0)
        data = json.loads(self.request("GET", f"/sessions/{self.session}/segments")[2])
        self.assertEqual([0, 1], [s["sequence"] for s in data["segments"]])
        self.assertTrue(data["complete"])
        self.assertIn("clock skew", data["latencyNote"])
        lines = self.request("GET", f"/sessions/{self.session}/segments.jsonl")[2].splitlines()
        self.assertEqual([0, 1], [json.loads(line)["sequence"] for line in lines])
        self.assertEqual(2, json.loads(self.request("GET", "/sessions")[2])[0]["contiguous"])
        self.assertEqual(503, self.request("GET", f"/sessions/{self.session}/index.m3u8")[0])

    def test_file_offset_recovers_commit_window(self):
        url = self.create(b"complete")
        # Emulate process death after durable file write but before SQLite offset commit.
        with self.store.raw(url.rsplit("/", 1)[1]).open("wb") as stream:
            stream.write(b"complete")
            stream.flush()
            os.fsync(stream.fileno())
        self.stop_server()
        self.store.close()
        self.store = Store(self.temp.name)
        self.start_server()
        self.assertEqual("8", self.request("HEAD", url)[1]["Upload-Offset"])
        self.assertTrue(json.loads(self.request("GET", url)[2])["complete"])

    def test_browser_cookie_does_not_authorize_uploads(self):
        self.assertEqual(401, self.request("POST", "/auth", auth=False)[0])
        status, headers, _ = self.request("POST", "/auth", headers={"X-Forwarded-Proto": "https"})
        self.assertEqual(200, status)
        self.assertIn("HttpOnly", headers["Set-Cookie"])
        self.assertIn("SameSite=Strict", headers["Set-Cookie"])
        self.assertIn("Secure", headers["Set-Cookie"])
        cookie = headers["Set-Cookie"].split(";", 1)[0]
        self.assertEqual(200, self.request("GET", "/sessions", headers={"Cookie": cookie}, auth=False)[0])
        self.assertEqual(401, self.request("POST", "/files", headers={"Cookie": cookie}, auth=False)[0])
        self.assertEqual(401, self.request("GET", "/sessions", headers={"Cookie": cookie + "bad"}, auth=False)[0])

    @unittest.skipUnless(FFMPEG, "set FFMPEG to a real FFmpeg executable")
    def test_real_continuous_audio_video_hls_and_remux_retry(self):
        fixture = Path(self.temp.name) / "fixture"
        fixture.mkdir()
        subprocess.run([FFMPEG, "-nostdin", "-hide_banner", "-loglevel", "error", "-y",
                        "-f", "lavfi", "-i", "testsrc2=size=160x90:rate=30",
                        "-f", "lavfi", "-i", "sine=frequency=440:sample_rate=48000",
                        "-t", "4", "-c:v", "libx264", "-preset", "ultrafast", "-bf", "0", "-g", "60",
                        "-keyint_min", "60", "-sc_threshold", "0", "-c:a", "aac", "-b:a", "96k",
                        "-avoid_negative_ts", "disabled", "-f", "segment", "-segment_time", "2",
                        "-reset_timestamps", "1", str(fixture / "%d.mp4")],
                       check=True, capture_output=True)
        pieces = sorted(fixture.glob("*.mp4"))
        self.assertEqual(2, len(pieces))
        urls = [self.upload(piece.read_bytes(), sequence=i, final=i == 1) for i, piece in enumerate(pieces)]
        # Analysis confirmation is already available without waiting for HLS.
        self.assertTrue(json.loads(self.request("GET", f"/sessions/{self.session}/segments")[2])["complete"])
        self.store.ffmpeg = "/does/not/exist"
        self.store.remux(self.store.get(urls[0].split("/")[-1]))
        self.assertFalse(self.store.get(urls[0].split("/")[-1])["ts_ready"])
        self.assertEqual(503, self.request("GET", f"/sessions/{self.session}/index.m3u8")[0])
        self.store.ffmpeg = FFMPEG
        self.store.work_event.set()
        deadline = time.monotonic() + 15
        while time.monotonic() < deadline and len(self.store.contiguous(self.session, hls=True)) != 2:
            time.sleep(0.05)
        self.assertEqual(2, len(self.store.contiguous(self.session, hls=True)))
        status, _, playlist = self.request("GET", f"/sessions/{self.session}/index.m3u8")
        self.assertEqual(200, status)
        self.assertIn(b"#EXT-X-TARGETDURATION:6", playlist)
        self.assertEqual(2, playlist.count(b"#EXT-X-DISCONTINUITY"))
        self.assertIn(b"#EXT-X-ENDLIST", playlist)
        # Decode both real streams through the authenticated HTTP HLS endpoint.
        decoded = subprocess.run([FFMPEG, "-nostdin", "-hide_banner", "-loglevel", "error",
                                  "-headers", f"Authorization: Bearer {TOKEN}\r\n",
                                  "-i", f"http://127.0.0.1:{self.port}/sessions/{self.session}/index.m3u8",
                                  "-map", "0:v:0", "-map", "0:a:0", "-f", "null", "-"],
                                 capture_output=True, timeout=20)
        self.assertEqual(0, decoded.returncode, decoded.stderr.decode())
        def packet_times(path, stream):
            crc = subprocess.run([FFMPEG, "-nostdin", "-hide_banner", "-loglevel", "error", "-copyts",
                                  "-i", str(path), "-map", stream, "-c", "copy", "-f", "framecrc", "-"],
                                 capture_output=True, check=True).stdout.decode()
            timebase_line = next(line for line in crc.splitlines() if line.startswith("#tb 0:"))
            numerator, denominator = map(int, timebase_line.split(":", 1)[1].strip().split("/"))
            packets = [line.split(",") for line in crc.splitlines() if line and not line.startswith("#")]
            return [(int(packet[2]) * numerator / denominator, int(packet[3]) * numerator / denominator) for packet in packets]

        # Both tracks retain their original intra-segment PTS plus source offset;
        # no duration of the MP4 container is accumulated across segment boundaries.
        audio_segments = []
        for i, (url, original) in enumerate(zip(urls, pieces)):
            ts = self.store.ts(url.split("/")[-1])
            for stream in ("0:v:0", "0:a:0"):
                raw_packets = packet_times(original, stream)
                ts_packets = packet_times(ts, stream)
                self.assertEqual(len(raw_packets), len(ts_packets))
                for (raw_pts, _), (ts_pts, _) in zip(raw_packets, ts_packets):
                    self.assertAlmostEqual(raw_pts + i * 2, ts_pts, delta=0.0001)
                if stream == "0:a:0":
                    audio_segments.append(ts_packets)
        # MP4 edit-list timestamps can round to its millisecond movie timescale.
        self.assertAlmostEqual(audio_segments[0][-1][0] + audio_segments[0][-1][1], audio_segments[1][0][0], delta=0.001)
        # HLS survives store reconstruction; verified originals are untouched.
        self.stop_server()
        self.store.close()
        self.store = Store(self.temp.name, FFMPEG)
        self.start_server()
        self.assertEqual(2, len(self.store.contiguous(self.session, hls=True)))
        self.assertIn(b"#EXT-X-ENDLIST", self.request("GET", f"/sessions/{self.session}/index.m3u8")[2])


if __name__ == "__main__":
    unittest.main()
