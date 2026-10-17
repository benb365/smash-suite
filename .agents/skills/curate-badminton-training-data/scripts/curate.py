#!/usr/bin/env python3
"""Curate bounded badminton court-geometry and court-conditioned people data."""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import math
import os
import re
import shutil
import subprocess
import sys
import tempfile
import urllib.parse
import zipfile
from pathlib import Path
from typing import Any


SCHEMA_VERSION = 2
CACHE_DAYS = 30
PREVIEW_FAILURE_DAYS = 7
SEARCH_PURPOSES = ("court", "people")
CAPTURE_CONTEXTS = ("campus", "club", "personal", "broadcast", "other")
COMPETITION_LEVELS = ("amateur", "professional", "unknown")
COURT_SCENES = (
    "court_complete",
    "court_partial",
    "view_negative",
    "court_partial_unresolved",
)
PEOPLE_SCENES = ("clean", "adjacent_court", "extra_people", "occlusion_or_exit")
COURT_PROPOSAL_DECISIONS = ("accepted", "needs_review", "rejected")
PIPELINE_PILOT_VIEWS = 10
PIPELINE_PILOT_NON_BROADCAST_VIEWS = 8
INITIAL_BASELINE_VIEWS = 30
INITIAL_BASELINE_NON_BROADCAST_VIEWS = 24
INITIAL_BASELINE_SPLIT_GROUPS = 12
CHALLENGE_VIEWS_PER_SCENE = 5

# Singles court coordinates in metres: x left-to-right, y far-to-near.
COURT_WIDTH_M = 5.18
COURT_LENGTH_M = 13.40
NET_Y_M = COURT_LENGTH_M / 2
SHORT_SERVICE_OFFSET_M = 1.98
COURT_CONTROL_POINTS: dict[str, tuple[float, float]] = {
    "far_left_baseline": (0.0, 0.0),
    "far_center_baseline": (COURT_WIDTH_M / 2, 0.0),
    "far_right_baseline": (COURT_WIDTH_M, 0.0),
    "far_left_short_service": (0.0, NET_Y_M - SHORT_SERVICE_OFFSET_M),
    "far_center_short_service": (COURT_WIDTH_M / 2, NET_Y_M - SHORT_SERVICE_OFFSET_M),
    "far_right_short_service": (COURT_WIDTH_M, NET_Y_M - SHORT_SERVICE_OFFSET_M),
    "net_left": (0.0, NET_Y_M),
    "net_right": (COURT_WIDTH_M, NET_Y_M),
    "near_left_short_service": (0.0, NET_Y_M + SHORT_SERVICE_OFFSET_M),
    "near_center_short_service": (COURT_WIDTH_M / 2, NET_Y_M + SHORT_SERVICE_OFFSET_M),
    "near_right_short_service": (COURT_WIDTH_M, NET_Y_M + SHORT_SERVICE_OFFSET_M),
    "near_left_baseline": (0.0, COURT_LENGTH_M),
    "near_center_baseline": (COURT_WIDTH_M / 2, COURT_LENGTH_M),
    "near_right_baseline": (COURT_WIDTH_M, COURT_LENGTH_M),
}
CANONICAL_POINT_IDS = (
    "far_left_baseline",
    "far_right_baseline",
    "net_left",
    "net_right",
    "near_left_baseline",
    "near_right_baseline",
)
COURT_TEMPLATE_SEGMENTS = (
    ("far_left_baseline", "far_right_baseline"),
    ("near_left_baseline", "near_right_baseline"),
    ("far_left_baseline", "near_left_baseline"),
    ("far_right_baseline", "near_right_baseline"),
    ("net_left", "net_right"),
    ("far_left_short_service", "far_right_short_service"),
    ("near_left_short_service", "near_right_short_service"),
    ("far_center_baseline", "far_center_short_service"),
    ("near_center_short_service", "near_center_baseline"),
)


class CurateError(RuntimeError):
    pass


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat()


def repo_root() -> Path:
    return Path(__file__).resolve().parents[4]


def dataset_root(args: argparse.Namespace) -> Path:
    return Path(args.dataset_root).resolve() if args.dataset_root else repo_root() / "datasets/badminton-v1"


def paths(root: Path) -> dict[str, Path]:
    return {
        "sources": root / "manifests/sources.json",
        "cache": root / "manifests/search-cache.json",
        "splits": root / "manifests/splits.json",
        "local": root / "local",
        "annotations": root / "annotations",
    }


def read_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("w", encoding="utf-8", newline="\n") as handle:
        json.dump(value, handle, ensure_ascii=False, indent=2, sort_keys=True)
        handle.write("\n")
    os.replace(temporary, path)


def load_sources(root: Path) -> dict[str, Any]:
    document = read_json(paths(root)["sources"], {"schema_version": SCHEMA_VERSION, "sources": []})
    if document.get("schema_version") != SCHEMA_VERSION:
        raise CurateError(
            f"sources schema must be v{SCHEMA_VERSION}; migrate the tracked manifest before running the skill"
        )
    return document


def source_by_id(document: dict[str, Any], source_id: str) -> dict[str, Any]:
    for source in document["sources"]:
        if source["source_id"] == source_id:
            return source
    raise CurateError(f"unknown source_id: {source_id}")


def safe_key(value: str) -> str:
    return re.sub(r"[^0-9A-Za-z._-]+", "_", value).strip("_")


def normalize_query(query: str) -> str:
    return " ".join(query.casefold().split())


def search_key(purpose: str, query: str) -> str:
    return f"{purpose}:{normalize_query(query)}"


def normalize_url(value: str) -> tuple[str, str, str]:
    raw = value.strip()
    parsed = urllib.parse.urlsplit(raw if "://" in raw else "https://" + raw)
    if parsed.scheme == "file":
        local_path = Path(urllib.parse.unquote(parsed.path)).resolve()
        video_id = hashlib.sha256(str(local_path).encode()).hexdigest()[:16]
        return "local", video_id, local_path.as_uri()
    host = parsed.netloc.casefold().removeprefix("www.")
    query = urllib.parse.parse_qs(parsed.query)
    if host in {"bilibili.com", "m.bilibili.com"}:
        match = re.search(r"/video/(BV[0-9A-Za-z]+)", parsed.path, re.I)
        if not match:
            raise CurateError(f"missing Bilibili BV id: {value}")
        video_id = match.group(1)
        return "bilibili", video_id, f"https://www.bilibili.com/video/{video_id}/"
    if host in {"youtube.com", "m.youtube.com"} and query.get("v"):
        video_id = query["v"][0]
        return "youtube", video_id, f"https://www.youtube.com/watch?v={video_id}"
    if host == "youtu.be":
        video_id = parsed.path.strip("/").split("/")[0]
        return "youtube", video_id, f"https://www.youtube.com/watch?v={video_id}"
    if host == "zenodo.org":
        match = re.search(r"/records?/(\d+)", parsed.path)
        if not match:
            raise CurateError(f"missing Zenodo record id: {value}")
        video_id = match.group(1)
        return "zenodo", video_id, f"https://zenodo.org/records/{video_id}"
    clean = urllib.parse.urlunsplit((parsed.scheme or "https", host, parsed.path.rstrip("/"), "", ""))
    video_id = hashlib.sha256(clean.encode()).hexdigest()[:16]
    return host or "web", video_id, clean


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def sha256_export(path: Path) -> str:
    if path.is_file():
        return sha256(path)
    digest = hashlib.sha256()
    for item in sorted(candidate for candidate in path.rglob("*") if candidate.is_file()):
        digest.update(item.relative_to(path).as_posix().encode())
        digest.update(b"\0")
        digest.update(sha256(item).encode())
        digest.update(b"\0")
    return digest.hexdigest()


def parse_range(text: str) -> tuple[float, float]:
    try:
        start_text, end_text = text.split(":", 1)
        start, end = float(start_text), float(end_text)
    except ValueError as exc:
        raise CurateError(f"invalid time range {text!r}; use START:END seconds") from exc
    if start < 0 or end <= start:
        raise CurateError(f"invalid increasing time range: {text}")
    return start, end


def find_ffmpeg() -> str:
    executable = shutil.which("ffmpeg")
    if executable:
        return executable
    try:
        import imageio_ffmpeg  # type: ignore

        return imageio_ffmpeg.get_ffmpeg_exe()
    except (ImportError, RuntimeError) as exc:
        raise CurateError("FFmpeg not found; install scripts/requirements.txt") from exc


def yt_dlp_command() -> list[str]:
    executable = shutil.which("yt-dlp")
    if executable:
        return [executable]
    try:
        import yt_dlp  # noqa: F401

        return [sys.executable, "-m", "yt_dlp"]
    except ImportError as exc:
        raise CurateError("yt-dlp not found; install scripts/requirements.txt") from exc


def run(command: list[str]) -> None:
    print("+", " ".join(command))
    completed = subprocess.run(command, text=True)
    if completed.returncode:
        raise CurateError(f"command failed with exit code {completed.returncode}")


def yt_dlp_section_command(
    source: dict[str, Any], ranges: list[tuple[float, float]], output_template: Path
) -> list[str]:
    if source["platform"] == "zenodo":
        raise CurateError("Zenodo records are metadata-only; do not bulk-download them")
    command = yt_dlp_command() + [
        "--no-playlist",
        "--no-part",
        "--ffmpeg-location",
        find_ffmpeg(),
        "--force-keyframes-at-cuts",
        "-f",
        "bv*[height<=720]/b[height<=720]",
        "-o",
        str(output_template),
    ]
    for start, end in ranges:
        command += ["--download-sections", f"*{start}-{end}"]
    if source["platform"] == "bilibili":
        command += ["--impersonate", "chrome"]
    command.append(source["canonical_url"])
    return command


