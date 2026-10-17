"""Native-rate Rally test clips, independent of court/people annotation approval."""

from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path

import curate


def manifest(root: Path) -> Path:
    return root / "manifests/rally-samples.json"


def command(arguments: list[str], log: Path, timeout: int = 600) -> str:
    """Bound retries/time; preserve useful errors without printing signed media URLs."""
    try:
        result = subprocess.run(arguments, capture_output=True, text=True, timeout=timeout)
    except subprocess.TimeoutExpired as exc:
        log.write_text(f"Timed out after {timeout}s\n", encoding="utf-8")
        raise curate.CurateError(f"operation timed out; see {log}") from exc
    log.write_text(result.stderr, encoding="utf-8")
    if result.returncode:
        raise curate.CurateError(f"operation failed ({result.returncode}); see {log}")
    return result.stdout


def inspect(clip: Path, directory: Path) -> dict:
    import imageio_ffmpeg

    reader = imageio_ffmpeg.read_frames(str(clip))
    try:
        metadata = next(reader)
    finally:
        reader.close()
    # Decode every source frame. Scene scores flag possible cuts; they are not
    # proof of a fixed camera. Visual review is recorded separately below.
    output = command([
        curate.find_ffmpeg(), "-hide_banner", "-nostdin", "-v", "info",
        "-xerror", "-i", str(clip), "-map", "0:v:0", "-an",
        "-vf", "scale=320:-2,select='gt(scene,0.25)',showinfo",
        "-vsync", "0", "-f", "null", "-", "-progress", "pipe:1",
    ], directory / "decode.log")
    stderr = (directory / "decode.log").read_text(encoding="utf-8")
    cuts = [float(value) for value in re.findall(r"pts_time:([\d.]+)", stderr)]
    duration = float(metadata["duration"])
    width, height = metadata["source_size"]
    fps = float(metadata["fps"])
    # 36 thumbnails cover a three-minute clip at five-second spacing; originals
    # retain their native frame rate. Suspected cuts need closer inspection.
    command([
        curate.find_ffmpeg(), "-hide_banner", "-nostdin", "-v", "error",
        "-i", str(clip), "-an", "-vf",
        "fps=1/5,scale=320:-2,tile=6x6", "-frames:v", "1", "-y",
        str(directory / "contact.jpg"),
    ], directory / "contact.log")
    return {
        "width": width, "height": height, "fps": fps, "duration_s": duration,
        "decode_complete": "progress=end" in output,
        "suspected_cut_times_s": cuts,
        "contact_sheet": str(directory / "contact.jpg"),
        "sha256": curate.sha256(clip), "bytes": clip.stat().st_size,
    }


def sample(args) -> None:
    root = curate.dataset_root(args)
    start, end = curate.parse_range(args.window)
    if not 60 <= end - start <= 300:
        raise curate.CurateError("Rally test windows must be 60–300 seconds")
    if not re.fullmatch(r"[A-Za-z0-9_-]+", args.sample_id):
        raise curate.CurateError("sample-id must use letters, digits, underscores or hyphens")
    platform, video_id, url = curate.normalize_url(args.url)
    source_id = f"{platform}:{video_id}"
    for known in curate.load_sources(root)["sources"]:
        if known["source_id"] == source_id and known.get("status") == "rejected":
            raise curate.CurateError("source has a durable human rejection; choose another source")
    directory = root / "local/rally" / args.sample_id
    directory.mkdir(parents=True, exist_ok=True)
    record_path = directory / "sample.json"
    if record_path.exists():
        cached = curate.read_json(record_path, {})
        if (cached.get("source_id"), cached.get("window_s")) != (source_id, [start, end]):
            raise curate.CurateError("sample-id already belongs to another source/window")
        if cached.get("status") != "failed" and curate.sha256(directory / "clip.mp4") == cached["media"]["sha256"]:
            print(json.dumps(cached, ensure_ascii=False))
            return
        raise curate.CurateError("cached failed or changed sample; inspect logs and use a new sample-id")
    record = {
        "sample_id": args.sample_id, "source_id": source_id, "url": url,
        "group": args.group, "view_id": args.view_id, "window_s": [start, end],
        "match_type": args.match_type,
        "device_evidence": args.device_evidence, "status": "pending",
        "created_at": curate.utc_now(), "annotation_status": "unlabelled",
    }
    try:
        if args.input:
            raw = curate.bounded_captures({}, args.input, [(start, end)], directory)[0]
            record["title"] = Path(args.input).name
        else:
            common = curate.yt_dlp_command() + [
                "--ignore-config", "--no-playlist", "--socket-timeout", "15",
                "--retries", "0", "--fragment-retries", "0", "--no-warnings",
                "--ffmpeg-location", curate.find_ffmpeg(),
            ]
            if platform == "bilibili":
                common += ["--impersonate", "chrome"]
            metadata = curate.read_json(Path(args.metadata), {}) if args.metadata else json.loads(command(common + ["--skip-download", "--dump-single-json", url], directory / "metadata.log", 60))
            if not isinstance(metadata, dict):
                raise curate.CurateError("source metadata unavailable; see metadata.log")
            resolved_id = str(metadata.get("id"))
            # Bilibili names the first part of a multi-part source BVID_p1.
            expected_ids = {video_id, f"{video_id}_p1"} if platform == "bilibili" else {video_id}
            if platform in ("youtube", "bilibili") and resolved_id not in expected_ids:
                raise curate.CurateError("resolved metadata belongs to a different video")
            record.update({key: metadata.get(key) for key in ("title", "uploader", "channel", "duration", "description")})
            if metadata.get("duration") and end > float(metadata["duration"]) + 1:
                raise curate.CurateError("requested window exceeds source duration")
            # Resolve once: a second extractor call can hit a different public
            # CDN/API response. Use the returned public formats, not cookies.
            info_path = directory / "source-info.json"
            curate.write_json(info_path, metadata)
            command(common + [
                "--no-part", "--download-sections", f"*{start}-{end}",
                "--force-keyframes-at-cuts", "--load-info-json", str(info_path), "-S", "vcodec:h264", "-f",
                "bv*[height<=1080][fps>=24]/bv*[height<=1080]/b[height<=1080]",
                "-o", str(directory / "raw.%(ext)s"),
            ], directory / "download.log")
            info_path.unlink()
            matches = [path for path in directory.glob("raw.*") if path.is_file()]
            if len(matches) != 1:
                raise curate.CurateError("expected exactly one bounded media file")
            raw = matches[0]
        clip = directory / "clip.mp4"
        # Remux only: no scaling, fps conversion, interpolation or audio. The
        # downloaded/decoded native frames are the actual algorithm inputs.
        command([
            curate.find_ffmpeg(), "-hide_banner", "-nostdin", "-v", "error",
            "-i", str(raw), "-map", "0:v:0", "-an", "-c:v", "copy",
            "-avoid_negative_ts", "make_zero", "-y", str(clip),
        ], directory / "remux.log")
        record["media"] = inspect(clip, directory)
        media = record["media"]
        if media["fps"] < 24 or media["duration_s"] < (end - start) - 1 or not media["decode_complete"]:
            raise curate.CurateError("native fps, duration or complete-decode check failed")
        record["status"] = "needs_visual_review"
        raw.unlink()
    except (curate.CurateError, OSError, json.JSONDecodeError) as exc:
        record.update(status="failed", error=str(exc))
        raise
    finally:
        curate.write_json(record_path, record)
        index = curate.read_json(manifest(root), {"schema_version": 1, "samples": []})
        index["samples"] = [item for item in index["samples"] if item["sample_id"] != args.sample_id] + [record]
        curate.write_json(manifest(root), index)
    print(json.dumps(record, ensure_ascii=False))


def review(args) -> None:
    root = curate.dataset_root(args)
    index = curate.read_json(manifest(root), {"schema_version": 1, "samples": []})
    item = next((sample for sample in index["samples"] if sample["sample_id"] == args.sample_id), None)
    if not item or item["status"] == "failed":
        raise curate.CurateError("sample has not passed media validation")
    clip = root / "local/rally" / args.sample_id / "clip.mp4"
    if curate.sha256(clip) != item["media"]["sha256"]:
        raise curate.CurateError("media changed after validation")
    if args.phone_confirmed and item["device_evidence"] == "unknown":
        raise curate.CurateError("phone confirmation requires source evidence")
    item.update(status=args.decision, suitability_review={
        "reviewer": args.reviewer, "reason": args.reason, "at": curate.utc_now(),
        "phone_confirmed": args.phone_confirmed,
        "note": "clip suitability only; not rally labels or court-geometry verification",
    })
    curate.write_json(root / "local/rally" / args.sample_id / "sample.json", item)
    curate.write_json(manifest(root), index)
    status(args)


def status(args) -> None:
    samples = curate.read_json(manifest(curate.dataset_root(args)), {"samples": []})["samples"]
    accepted = [item for item in samples if item["status"] == "accepted" and item.get("match_type") == "singles"]
    official = {item["view_id"] for item in accepted if item["group"] == "official"}
    personal = {item["view_id"] for item in accepted if item["group"] == "personal"}
    phone = {item["view_id"] for item in accepted if item["group"] == "personal" and item["suitability_review"]["phone_confirmed"]}
    print(json.dumps({
        "samples": len(samples), "accepted_clips": len(accepted),
        "official_views": len(official), "personal_views": len(personal), "confirmed_phone_views": len(phone),
        "target_met": len(official) >= 6 and len(phone) >= 6,
        "statuses": {value: sum(item["status"] == value for item in samples) for value in ("accepted", "rejected", "failed", "needs_visual_review")},
    }, ensure_ascii=False, indent=2))