def bounded_captures(
    source: dict[str, Any],
    input_path: str | None,
    ranges: list[tuple[float, float]],
    output_dir: Path,
) -> list[Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    outputs = [output_dir / f"raw-{index}.mp4" for index in range(1, len(ranges) + 1)]
    if input_path:
        for (start, end), output in zip(ranges, outputs):
            run(
                [
                    find_ffmpeg(),
                    "-hide_banner",
                    "-loglevel",
                    "error",
                    "-ss",
                    str(start),
                    "-i",
                    input_path,
                    "-t",
                    str(end - start),
                    "-map",
                    "0:v:0",
                    "-an",
                    "-c:v",
                    "libx264",
                    "-preset",
                    "ultrafast",
                    "-pix_fmt",
                    "yuv420p",
                    "-y",
                    str(output),
                ]
            )
        return outputs
    template = output_dir / "section-%(section_start)012.3f.%(ext)s"
    run(yt_dlp_section_command(source, ranges, template))
    for (start, _), output in zip(ranges, outputs):
        matches = sorted(output_dir.glob(f"section-{start:012.3f}.*"))
        if len(matches) != 1:
            raise CurateError(
                f"bounded download did not create exactly one file for section starting at {start}"
            )
        matches[0].replace(output)
    return outputs


def transcode(
    source: Path,
    output: Path,
    fps: int,
    height: int,
    bitrate: str,
    duration_s: float | None = None,
) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    filters = [f"scale=-2:'min({height},ih)'", f"fps={fps}"]
    command = [
        find_ffmpeg(),
        "-hide_banner",
        "-loglevel",
        "error",
        "-i",
        str(source),
        "-an",
        "-vf",
        ",".join(filters),
    ]
    if duration_s is not None:
        command += ["-t", f"{duration_s:.3f}"]
    command += [
        "-r",
        str(fps),
        "-fps_mode",
        "cfr",
        "-c:v",
        "libx264",
        "-preset",
        "fast",
        "-b:v",
        bitrate,
        "-maxrate",
        bitrate,
        "-bufsize",
        "2000k",
        "-pix_fmt",
        "yuv420p",
        "-movflags",
        "+faststart",
        "-y",
        str(output),
    ]
    run(command)


def extract_frame(source: Path, second: float, output: Path, scale: int | None = None) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    command = [
        find_ffmpeg(),
        "-hide_banner",
        "-loglevel",
        "error",
        "-ss",
        f"{second:.3f}",
        "-i",
        str(source),
        "-frames:v",
        "1",
    ]
    if scale:
        command += ["-vf", f"scale={scale}:-2"]
    command += ["-q:v", "2", "-strict", "unofficial", "-y", str(output)]
    run(command)
    if not output.exists() or output.stat().st_size == 0:
        raise CurateError(f"frame extraction produced no data: {output}")


def inspect_media(source: dict[str, Any], input_path: str | None) -> dict[str, Any]:
    if input_path:
        try:
            import imageio_ffmpeg  # type: ignore
        except ImportError as exc:
            raise CurateError("imageio-ffmpeg is required to inspect local media") from exc
        reader = imageio_ffmpeg.read_frames(input_path)
        try:
            metadata = next(reader)
        finally:
            reader.close()
        return {
            "duration_s": float(metadata["duration"]),
            "width": int(metadata["source_size"][0]),
            "height": int(metadata["source_size"][1]),
            "inspected_at": utc_now(),
        }
    cached = source.get("media_metadata")
    if cached and cached.get("duration_s"):
        return cached
    try:
        import yt_dlp  # type: ignore
        from yt_dlp.utils import DownloadError  # type: ignore
    except ImportError as exc:
        raise CurateError("yt-dlp not found; run through scripts/run.py") from exc
    options: dict[str, Any] = {
        "quiet": True,
        "no_warnings": True,
        "skip_download": True,
        "noplaylist": True,
    }
    if source["platform"] == "bilibili":
        from yt_dlp.networking.impersonate import ImpersonateTarget  # type: ignore

        options["impersonate"] = ImpersonateTarget.from_str("chrome")
    try:
        with yt_dlp.YoutubeDL(options) as downloader:
            info = downloader.extract_info(source["canonical_url"], download=False)
    except DownloadError as exc:
        raise CurateError(f"source metadata is unavailable: {exc}") from exc
    if info and info.get("entries"):
        info = next((entry for entry in info["entries"] if entry), None)
    if not info or not info.get("duration"):
        raise CurateError("source metadata does not contain a usable duration")
    formats = info.get("formats") or []
    return {
        "duration_s": float(info["duration"]),
        "width": max((item.get("width") or 0 for item in formats), default=info.get("width") or 0),
        "height": max((item.get("height") or 0 for item in formats), default=info.get("height") or 0),
        "inspected_at": utc_now(),
    }


def automatic_preview_windows(duration_s: float) -> list[tuple[float, float]]:
    if duration_s < 1:
        raise CurateError("source is too short to preview")
    if duration_s <= 12:
        return [(0.0, round(duration_s, 3))]
    count = 2 if duration_s <= 30 else 3
    window_s = min(8.0, duration_s / count)
    ratios = (1 / 3, 2 / 3) if count == 2 else (0.2, 0.5, 0.8)
    windows = []
    for ratio in ratios:
        start = min(duration_s - window_s, max(0.0, duration_s * ratio - window_s / 2))
        windows.append((round(start, 3), round(start + window_s, 3)))
    return windows


def artifact(
    root: Path,
    path: Path,
    start: float | None,
    end: float | None,
    sampling: dict[str, Any],
    **metadata: Any,
) -> dict[str, Any]:
    result: dict[str, Any] = {
        "path": path.relative_to(root).as_posix(),
        "sampling": sampling,
        "sha256": sha256(path),
        **metadata,
    }
    if start is not None:
        result["start_s"] = start
    if end is not None:
        result["end_s"] = end
    return result


def append_artifacts(source: dict[str, Any], group: str, items: list[dict[str, Any]]) -> None:
    existing = source.setdefault("artifacts", {}).setdefault(group, [])
    by_path = {item["path"]: item for item in existing}
    by_path.update({item["path"]: item for item in items})
    source["artifacts"][group] = [by_path[key] for key in sorted(by_path)]


def portable_path(path: Path, root: Path) -> str:
    resolved = path.resolve()
    try:
        return resolved.relative_to(root.resolve()).as_posix()
    except ValueError:
        return str(resolved)


def require_accepted(source: dict[str, Any], command: str) -> None:
    if source.get("status") != "accepted":
        raise CurateError(f"{command} requires a human-accepted source")


def cmd_status(args: argparse.Namespace) -> None:
    root = dataset_root(args)
    sources = load_sources(root)["sources"]
    cache = read_json(paths(root)["cache"], {"schema_version": SCHEMA_VERSION, "queries": []})
    now = dt.datetime.now(dt.timezone.utc)
    fresh_queries = []
    for entry in cache.get("queries", []):
        searched_at = dt.datetime.fromisoformat(entry["searched_at"])
        if (now - searched_at).days < CACHE_DAYS:
            fresh_queries.append(
                {
                    "purpose": entry.get("purpose"),
                    "query_key": entry["query_key"],
                    "searched_at": entry["searched_at"],
                    "result_count": len(entry.get("results", [])),
                }
            )
    counts: dict[str, int] = {}
    for source in sources:
        counts[source["status"]] = counts.get(source["status"], 0) + 1
    accepted = [source for source in sources if source.get("status") == "accepted"]
    accepted_views = {source.get("view_id") for source in accepted if source.get("view_id")}
    accepted_non_broadcast = {
        source.get("view_id")
        for source in accepted
        if source.get("view_id") and source.get("capture_context") != "broadcast"
    }
    accepted_contexts = {
        source.get("capture_context")
        for source in accepted
        if source.get("capture_context") not in {None, "broadcast", "other"}
    }
    accepted_split_groups = {
        source.get("split_group_id")
        for source in accepted
        if source.get("split_group_id")
    }
    verified_courts = list((paths(root)["annotations"] / "verified/court").glob("*.json"))
    verified_view_ids = {
        document.get("view_id")
        for document in (read_json(path, {}) for path in verified_courts)
        if document.get("review_status") == "verified" and document.get("view_id")
    }
    verified_sources = [
        source for source in accepted if source.get("view_id") in verified_view_ids
    ]
    verified_views = {source.get("view_id") for source in verified_sources}
    verified_non_broadcast = {
        source.get("view_id")
        for source in verified_sources
        if source.get("capture_context") != "broadcast"
    }
    verified_contexts = {
        source.get("capture_context")
        for source in verified_sources
        if source.get("capture_context") not in {None, "broadcast", "other"}
    }
    verified_split_groups = {
        source.get("split_group_id")
        for source in verified_sources
        if source.get("split_group_id")
    }
    draft_courts = [
        read_json(path, {})
        for path in (paths(root)["annotations"] / "draft/court").glob("*.json")
    ]
    pending = sum(item.get("review_status") == "pending_review" for item in draft_courts)
    unresolved = sum(item.get("scene_state") == "court_partial_unresolved" for item in draft_courts)
    people_documents = [
        read_json(path, {})
        for path in (paths(root)["annotations"] / "verified/people").glob("*.json")
    ]
    people_scenes = {
        scene
        for document in people_documents
        for scene in document.get("scene_types", [])
        if scene in PEOPLE_SCENES
    }
    challenge_scenes = {"adjacent_court", "extra_people", "occlusion_or_exit"}
    challenge_views = {
        scene: {
            document.get("view_id")
            for document in people_documents
            if scene in document.get("scene_types", []) and document.get("view_id")
        }
        for scene in challenge_scenes
    }
    proposal_paths = [
        path
        for path in (paths(root)["annotations"] / "proposed/court").glob("*/*.json")
        if not path.name.endswith(".review.json")
    ]
    proposal_reviews = {
        path.with_suffix(".review.json").as_posix(): read_json(
            path.with_suffix(".review.json"), {}
        )
        for path in proposal_paths
        if path.with_suffix(".review.json").is_file()
    }
    proposal_decisions: dict[str, int] = {"pending": 0}
    uncertain_proposals = 0
    for path in proposal_paths:
        proposal = read_json(path, {})
        uncertain_proposals += int(proposal.get("uncertain_point_count", 0) > 0)
        review = proposal_reviews.get(path.with_suffix(".review.json").as_posix())
        decision = review.get("decision") if review else "pending"
        proposal_decisions[decision] = proposal_decisions.get(decision, 0) + 1
    preview_failures = sum(bool(source.get("preview_failure")) for source in sources)
    pilot_gaps = {
        "independent_views": max(0, PIPELINE_PILOT_VIEWS - len(verified_views)),
        "non_broadcast_views": max(
            0, PIPELINE_PILOT_NON_BROADCAST_VIEWS - len(verified_non_broadcast)
        ),
        "capture_contexts": max(0, 3 - len(verified_contexts)),
        "verified_courts": max(0, PIPELINE_PILOT_VIEWS - len(verified_views)),
    }
    baseline_gaps = {
        "independent_views": max(0, INITIAL_BASELINE_VIEWS - len(verified_views)),
        "non_broadcast_views": max(
            0, INITIAL_BASELINE_NON_BROADCAST_VIEWS - len(verified_non_broadcast)
        ),
        "split_groups": max(0, INITIAL_BASELINE_SPLIT_GROUPS - len(verified_split_groups)),
        "capture_contexts": max(0, 3 - len(verified_contexts)),
        "verified_courts": max(0, INITIAL_BASELINE_VIEWS - len(verified_views)),
        "people_challenge_views": {
            scene: max(0, CHALLENGE_VIEWS_PER_SCENE - len(challenge_views[scene]))
            for scene in sorted(challenge_scenes)
        },
    }
    print(
        json.dumps(
            {
                "dataset_root": str(root),
                "source_status": counts,
                "accepted_views": len(accepted_views),
                "accepted_non_broadcast_views": len(accepted_non_broadcast),
                "accepted_contexts": sorted(accepted_contexts),
                "accepted_split_groups": len(accepted_split_groups),
                "verified_views": len(verified_views),
                "verified_non_broadcast_views": len(verified_non_broadcast),
                "verified_contexts": sorted(verified_contexts),
                "verified_split_groups": len(verified_split_groups),
                "verified_court_geometries": len(verified_views),
                "pending_court_fit_reviews": pending,
                "unresolved_court_fits": unresolved,
                "cached_preview_failures": preview_failures,
                "verified_people_documents": len(people_documents),
                "verified_people_scenes": sorted(people_scenes),
                "verified_people_challenge_views": {
                    scene: len(challenge_views[scene])
                    for scene in sorted(challenge_scenes)
                },
                "court_proposals": {
                    "total": len(proposal_paths),
                    "with_uncertain_points": uncertain_proposals,
                    "decisions": proposal_decisions,
                },
                "fresh_search_queries": fresh_queries,
                "targets": {
                    "pipeline_pilot": {
                        "verified_views": PIPELINE_PILOT_VIEWS,
                        "non_broadcast_views": PIPELINE_PILOT_NON_BROADCAST_VIEWS,
                    },
                    "initial_model_baseline": {
                        "verified_views_minimum": INITIAL_BASELINE_VIEWS,
                        "non_broadcast_views_minimum": INITIAL_BASELINE_NON_BROADCAST_VIEWS,
                        "split_groups_minimum": INITIAL_BASELINE_SPLIT_GROUPS,
                        "verified_views_per_people_challenge_minimum": CHALLENGE_VIEWS_PER_SCENE,
                        "growth_increment_views": 10,
                    },
                },
                "pilot_gaps": pilot_gaps,
                "baseline_gaps": baseline_gaps,
                "gaps": baseline_gaps,
            },
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
    )


def cmd_record_search(args: argparse.Namespace) -> None:
    root = dataset_root(args)
    store = paths(root)
    cache = read_json(store["cache"], {"schema_version": SCHEMA_VERSION, "queries": []})
    if cache.get("schema_version") != SCHEMA_VERSION:
        raise CurateError(f"search cache schema must be v{SCHEMA_VERSION}")
    key = search_key(args.purpose, args.query)
    now = dt.datetime.now(dt.timezone.utc)
    for entry in cache["queries"]:
        age = now - dt.datetime.fromisoformat(entry["searched_at"])
        if entry["query_key"] == key and age.days < CACHE_DAYS and not args.refresh:
            raise CurateError(
                f"query is cached for {CACHE_DAYS - age.days} more day(s); use --refresh explicitly"
            )
    results = read_json(Path(args.results), None)
    if not isinstance(results, list):
        raise CurateError("--results must contain a JSON array")
    sources = load_sources(root)
    known = {source["source_id"]: source for source in sources["sources"]}
    compact_results = []
    result_ids: set[str] = set()
    new_count = 0
    for item in results:
        if not isinstance(item, dict) or not item.get("url"):
            raise CurateError("each result needs url and preferably title")
        platform, video_id, url = normalize_url(str(item["url"]))
        source_id = f"{platform}:{video_id}"
        if source_id in result_ids:
            continue
        result_ids.add(source_id)
        compact_results.append(
            {"source_id": source_id, "canonical_url": url, "title": str(item.get("title", ""))}
        )
        if source_id in known:
            purposes = set(known[source_id].get("purposes", []))
            purposes.add(args.purpose)
            known[source_id]["purposes"] = sorted(purposes)
            continue
        if new_count >= 5:
            continue
        record = {
            "source_id": source_id,
            "platform": platform,
            "platform_video_id": video_id,
            "canonical_url": url,
            "title": str(item.get("title", "")),
            "status": "candidate",
            "capture_context": item.get("capture_context", "other"),
            "competition_level": item.get("competition_level", "unknown"),
            "purposes": [args.purpose],
            "usage": "internal_research",
            "venue": item.get("venue"),
            "discovered_at": utc_now(),
        }
        sources["sources"].append(record)
        known[source_id] = record
        new_count += 1
    cache["queries"] = [entry for entry in cache["queries"] if entry["query_key"] != key]
    cache["queries"].append(
        {
            "purpose": args.purpose,
            "query": args.query.strip(),
            "query_key": key,
            "searched_at": utc_now(),
            "results": compact_results[:5],
        }
    )
    write_json(store["sources"], sources)
    write_json(store["cache"], cache)
    print(f"recorded {new_count} new candidate(s); {len(compact_results[:5])} result(s) cached")


def cmd_review_source(args: argparse.Namespace) -> None:
    root = dataset_root(args)
    document = load_sources(root)
    source = source_by_id(document, args.source_id)
    if source.get("review") and not args.recheck:
        raise CurateError("review already exists; use --recheck only after an explicit human decision")
    purposes = sorted(set(args.purpose or source.get("purposes", [])))
    if not purposes or any(purpose not in SEARCH_PURPOSES for purpose in purposes):
        raise CurateError("review requires at least one purpose: court or people")
    source.update(
        {
            "status": args.decision,
            "capture_context": args.capture_context,
            "competition_level": args.competition_level,
            "purposes": purposes,
        }
    )
    if args.decision == "accepted":
        if not args.view_id or not args.split_group_id:
            raise CurateError("accepted source requires --view-id and --split-group-id")
        source["view_id"] = args.view_id
        source["split_group_id"] = args.split_group_id
    source["review"] = {
        "decision": args.decision,
        "reason": args.reason,
        "reviewer": args.reviewer,
        "reviewed_at": utc_now(),
    }
    write_json(paths(root)["sources"], document)
    print(f"{args.source_id}: {args.decision}")


def _run_preview(args: argparse.Namespace) -> None:
    root = dataset_root(args)
    document = load_sources(root)
    source = source_by_id(document, args.source_id)
    metadata = inspect_media(source, args.input)
    source["media_metadata"] = metadata
    windows = [parse_range(value) for value in args.window] if args.window else automatic_preview_windows(
        metadata["duration_s"]
    )
    if not 1 <= len(windows) <= 3 or any(not 1 <= end - start <= 12 for start, end in windows):
        raise CurateError("preview requires one to three windows, each between 1 and 12 seconds")
    out_dir = paths(root)["local"] / "previews" / safe_key(args.source_id)
    artifacts = []
    with tempfile.TemporaryDirectory(prefix="badminton-preview-") as temp_dir:
        temporary = Path(temp_dir)
        raw_clips = bounded_captures(source, args.input, windows, temporary)
        sheet_frames = temporary / "sheet"
        frames_per_window = 3
        sheet_index = 1
        for index, ((start, end), raw) in enumerate(zip(windows, raw_clips), 1):
            duration = end - start
            clip = out_dir / f"preview-{index}.mp4"
            transcode(raw, clip, fps=1, height=360, bitrate="300k", duration_s=duration)
            artifacts.append(
                artifact(
                    root,
                    clip,
                    start,
                    end,
                    {"height": 360, "fps": 1, "audio": False},
                )
            )
            for ratio in (0.15, 0.5, 0.85):
                frame = sheet_frames / f"sheet-{sheet_index:03d}.jpg"
                extract_frame(clip, min(max(0.0, duration * ratio), max(0.0, duration - 0.1)), frame, 320)
                sheet_index += 1
        sheet = out_dir / "contact-sheet.jpg"
        run(
            [
                find_ffmpeg(),
                "-hide_banner",
                "-loglevel",
                "error",
                "-framerate",
                "1",
                "-i",
                str(sheet_frames / "sheet-%03d.jpg"),
                "-vf",
                f"tile=3x{len(windows)}",
                "-frames:v",
                "1",
                "-strict",
                "unofficial",
                "-y",
                str(sheet),
            ]
        )
        artifacts.append(
            {
                "path": sheet.relative_to(root).as_posix(),
                "sha256": sha256(sheet),
                "sampling": {"layout": f"3x{len(windows)}"},
            }
        )
    source.setdefault("artifacts", {})["previews"] = artifacts
    write_json(paths(root)["sources"], document)
    print(sheet)


def cmd_preview(args: argparse.Namespace) -> None:
    root = dataset_root(args)
    document = load_sources(root)
    source = source_by_id(document, args.source_id)
    failure = source.get("preview_failure")
    if failure and not args.retry:
        failed_at = dt.datetime.fromisoformat(failure["failed_at"])
        age = dt.datetime.now(dt.timezone.utc) - failed_at
        if age.days < PREVIEW_FAILURE_DAYS:
            raise CurateError(
                f"preview failure is cached for {PREVIEW_FAILURE_DAYS - age.days} more day(s); "
                "use --retry explicitly"
            )
    try:
        _run_preview(args)
    except (CurateError, OSError) as exc:
        document = load_sources(root)
        source = source_by_id(document, args.source_id)
        source["preview_failure"] = {"error": str(exc), "failed_at": utc_now()}
        write_json(paths(root)["sources"], document)
        raise
    document = load_sources(root)
    source = source_by_id(document, args.source_id)
    if source.pop("preview_failure", None):
        write_json(paths(root)["sources"], document)


def require_source_view(source: dict[str, Any], view_id: str) -> None:
    if source.get("view_id") != view_id:
        raise CurateError(
            f"view_id does not match accepted source metadata: expected {source.get('view_id')!r}"
        )


def cmd_sample_court(args: argparse.Namespace) -> None:
    if args.scene == "court_partial_unresolved":
        raise CurateError("court_partial_unresolved is produced by fit/review, not sampled directly")
    root = dataset_root(args)
    document = load_sources(root)
    source = source_by_id(document, args.source_id)
    require_accepted(source, "sample-court")
    require_source_view(source, args.view_id)
    start, end = parse_range(args.window)
    if not 2 <= end - start <= 20:
        raise CurateError("court sampling window must be between 2 and 20 seconds")
    count = 3 if args.scene == "court_complete" else 1
    existing_complete = sum(
        item.get("view_id") == args.view_id and item.get("scene") == "court_complete"
        for item in source.get("artifacts", {}).get("court_samples", [])
    )
    if args.scene == "court_complete" and existing_complete + count > 5:
        raise CurateError("a view may retain at most five court_complete frames")
    out_dir = paths(root)["local"] / "frames/court" / safe_key(args.view_id)
    prefix = f"{safe_key(args.source_id)}-{args.scene}-{round(start * 1000):012d}"
    artifacts = []
    with tempfile.TemporaryDirectory(prefix="badminton-court-") as temp_dir:
        raw = bounded_captures(source, args.input, [(start, end)], Path(temp_dir))[0]
        for index in range(count):
            ratio = (index + 1) / (count + 1)
            relative_second = (end - start) * ratio
            output = out_dir / f"{prefix}-{index + 1}.jpg"
            extract_frame(raw, relative_second, output)
            artifacts.append(
                artifact(
                    root,
                    output,
                    start + relative_second,
                    start + relative_second,
                    {"frame_count": 1},
                    view_id=args.view_id,
                    scene=args.scene,
                    target="court",
                )
            )
    append_artifacts(source, "court_samples", artifacts)
    write_json(paths(root)["sources"], document)
    print(json.dumps({"frames": [item["path"] for item in artifacts]}, ensure_ascii=False))


def verified_court_path(root: Path, view_id: str) -> Path:
    return paths(root)["annotations"] / "verified/court" / f"{safe_key(view_id)}.json"


def cmd_sample_people(args: argparse.Namespace) -> None:
    root = dataset_root(args)
    document = load_sources(root)
    source = source_by_id(document, args.source_id)
    require_accepted(source, "sample-people")
    require_source_view(source, args.view_id)
    geometry_path = verified_court_path(root, args.view_id)
    geometry = read_json(geometry_path, None)
    if not geometry or geometry.get("review_status") != "verified":
        raise CurateError("sample-people requires verified court geometry for the same view_id")
    start, end = parse_range(args.segment)
    duration = end - start
    if not 10 <= duration <= 20:
        raise CurateError("people segment must be between 10 and 20 seconds")
    output = (
        paths(root)["local"]
        / "clips/people"
        / safe_key(args.view_id)
        / f"{args.scene}-{round(start * 1000):012d}.mp4"
    )
    with tempfile.TemporaryDirectory(prefix="badminton-people-") as temp_dir:
        raw = bounded_captures(source, args.input, [(start, end)], Path(temp_dir))[0]
        transcode(raw, output, fps=10, height=720, bitrate="1000k", duration_s=duration)
    if not output.exists() or output.stat().st_size == 0:
        raise CurateError(f"people transcode produced no data: {output}")
    record = artifact(
        root,
        output,
        start,
        end,
        {"max_height": 720, "fps": 10, "video_bitrate": "1000k", "audio": False},
        view_id=args.view_id,
        scene=args.scene,
        target="people",
        court_geometry=geometry_path.relative_to(root).as_posix(),
    )
    append_artifacts(source, "people_samples", [record])
    write_json(paths(root)["sources"], document)
    print(output)


def court_label_spec() -> dict[str, Any]:
    return {
        "labels": [
            {
                "name": "court_control_point",
                "type": "points",
                "attributes": [
                    {
                        "name": "point_id",
                        "input_type": "select",
                        "values": list(COURT_CONTROL_POINTS),
                        "mutable": False,
                    }
                ],
            },
            {
                "name": "view_state",
                "type": "tag",
                "attributes": [
                    {
                        "name": "state",
                        "input_type": "select",
                        "values": list(COURT_SCENES[:3]),
                        "mutable": False,
                    }
                ],
            },
        ]
    }


def people_label_spec() -> dict[str, Any]:
    return {
        "labels": [
            {
                "name": "person",
                "type": "rectangle",
                "attributes": [
                    {
                        "name": "role",
                        "input_type": "select",
                        "values": ["participant", "non_participant", "unknown"],
                        "mutable": False,
                    },
                    {
                        "name": "court_side",
                        "input_type": "select",
                        "values": ["near", "far", "outside", "unknown"],
                        "mutable": True,
                    },
                ],
            }
        ]
    }


def cmd_build_cvat(args: argparse.Namespace) -> None:
    root = dataset_root(args)
    source = source_by_id(load_sources(root), args.source_id)
    require_accepted(source, "build-cvat")
    require_source_view(source, args.view_id)
    local = paths(root)["local"]
    if args.target == "court":
        media = sorted((local / "frames/court" / safe_key(args.view_id)).glob("*.jpg"))
        labels = court_label_spec()
        geometry_reference = None
    else:
        geometry_path = verified_court_path(root, args.view_id)
        if not geometry_path.is_file():
            raise CurateError("people CVAT task requires verified court geometry")
        media = sorted((local / "clips/people" / safe_key(args.view_id)).glob("*.mp4"))
        labels = people_label_spec()
        geometry_reference = geometry_path.relative_to(root).as_posix()
    if not media:
        raise CurateError(f"no {args.target} media; run sample-{args.target} first")
    task_dir = local / "cvat-tasks" / args.target / safe_key(args.view_id)
    write_json(task_dir / "labels.json", labels)
    write_json(
        task_dir / "task.json",
        {
            "schema_version": SCHEMA_VERSION,
            "target": args.target,
            "source_id": args.source_id,
            "view_id": args.view_id,
            "created_at": utc_now(),
            "media": [
                {"path": item.relative_to(root).as_posix(), "sha256": sha256(item)}
                for item in media
            ],
            "court_geometry": geometry_reference,
            "instructions": {
                "court": "label only certain visible standard control points; never invent hidden points",
                "people": (
                    "track every discernible person on the playing floor and officiating area; "
                    "ignore seated stands"
                ),
                "workflow": "draft -> verified",
            },
        },
    )
    bundle = Path(str(task_dir) + ".zip")
    with zipfile.ZipFile(bundle, "w", zipfile.ZIP_DEFLATED) as archive:
        for item in sorted(task_dir.glob("*.json")):
            archive.write(item, item.name)
        for item in media:
            archive.write(item, "media/" + item.name)
    print(bundle)


def safe_read_datumaro(export: Path) -> dict[str, Any]:
    if export.is_dir():
        return read_json(export / "annotations/default.json", None)
    with zipfile.ZipFile(export) as archive:
        candidates = [name for name in archive.namelist() if name.endswith("annotations/default.json")]
        if len(candidates) != 1:
            raise CurateError("Datumaro export must contain one annotations/default.json")
        return json.loads(archive.read(candidates[0]))


def datumaro_label_names(document: dict[str, Any]) -> list[str | None]:
    categories = document.get("categories", {})
    return [item.get("name") for item in categories.get("label", {}).get("labels", [])]


def annotation_label(annotation: dict[str, Any], names: list[str | None]) -> str | None:
    label_id = annotation.get("label_id", annotation.get("label"))
    return names[label_id] if isinstance(label_id, int) and 0 <= label_id < len(names) else None


def json_sha256(value: Any) -> str:
    encoded = json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode()
    return hashlib.sha256(encoded).hexdigest()


def image_dimensions(path: Path) -> tuple[int, int]:
    try:
        from PIL import Image  # type: ignore
    except ImportError as exc:
        raise CurateError("Pillow is required for court proposals") from exc
    with Image.open(path) as image:
        return image.size


def validated_proposal_points(
    value: Any, width: int, height: int
) -> list[dict[str, Any]]:
    if not isinstance(value, list) or not value:
        raise CurateError("court proposal requires a non-empty points array")
    result = []
    point_ids: set[str] = set()
    for raw in value:
        if not isinstance(raw, dict):
            raise CurateError("every proposed court point must be an object")
        point_id = raw.get("point_id")
        if point_id not in COURT_CONTROL_POINTS or point_id in point_ids:
            raise CurateError("proposed court point ids must be unique and known")
        try:
            x, y = float(raw["x"]), float(raw["y"])
            confidence = float(raw["confidence"])
        except (KeyError, TypeError, ValueError) as exc:
            raise CurateError("proposed court point requires numeric x, y, confidence") from exc
        if not all(math.isfinite(item) for item in (x, y, confidence)):
            raise CurateError("proposed court point contains non-finite values")
        if not 0 <= x < width or not 0 <= y < height:
            raise CurateError("proposed court point must be visible inside the image")
        if not 0 <= confidence <= 1:
            raise CurateError("proposed court point confidence must be between zero and one")
        if not isinstance(raw.get("uncertain"), bool):
            raise CurateError("proposed court point requires boolean uncertain")
        point = {
            "point_id": point_id,
            "x": x,
            "y": y,
            "confidence": confidence,
            "uncertain": raw["uncertain"],
        }
        if raw.get("reason"):
            point["reason"] = str(raw["reason"])
        result.append(point)
        point_ids.add(point_id)
    return result


def court_proposal_review_path(proposal_path: Path) -> Path:
    return proposal_path.with_suffix(".review.json")


def stored_court_proposal(root: Path, value: str) -> tuple[Path, dict[str, Any]]:
    proposed_root = (paths(root)["annotations"] / "proposed/court").resolve()
    proposal_path = Path(value).resolve()
    if not proposal_path.is_file() or not proposal_path.is_relative_to(proposed_root):
        raise CurateError("--proposal must point to a stored court proposal")
    if proposal_path.name.endswith(".review.json"):
        raise CurateError("--proposal must point to the immutable model output")
    proposal = read_json(proposal_path, None)
    if not isinstance(proposal, dict) or proposal.get("status") != "proposed":
        raise CurateError("invalid court proposal document")
    return proposal_path, proposal


def court_proposal_identity(proposal: dict[str, Any]) -> dict[str, Any]:
    return {
        "source_id": proposal.get("source_id"),
        "view_id": proposal.get("view_id"),
        "item_id": proposal.get("item_id"),
        "view_state": proposal.get("view_state"),
        "image_sha256": proposal.get("image_sha256"),
        "producer": proposal.get("producer"),
        "points": proposal.get("points"),
    }


def cmd_record_court_proposal(args: argparse.Namespace) -> None:
    root = dataset_root(args)
    source = source_by_id(load_sources(root), args.source_id)
    require_accepted(source, "record-court-proposal")
    require_source_view(source, args.view_id)
    frame = Path(args.frame).resolve()
    if not frame.is_file():
        raise CurateError("court proposal frame does not exist")
    frame_path = portable_path(frame, root)
    sampled = next(
        (
            item
            for item in source.get("artifacts", {}).get("court_samples", [])
            if item.get("view_id") == args.view_id and item.get("path") == frame_path
        ),
        None,
    )
    if not sampled:
        raise CurateError("court proposal frame is not a sampled artifact for this view")
    payload = read_json(Path(args.proposal), None)
    if not isinstance(payload, dict):
        raise CurateError("--proposal must be a JSON document")
    width, height = image_dimensions(frame)
    points = validated_proposal_points(payload.get("points"), width, height)
    producer = {
        "tool": args.producer,
        "model": args.model,
        "model_version": args.model_version,
        "prompt_version": args.prompt_version,
    }
    identity = court_proposal_identity({
        "source_id": args.source_id,
        "view_id": args.view_id,
        "item_id": payload.get("item_id") or frame.stem,
        "view_state": sampled.get("scene"),
        "image_sha256": sha256(frame),
        "producer": producer,
        "points": points,
    })
    proposal_id = json_sha256(identity)[:20]
    proposal_path = (
        paths(root)["annotations"]
        / "proposed/court"
        / safe_key(args.view_id)
        / f"{proposal_id}.json"
    )
    if not proposal_path.exists():
        write_json(
            proposal_path,
            {
                "schema_version": SCHEMA_VERSION,
                "target": "court",
                "status": "proposed",
                "proposal_id": proposal_id,
                "source_id": args.source_id,
                "view_id": args.view_id,
                "item_id": identity["item_id"],
                "view_state": identity["view_state"],
                "frame": frame_path,
                "image_size": {"width": width, "height": height},
                "image_sha256": identity["image_sha256"],
                "producer": producer,
                "points": points,
                "uncertain_point_count": sum(point["uncertain"] for point in points),
                "created_at": utc_now(),
            },
        )
    print(proposal_path)


def cmd_render_court_proposal(args: argparse.Namespace) -> None:
    root = dataset_root(args)
    proposal_path, proposal = stored_court_proposal(root, args.proposal)
    frame = (root / proposal.get("frame", "")).resolve()
    if not frame.is_file() or not frame.is_relative_to(root):
        raise CurateError("court proposal frame is missing")
    try:
        from PIL import Image, ImageDraw  # type: ignore
    except ImportError as exc:
        raise CurateError("Pillow is required for court proposal overlays") from exc
    with Image.open(frame).convert("RGB") as image:
        draw = ImageDraw.Draw(image)
        for point in proposal.get("points", []):
            x, y = float(point["x"]), float(point["y"])
            color = "#ff3b30" if point.get("uncertain") else "#34c759"
            radius = 7
            draw.ellipse((x - radius, y - radius, x + radius, y + radius), fill=color)
            label = (
                f"{point['point_id']} "
                f"{float(point.get('confidence', 0)):.2f}"
                f"{' ?' if point.get('uncertain') else ''}"
            )
            draw.rectangle((x + 10, y - 10, x + 16 + 7 * len(label), y + 8), fill="#000000")
            draw.text((x + 13, y - 8), label, fill="#ffffff")
        output = (
            paths(root)["local"]
            / "court-proposals"
            / safe_key(proposal["view_id"])
            / f"{proposal_path.stem}-overlay.jpg"
        )
        output.parent.mkdir(parents=True, exist_ok=True)
        image.save(output, quality=92)
    print(output)


def cmd_review_court_proposal(args: argparse.Namespace) -> None:
    root = dataset_root(args)
    proposal_path, proposal = stored_court_proposal(root, args.proposal)
    source = source_by_id(load_sources(root), proposal.get("source_id", ""))
    require_accepted(source, "review-court-proposal")
    require_source_view(source, proposal.get("view_id", ""))
    review_path = court_proposal_review_path(proposal_path)
    if review_path.exists() and not args.recheck:
        raise CurateError("proposal already reviewed; use --recheck after an explicit human decision")
    if args.corrected and args.decision == "rejected":
        raise CurateError("--corrected is only valid for accepted or needs_review")
    width = int(proposal.get("image_size", {}).get("width", 0))
    height = int(proposal.get("image_size", {}).get("height", 0))
    points = validated_proposal_points(proposal.get("points"), width, height)
    corrected_sha256 = None
    if args.corrected:
        corrected_path = Path(args.corrected)
        corrected = read_json(corrected_path, None)
        if not isinstance(corrected, dict):
            raise CurateError("--corrected must be a JSON document")
        points = validated_proposal_points(corrected.get("points"), width, height)
        corrected_sha256 = sha256(corrected_path)
    review = {
        "schema_version": SCHEMA_VERSION,
        "target": "court_proposal_review",
        "proposal": proposal_path.relative_to(root).as_posix(),
        "proposal_sha256": sha256(proposal_path),
        "decision": args.decision,
        "reviewer": args.reviewer,
        "reason": args.reason,
        "reviewed_at": utc_now(),
        "corrected_sha256": corrected_sha256,
    }
    if args.corrected:
        review["corrected_points"] = points
    output = review_path
    if args.decision == "accepted":
        if any(point["uncertain"] for point in points):
            raise CurateError("accepted proposal cannot retain uncertain points")
        normalized_dlt(points)
        draft_path = (
            paths(root)["annotations"]
            / "draft/court-controls"
            / f"{safe_key(proposal['view_id'])}.json"
        )
        if draft_path.exists() and not args.replace:
            raise CurateError(
                "draft court controls already exist; --replace requires an explicit human decision"
            )
        promoted_points = [
            {
                "point_id": point["point_id"],
                "x": point["x"],
                "y": point["y"],
                "source": "manual",
                "annotation_origin": "model_assisted_human_verified",
                "model_confidence": point["confidence"],
            }
            for point in points
        ]
        write_json(
            draft_path,
            {
                "schema_version": SCHEMA_VERSION,
                "target": "court",
                "source_id": proposal["source_id"],
                "view_id": proposal["view_id"],
                "status": "draft",
                "reviewer": args.reviewer,
                "imported_at": utc_now(),
                "annotation_origin": "model_assisted_human_verified",
                "proposal_provenance": {
                    "proposal": proposal_path.relative_to(root).as_posix(),
                    "proposal_sha256": review["proposal_sha256"],
                    "producer": proposal["producer"],
                },
                "items": [
                    {
                        "item_id": proposal["item_id"],
                        "view_state": proposal["view_state"],
                        "points": promoted_points,
                    }
                ],
            },
        )
        review["promoted_draft"] = draft_path.relative_to(root).as_posix()
        review["promoted_draft_sha256"] = sha256(draft_path)
        review["accepted_points"] = points
        output = draft_path
    write_json(review_path, review)
    print(output)


def cmd_import_cvat(args: argparse.Namespace) -> None:
    root = dataset_root(args)
    source = source_by_id(load_sources(root), args.source_id)
    require_source_view(source, args.view_id)
    export = Path(args.export)
    datumaro = safe_read_datumaro(export)
    if not isinstance(datumaro, dict) or not isinstance(datumaro.get("items"), list):
        raise CurateError("invalid Datumaro document")
    label_names = datumaro_label_names(datumaro)
    if args.target == "court":
        if "court_control_point" not in label_names or "view_state" not in label_names:
            raise CurateError("court export requires court_control_point and view_state labels")
        items = []
        for item in datumaro["items"]:
            points = []
            states = []
            for annotation in item.get("annotations", []):
                label = annotation_label(annotation, label_names)
                attributes = annotation.get("attributes", {})
                if label == "court_control_point" and annotation.get("type") == "points":
                    coordinates = annotation.get("points", [])
                    point_id = attributes.get("point_id")
                    if point_id not in COURT_CONTROL_POINTS or len(coordinates) != 2:
                        raise CurateError("court point requires a known point_id and one x,y pair")
                    points.append({"point_id": point_id, "x": coordinates[0], "y": coordinates[1]})
                elif label == "view_state":
                    state = attributes.get("state")
                    if state not in COURT_SCENES[:3]:
                        raise CurateError("view_state requires a supported state")
                    states.append(state)
            if len(states) != 1:
                raise CurateError("every court item requires exactly one view_state tag")
            items.append({"item_id": item.get("id"), "view_state": states[0], "points": points})
        output = (
            paths(root)["annotations"]
            / "draft/court-controls"
            / f"{safe_key(args.view_id)}.json"
        )
        write_json(
            output,
            {
                "schema_version": SCHEMA_VERSION,
                "target": "court",
                "source_id": args.source_id,
                "view_id": args.view_id,
                "status": "draft",
                "reviewer": args.reviewer,
                "imported_at": utc_now(),
                "items": items,
                "datumaro_sha256": sha256_export(export),
            },
        )
    else:
        if args.status is None:
            raise CurateError("people import requires --status draft|verified")
        if "person" not in label_names:
            raise CurateError("people export requires person label")
        if args.status == "verified" and not verified_court_path(root, args.view_id).is_file():
            raise CurateError("verified people annotations require verified court geometry")
        annotations = []
        scenes: set[str] = set()
        for item in datumaro["items"]:
            for annotation in item.get("annotations", []):
                if annotation_label(annotation, label_names) != "person":
                    continue
                if annotation.get("type") != "bbox":
                    raise CurateError("person annotations must be bbox tracks")
                attributes = annotation.get("attributes", {})
                if attributes.get("role") not in {"participant", "non_participant", "unknown"}:
                    raise CurateError("person bbox requires role")
                if attributes.get("court_side") not in {"near", "far", "outside", "unknown"}:
                    raise CurateError("person bbox requires court_side")
                if "track_id" not in attributes:
                    raise CurateError("person bbox requires CVAT track_id")
                annotations.append({"item_id": item.get("id"), **annotation})
        scenes.update(
            item.get("scene")
            for item in source.get("artifacts", {}).get("people_samples", [])
            if item.get("view_id") == args.view_id and item.get("scene") in PEOPLE_SCENES
        )
        output = (
            paths(root)["annotations"]
            / args.status
            / "people"
            / f"{safe_key(args.view_id)}-{safe_key(args.source_id)}.json"
        )
        write_json(
            output,
            {
                "schema_version": SCHEMA_VERSION,
                "target": "people",
                "source_id": args.source_id,
                "view_id": args.view_id,
                "status": args.status,
                "reviewer": args.reviewer,
                "imported_at": utc_now(),
                "scene_types": sorted(scenes),
                "court_geometry": verified_court_path(root, args.view_id).relative_to(root).as_posix(),
                "annotations": annotations,
                "datumaro_sha256": sha256_export(export),
            },
        )
    print(output)


def select_control_item(document: dict[str, Any], item_id: str | None) -> dict[str, Any]:
    if isinstance(document.get("points"), list):
        return {"item_id": item_id, "points": document["points"]}
    items = document.get("items")
    if not isinstance(items, list):
        raise CurateError("controls document requires points or items")
    candidates = [item for item in items if item_id is None or str(item.get("item_id")) == item_id]
    if item_id is not None and len(candidates) != 1:
        raise CurateError(f"controls contain no unique item_id={item_id!r}")
    if item_id is None:
        candidates = [item for item in candidates if len(item.get("points", [])) >= 4]
    if not candidates:
        return {"item_id": item_id, "points": []}
    return candidates[0]


def normalized_dlt(control_points: list[dict[str, Any]]) -> tuple[list[list[float]], list[float]]:
    try:
        import numpy as np  # type: ignore
    except ImportError as exc:
        raise CurateError("numpy is required for court fitting") from exc
    if len(control_points) < 4:
        raise CurateError("at least four control points are required")
    ids = [point.get("point_id") for point in control_points]
    if len(ids) != len(set(ids)) or any(point_id not in COURT_CONTROL_POINTS for point_id in ids):
        raise CurateError("control point ids must be unique and known")
    world = np.asarray([COURT_CONTROL_POINTS[point_id] for point_id in ids], dtype=float)
    image = np.asarray([[float(point["x"]), float(point["y"])] for point in control_points], dtype=float)
    if np.linalg.matrix_rank(world - world.mean(axis=0)) < 2:
        raise CurateError("world control points are collinear")
    if np.linalg.matrix_rank(image - image.mean(axis=0)) < 2:
        raise CurateError("image control points are collinear")

    def normalize(points: Any) -> tuple[Any, Any]:
        center = points.mean(axis=0)
        shifted = points - center
        mean_distance = np.mean(np.linalg.norm(shifted, axis=1))
        if mean_distance <= 1e-9:
            raise CurateError("control points are degenerate")
        scale = math.sqrt(2) / mean_distance
        transform = np.asarray(
            [[scale, 0.0, -scale * center[0]], [0.0, scale, -scale * center[1]], [0.0, 0.0, 1.0]]
        )
        homogeneous = np.column_stack([points, np.ones(len(points))])
        normalized = (transform @ homogeneous.T).T
        return normalized[:, :2], transform

    world_n, world_transform = normalize(world)
    image_n, image_transform = normalize(image)
    rows = []
    for (x, y), (u, v) in zip(world_n, image_n):
        rows.append([-x, -y, -1, 0, 0, 0, u * x, u * y, u])
        rows.append([0, 0, 0, -x, -y, -1, v * x, v * y, v])
    matrix = np.asarray(rows, dtype=float)
    if np.linalg.matrix_rank(matrix) < 8:
        raise CurateError("control point system is rank-deficient")
    _, _, vectors = np.linalg.svd(matrix)
    homography_n = vectors[-1].reshape(3, 3)
    homography = np.linalg.inv(image_transform) @ homography_n @ world_transform
    scale = homography[2, 2]
    if abs(scale) <= 1e-12:
        scale = np.linalg.norm(homography)
    if not np.isfinite(scale) or abs(scale) <= 1e-12:
        raise CurateError("homography normalization failed")
    homography /= scale
    projected = project_points(homography.tolist(), [COURT_CONTROL_POINTS[point_id] for point_id in ids])
    errors = [
        math.hypot(projected_point[0] - image_point[0], projected_point[1] - image_point[1])
        for projected_point, image_point in zip(projected, image.tolist())
    ]
    if not all(math.isfinite(value) for row in homography for value in row):
        raise CurateError("homography contains non-finite values")
    return homography.tolist(), errors


def project_points(
    homography: list[list[float]], points: list[tuple[float, float]]
) -> list[tuple[float, float]]:
    result = []
    for x, y in points:
        denominator = homography[2][0] * x + homography[2][1] * y + homography[2][2]
        if abs(denominator) <= 1e-12:
            raise CurateError("court point projects to infinity")
        u = (homography[0][0] * x + homography[0][1] * y + homography[0][2]) / denominator
        v = (homography[1][0] * x + homography[1][1] * y + homography[1][2]) / denominator
        result.append((u, v))
    return result


def clip_segment(
    start: tuple[float, float],
    end: tuple[float, float],
    width: int,
    height: int,
) -> tuple[tuple[float, float], tuple[float, float]] | None:
    x0, y0 = start
    x1, y1 = end
    dx, dy = x1 - x0, y1 - y0
    lower, upper = 0.0, 1.0
    for p, q in ((-dx, x0), (dx, width - 1 - x0), (-dy, y0), (dy, height - 1 - y0)):
        if abs(p) < 1e-12:
            if q < 0:
                return None
            continue
        ratio = q / p
        if p < 0:
            lower = max(lower, ratio)
        else:
            upper = min(upper, ratio)
        if lower > upper:
            return None
    return ((x0 + lower * dx, y0 + lower * dy), (x0 + upper * dx, y0 + upper * dy))


def create_overlay(
    frame: Path,
    output: Path,
    homography: list[list[float]],
    controls: list[dict[str, Any]],
) -> tuple[int, int]:
    try:
        from PIL import Image, ImageDraw  # type: ignore
    except ImportError as exc:
        raise CurateError("Pillow is required for court-fit overlays") from exc
    image = Image.open(frame).convert("RGB")
    width, height = image.size
    draw = ImageDraw.Draw(image)
    projected = {
        point_id: point
        for point_id, point in zip(
            COURT_CONTROL_POINTS,
            project_points(homography, list(COURT_CONTROL_POINTS.values())),
        )
    }
    for first, second in COURT_TEMPLATE_SEGMENTS:
        clipped = clip_segment(projected[first], projected[second], width, height)
        if clipped:
            draw.line(clipped, fill=(0, 255, 80), width=3)
    for point in controls:
        x, y = float(point["x"]), float(point["y"])
        draw.ellipse((x - 5, y - 5, x + 5, y + 5), fill=(255, 60, 60))
    output.parent.mkdir(parents=True, exist_ok=True)
    image.save(output, quality=92)
    return width, height


def unresolved_geometry(
    source_id: str,
    view_id: str,
    item_id: str | None,
    controls: list[dict[str, Any]],
    reason: str,
) -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "target": "court",
        "source_id": source_id,
        "view_id": view_id,
        "reference_item_id": item_id,
        "scene_state": "court_partial_unresolved",
        "review_status": "unresolved",
        "reason": reason,
        "control_points": controls,
        "canonical_points": [],
        "created_at": utc_now(),
    }


def cmd_fit_court(args: argparse.Namespace) -> None:
    root = dataset_root(args)
    source = source_by_id(load_sources(root), args.source_id)
    require_accepted(source, "fit-court")
    require_source_view(source, args.view_id)
    controls_document = read_json(Path(args.controls), None)
    if not isinstance(controls_document, dict):
        raise CurateError("--controls must be a JSON document")
    selected = select_control_item(controls_document, args.item_id)
    controls = selected.get("points", [])
    draft_path = (
        paths(root)["annotations"] / "draft/court" / f"{safe_key(args.view_id)}.json"
    )
    try:
        homography, errors = normalized_dlt(controls)
        width, height = create_overlay(
            Path(args.frame),
            paths(root)["local"] / "court-fits" / safe_key(args.view_id) / "overlay.jpg",
            homography,
            controls,
        )
        projected = dict(
            zip(
                CANONICAL_POINT_IDS,
                project_points(homography, [COURT_CONTROL_POINTS[name] for name in CANONICAL_POINT_IDS]),
            )
        )
        manual = {point["point_id"]: point for point in controls}
        canonical_points = []
        for point_id in CANONICAL_POINT_IDS:
            x, y = projected[point_id]
            if point_id in manual:
                x, y = float(manual[point_id]["x"]), float(manual[point_id]["y"])
                visibility, point_source = "visible", "manual"
            else:
                visibility = "outside" if x < 0 or x >= width or y < 0 or y >= height else "occluded"
                point_source = "geometry_inferred"
            canonical_points.append(
                {
                    "point_id": point_id,
                    "x": x,
                    "y": y,
                    "visibility": visibility,
                    "source": point_source,
                }
            )
        has_inferred = any(point["source"] == "geometry_inferred" for point in canonical_points)
        overlay_path = paths(root)["local"] / "court-fits" / safe_key(args.view_id) / "overlay.jpg"
        geometry = {
            "schema_version": SCHEMA_VERSION,
            "target": "court",
            "source_id": args.source_id,
            "view_id": args.view_id,
            "reference_item_id": selected.get("item_id"),
            "reference_frame": portable_path(Path(args.frame), root),
            "image_size": {"width": width, "height": height},
            "scene_state": "court_partial" if has_inferred else "court_complete",
            "review_status": "pending_review",
            "homography_image_from_court": homography,
            "control_points": controls,
            "canonical_points": canonical_points,
            "reprojection_error": {
                "per_point_px": errors,
                "mean_px": sum(errors) / len(errors),
                "max_px": max(errors),
            },
            "overlay": overlay_path.relative_to(root).as_posix(),
            "created_at": utc_now(),
        }
    except CurateError as exc:
        geometry = unresolved_geometry(
            args.source_id, args.view_id, selected.get("item_id"), controls, str(exc)
        )
    write_json(draft_path, geometry)
    print(draft_path)


def cmd_review_court_fit(args: argparse.Namespace) -> None:
    root = dataset_root(args)
    draft_path = paths(root)["annotations"] / "draft/court" / f"{safe_key(args.view_id)}.json"
    geometry = read_json(draft_path, None)
    if not isinstance(geometry, dict):
        raise CurateError("no draft court fit exists for view_id")
    if geometry.get("review_status") not in {"pending_review", "unresolved"} and not args.recheck:
        raise CurateError("court fit already reviewed; use --recheck after an explicit human decision")
    geometry["review"] = {
        "decision": args.decision,
        "reason": args.reason,
        "reviewer": args.reviewer,
        "reviewed_at": utc_now(),
    }
    if args.decision == "accepted":
        if not geometry.get("homography_image_from_court") or len(geometry.get("canonical_points", [])) != 6:
            raise CurateError("unresolved court fit cannot be accepted")
        geometry["review_status"] = "verified"
        geometry["allow_inferred_training"] = bool(args.allow_inferred_training)
        geometry["training_points"] = [
            point
            for point in geometry["canonical_points"]
            if point["source"] == "manual" or args.allow_inferred_training
        ]
        write_json(draft_path, geometry)
        output = verified_court_path(root, args.view_id)
        write_json(output, geometry)
    else:
        geometry["review_status"] = "rejected"
        geometry["scene_state"] = "court_partial_unresolved"
        geometry["canonical_points"] = []
        geometry.pop("homography_image_from_court", None)
        geometry.pop("training_points", None)
        output = draft_path
        write_json(output, geometry)
    print(output)


def validate_source(source: dict[str, Any], errors: list[str]) -> None:
    required = {
        "source_id",
        "platform",
        "platform_video_id",
        "canonical_url",
        "title",
        "status",
        "capture_context",
        "competition_level",
        "purposes",
        "usage",
    }
    missing = sorted(required - source.keys())
    if missing:
        errors.append(f"{source.get('source_id', '<unknown>')}: missing fields {missing}")
    if source.get("capture_context") not in CAPTURE_CONTEXTS:
        errors.append(f"{source.get('source_id')}: invalid capture_context")
    if source.get("competition_level") not in COMPETITION_LEVELS:
        errors.append(f"{source.get('source_id')}: invalid competition_level")
    if source.get("status") == "accepted":
        if not source.get("view_id") or not source.get("split_group_id"):
            errors.append(f"{source.get('source_id')}: accepted source lacks view/split group")
        if not set(source.get("purposes", [])).issubset(SEARCH_PURPOSES):
            errors.append(f"{source.get('source_id')}: invalid accepted purposes")


def cmd_validate(args: argparse.Namespace) -> None:
    root = dataset_root(args)
    errors: list[str] = []
    document = load_sources(root)
    sources = document.get("sources", [])
    ids = [source.get("source_id") for source in sources]
    urls = [source.get("canonical_url") for source in sources]
    if len(ids) != len(set(ids)):
        errors.append("duplicate source_id")
    if len(urls) != len(set(urls)):
        errors.append("duplicate canonical_url")
    for source in sources:
        validate_source(source, errors)
        for group in source.get("artifacts", {}).values():
            for item in group:
                artifact_path = root / item["path"]
                if not artifact_path.exists():
                    errors.append(f"missing artifact: {item['path']}")
                elif item.get("sha256") != sha256(artifact_path):
                    errors.append(f"hash mismatch: {item['path']}")
                if item.get("start_s", 0) > item.get("end_s", float("inf")):
                    errors.append(f"invalid artifact range: {item['path']}")
    source_map = {source["source_id"]: source for source in sources}
    splits = read_json(paths(root)["splits"], {"train": [], "validation": [], "test": []})
    assigned_sources: dict[str, str] = {}
    assigned_groups: dict[str, str] = {}
    for split in ("train", "validation", "test"):
        for source_id in splits.get(split, []):
            if source_id in assigned_sources:
                errors.append(f"source leakage: {source_id}")
            source = source_map.get(source_id)
            if not source:
                errors.append(f"unknown split source: {source_id}")
                continue
            if source.get("status") != "accepted":
                errors.append(f"split source is not accepted: {source_id}")
            group = source.get("split_group_id")
            if group in assigned_groups and assigned_groups[group] != split:
                errors.append(
                    f"split-group leakage: {group} in {assigned_groups[group]} and {split}"
                )
            assigned_sources[source_id] = split
            if group:
                assigned_groups[group] = split
    proposal_paths = [
        path
        for path in (paths(root)["annotations"] / "proposed/court").glob("*/*.json")
        if not path.name.endswith(".review.json")
    ]
    for path in proposal_paths:
        proposal = read_json(path, {})
        label = path.relative_to(root).as_posix()
        if (
            proposal.get("schema_version") != SCHEMA_VERSION
            or proposal.get("target") != "court"
            or proposal.get("status") != "proposed"
            or proposal.get("proposal_id") != path.stem
        ):
            errors.append(f"invalid court proposal envelope: {label}")
            continue
        source = source_map.get(proposal.get("source_id"))
        if not source or source.get("view_id") != proposal.get("view_id"):
            errors.append(f"court proposal source/view mismatch: {label}")
        frame = root / proposal.get("frame", "")
        if not frame.is_file():
            errors.append(f"court proposal frame is missing: {label}")
        elif proposal.get("image_sha256") != sha256(frame):
            errors.append(f"court proposal image hash mismatch: {label}")
        try:
            width = int(proposal.get("image_size", {}).get("width", 0))
            height = int(proposal.get("image_size", {}).get("height", 0))
            points = validated_proposal_points(proposal.get("points"), width, height)
        except (CurateError, TypeError, ValueError) as exc:
            errors.append(f"invalid court proposal points: {label}: {exc}")
            points = []
        if proposal.get("uncertain_point_count") != sum(
            point.get("uncertain", False) for point in points
        ):
            errors.append(f"court proposal uncertainty count mismatch: {label}")
        producer = proposal.get("producer", {})
        if any(
            not producer.get(field)
            for field in ("tool", "model", "model_version", "prompt_version")
        ):
            errors.append(f"court proposal lacks producer provenance: {label}")
        expected_proposal_id = json_sha256(court_proposal_identity(proposal))[:20]
        if proposal.get("proposal_id") != expected_proposal_id:
            errors.append(f"court proposal identity hash mismatch: {label}")
        review_path = court_proposal_review_path(path)
        if not review_path.exists():
            continue
        review = read_json(review_path, {})
        required_review_fields = {
            "schema_version",
            "target",
            "proposal",
            "proposal_sha256",
            "decision",
            "reviewer",
            "reason",
            "reviewed_at",
            "corrected_sha256",
        }
        if (
            not isinstance(review, dict)
            or not required_review_fields.issubset(review)
            or review.get("schema_version") != SCHEMA_VERSION
            or review.get("target") != "court_proposal_review"
            or review.get("proposal") != label
            or not review.get("reviewer")
            or not review.get("reason")
        ):
            errors.append(f"invalid court proposal review envelope: {review_path}")
            continue
        corrected_hash = review.get("corrected_sha256")
        if corrected_hash is not None and (
            not isinstance(corrected_hash, str)
            or not re.fullmatch(r"[0-9a-f]{64}", corrected_hash)
        ):
            errors.append(f"invalid corrected proposal hash: {review_path}")
        corrected_points = review.get("corrected_points")
        if corrected_hash is None and corrected_points is not None:
            errors.append(f"court proposal correction lacks input hash: {review_path}")
        elif corrected_hash is not None:
            try:
                validated_proposal_points(corrected_points, width, height)
            except (CurateError, TypeError, ValueError) as exc:
                errors.append(f"invalid corrected court proposal points: {label}: {exc}")
            if review.get("decision") == "rejected":
                errors.append(f"rejected court proposal contains correction data: {label}")
        if review.get("decision") not in COURT_PROPOSAL_DECISIONS:
            errors.append(f"invalid court proposal review decision: {review_path}")
        if review.get("proposal_sha256") != sha256(path):
            errors.append(f"court proposal changed after review: {label}")
        if review.get("decision") == "accepted":
            try:
                accepted_points = validated_proposal_points(
                    review.get("accepted_points"), width, height
                )
                if any(point["uncertain"] for point in accepted_points):
                    raise CurateError("accepted points retain uncertainty")
                normalized_dlt(accepted_points)
            except (CurateError, TypeError, ValueError) as exc:
                errors.append(f"invalid accepted court proposal points: {label}: {exc}")
                accepted_points = []
            promoted_value = review.get("promoted_draft")
            promoted = (root / promoted_value).resolve() if isinstance(promoted_value, str) else root
            if (
                not isinstance(promoted_value, str)
                or not promoted.is_relative_to(root.resolve())
                or not promoted.is_file()
            ):
                errors.append(f"accepted court proposal lacks promoted draft: {label}")
            elif review.get("promoted_draft_sha256") != sha256(promoted):
                errors.append(f"promoted court draft changed after review: {label}")
            else:
                draft = read_json(promoted, {})
                expected_points = [
                    {
                        "point_id": point["point_id"],
                        "x": point["x"],
                        "y": point["y"],
                        "source": "manual",
                        "annotation_origin": "model_assisted_human_verified",
                        "model_confidence": point["confidence"],
                    }
                    for point in accepted_points
                ]
                items = draft.get("items", []) if isinstance(draft, dict) else []
                valid_item = (
                    len(items) == 1
                    and items[0].get("item_id") == proposal.get("item_id")
                    and items[0].get("view_state") == proposal.get("view_state")
                    and items[0].get("points") == expected_points
                )
                provenance = draft.get("proposal_provenance", {})
                if (
                    draft.get("schema_version") != SCHEMA_VERSION
                    or draft.get("target") != "court"
                    or draft.get("status") != "draft"
                    or draft.get("source_id") != proposal.get("source_id")
                    or draft.get("view_id") != proposal.get("view_id")
                    or draft.get("annotation_origin")
                    != "model_assisted_human_verified"
                    or provenance.get("proposal") != label
                    or provenance.get("proposal_sha256") != sha256(path)
                    or provenance.get("producer") != proposal.get("producer")
                    or not valid_item
                ):
                    errors.append(f"invalid promoted court draft semantics: {label}")
        elif any(
            field in review
            for field in ("promoted_draft", "promoted_draft_sha256", "accepted_points")
        ):
            errors.append(f"non-accepted court proposal contains promotion data: {label}")
    for path in (paths(root)["annotations"] / "verified/court").glob("*.json"):
        geometry = read_json(path, {})
        if geometry.get("review_status") != "verified":
            errors.append(f"non-verified court geometry in verified directory: {path}")
        if len(geometry.get("canonical_points", [])) != 6:
            errors.append(f"verified court geometry lacks six canonical points: {path}")
        if not geometry.get("allow_inferred_training", False):
            if any(point.get("source") != "manual" for point in geometry.get("training_points", [])):
                errors.append(f"inferred point leaked into strong training labels: {path}")
    for path in (paths(root)["annotations"] / "verified/people").glob("*.json"):
        annotation = read_json(path, {})
        if annotation.get("status") != "verified":
            errors.append(f"non-verified people annotation in verified directory: {path}")
        if not verified_court_path(root, annotation.get("view_id", "")).is_file():
            errors.append(f"people annotation lacks verified court geometry: {path}")
    if errors:
        raise CurateError("validation failed:\n- " + "\n- ".join(errors))
    print(
        f"valid: {len(ids)} source(s), {len(assigned_sources)} split assignment(s), "
        f"{len(assigned_groups)} split group(s)"
    )


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description=__doc__)
    result.add_argument("--dataset-root", help="override datasets/badminton-v1 for isolated tests")
    commands = result.add_subparsers(dest="command", required=True)
    commands.add_parser("status").set_defaults(func=cmd_status)

    record = commands.add_parser("record-search")
    record.add_argument("--purpose", choices=SEARCH_PURPOSES, required=True)
    record.add_argument("--query", required=True)
    record.add_argument("--results", required=True)
    record.add_argument("--refresh", action="store_true")
    record.set_defaults(func=cmd_record_search)

    review = commands.add_parser("review-source")
    review.add_argument("--source-id", required=True)
    review.add_argument("--decision", choices=("accepted", "rejected"), required=True)
    review.add_argument("--capture-context", choices=CAPTURE_CONTEXTS, required=True)
    review.add_argument("--competition-level", choices=COMPETITION_LEVELS, required=True)
    review.add_argument("--purpose", choices=SEARCH_PURPOSES, action="append")
    review.add_argument("--view-id")
    review.add_argument("--split-group-id")
    review.add_argument("--reason", required=True)
    review.add_argument("--reviewer", required=True)
    review.add_argument("--recheck", action="store_true")
    review.set_defaults(func=cmd_review_source)

    preview = commands.add_parser("preview")
    preview.add_argument("--source-id", required=True)
    preview.add_argument("--input")
    preview.add_argument("--window", action="append")
    preview.add_argument("--retry", action="store_true")
    preview.set_defaults(func=cmd_preview)

    rally = commands.add_parser("sample-rally", help="capture a native-frame-rate continuous test clip")
    rally.add_argument("--url", required=True)
    rally.add_argument("--sample-id", required=True)
    rally.add_argument("--group", choices=("official", "personal"), required=True)
    rally.add_argument("--match-type", choices=("singles", "doubles"), default="singles")
    rally.add_argument("--view-id", required=True)
    rally.add_argument("--window", required=True)
    rally.add_argument("--input")
    rally.add_argument("--metadata", help="reuse freshly resolved yt-dlp public formats")
    rally.add_argument("--device-evidence", default="unknown")
    rally.set_defaults(func=lambda args: __import__("rally").sample(args))

    rally_review = commands.add_parser("review-rally", help="record visual clip suitability, not rally labels")
    rally_review.add_argument("--sample-id", required=True)
    rally_review.add_argument("--decision", choices=("accepted", "rejected"), required=True)
    rally_review.add_argument("--reviewer", required=True)
    rally_review.add_argument("--reason", required=True)
    rally_review.add_argument("--phone-confirmed", action="store_true")
    rally_review.set_defaults(func=lambda args: __import__("rally").review(args))

    commands.add_parser("rally-status").set_defaults(func=lambda args: __import__("rally").status(args))

    court = commands.add_parser("sample-court")
    court.add_argument("--source-id", required=True)
    court.add_argument("--view-id", required=True)
    court.add_argument("--scene", choices=COURT_SCENES, required=True)
    court.add_argument("--window", required=True)
    court.add_argument("--input")
    court.set_defaults(func=cmd_sample_court)

    people = commands.add_parser("sample-people")
    people.add_argument("--source-id", required=True)
    people.add_argument("--view-id", required=True)
    people.add_argument("--scene", choices=PEOPLE_SCENES, required=True)
    people.add_argument("--segment", required=True)
    people.add_argument("--input")
    people.set_defaults(func=cmd_sample_people)

    build = commands.add_parser("build-cvat")
    build.add_argument("--target", choices=("court", "people"), required=True)
    build.add_argument("--source-id", required=True)
    build.add_argument("--view-id", required=True)
    build.set_defaults(func=cmd_build_cvat)

    imported = commands.add_parser("import-cvat")
    imported.add_argument("--target", choices=("court", "people"), required=True)
    imported.add_argument("--source-id", required=True)
    imported.add_argument("--view-id", required=True)
    imported.add_argument("--export", required=True)
    imported.add_argument("--status", choices=("draft", "verified"))
    imported.add_argument("--reviewer", required=True)
    imported.set_defaults(func=cmd_import_cvat)

    propose_court = commands.add_parser("record-court-proposal")
    propose_court.add_argument("--source-id", required=True)
    propose_court.add_argument("--view-id", required=True)
    propose_court.add_argument("--frame", required=True)
    propose_court.add_argument("--proposal", required=True)
    propose_court.add_argument("--producer", required=True)
    propose_court.add_argument("--model", required=True)
    propose_court.add_argument("--model-version", required=True)
    propose_court.add_argument("--prompt-version", required=True)
    propose_court.set_defaults(func=cmd_record_court_proposal)

    render_proposal = commands.add_parser("render-court-proposal")
    render_proposal.add_argument("--proposal", required=True)
    render_proposal.set_defaults(func=cmd_render_court_proposal)

    review_proposal = commands.add_parser("review-court-proposal")
    review_proposal.add_argument("--proposal", required=True)
    review_proposal.add_argument(
        "--decision", choices=COURT_PROPOSAL_DECISIONS, required=True
    )
    review_proposal.add_argument("--reviewer", required=True)
    review_proposal.add_argument("--reason", required=True)
    review_proposal.add_argument("--corrected")
    review_proposal.add_argument("--replace", action="store_true")
    review_proposal.add_argument("--recheck", action="store_true")
    review_proposal.set_defaults(func=cmd_review_court_proposal)

    fit = commands.add_parser("fit-court")
    fit.add_argument("--source-id", required=True)
    fit.add_argument("--view-id", required=True)
    fit.add_argument("--controls", required=True)
    fit.add_argument("--item-id")
    fit.add_argument("--frame", required=True)
    fit.set_defaults(func=cmd_fit_court)

    review_fit = commands.add_parser("review-court-fit")
    review_fit.add_argument("--view-id", required=True)
    review_fit.add_argument("--decision", choices=("accepted", "rejected"), required=True)
    review_fit.add_argument("--reason", required=True)
    review_fit.add_argument("--reviewer", required=True)
    review_fit.add_argument("--allow-inferred-training", action="store_true")
    review_fit.add_argument("--recheck", action="store_true")
    review_fit.set_defaults(func=cmd_review_court_fit)

    commands.add_parser("validate").set_defaults(func=cmd_validate)
    return result


def main() -> int:
    # Helpers must share this module's exception type when invoked as a script.
    sys.modules["curate"] = sys.modules[__name__]
    args = parser().parse_args()
    try:
        args.func(args)
        return 0
    except (CurateError, json.JSONDecodeError, OSError, zipfile.BadZipFile) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
