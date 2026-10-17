from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
import zipfile
from argparse import Namespace
from pathlib import Path
from unittest import mock


SCRIPT = Path(__file__).parents[1] / "scripts/curate.py"
SPEC = importlib.util.spec_from_file_location("curate", SCRIPT)
assert SPEC and SPEC.loader
curate = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(curate)


class CurateTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name) / "dataset"
        self.results = Path(self.temp.name) / "results.json"
        self.results.write_text(
            json.dumps(
                [
                    {"url": "https://www.bilibili.com/video/BV1abc123/", "title": "club"},
                    {
                        "url": "https://m.bilibili.com/video/BV1abc123?share=1",
                        "title": "duplicate",
                    },
                    {"url": "https://youtu.be/example", "title": "personal"},
                ]
            ),
            encoding="utf-8",
        )

    def tearDown(self) -> None:
        self.temp.cleanup()

    def run_cli(self, *args: str, expected: int = 0) -> subprocess.CompletedProcess[str]:
        completed = subprocess.run(
            [sys.executable, str(SCRIPT), "--dataset-root", str(self.root), *args],
            text=True,
            capture_output=True,
        )
        self.assertEqual(expected, completed.returncode, completed.stderr + completed.stdout)
        return completed

    def seed_and_accept(self) -> None:
        self.run_cli(
            "record-search",
            "--purpose",
            "court",
            "--query",
            " Club   Match ",
            "--results",
            str(self.results),
        )
        self.run_cli(
            "review-source",
            "--source-id",
            "bilibili:BV1abc123",
            "--decision",
            "accepted",
            "--capture-context",
            "club",
            "--competition-level",
            "amateur",
            "--purpose",
            "court",
            "--purpose",
            "people",
            "--view-id",
            "club-a-camera-1",
            "--split-group-id",
            "club-a",
            "--reason",
            "fixed amateur full-court view",
            "--reviewer",
            "tester",
        )

    def make_video(self, duration: int = 40, size: str = "1280x720") -> Path:
        ffmpeg = curate.find_ffmpeg()
        video = Path(self.temp.name) / f"synthetic-{duration}-{size}.mp4"
        subprocess.run(
            [
                ffmpeg,
                "-hide_banner",
                "-loglevel",
                "error",
                "-f",
                "lavfi",
                "-i",
                f"testsrc2=size={size}:rate=10",
                "-t",
                str(duration),
                "-c:v",
                "libx264",
                "-pix_fmt",
                "yuv420p",
                "-y",
                str(video),
            ],
            check=True,
        )
        return video

    def court_export(self) -> Path:
        export = Path(self.temp.name) / "court-datumaro.zip"
        points = [
            ("far_left_short_service", 100.0, 72.0),
            ("far_right_short_service", 514.4, 72.0),
            ("near_left_short_service", 100.0, 468.0),
            ("near_right_short_service", 514.4, 468.0),
        ]
        document = {
            "categories": {
                "label": {
                    "labels": [
                        {"name": "court_control_point"},
                        {"name": "view_state"},
                    ]
                }
            },
            "items": [
                {
                    "id": "frame-1",
                    "annotations": [
                        *[
                            {
                                "id": index,
                                "type": "points",
                                "label_id": 0,
                                "points": [x, y],
                                "attributes": {"point_id": point_id},
                            }
                            for index, (point_id, x, y) in enumerate(points)
                        ],
                        {
                            "id": 10,
                            "type": "label",
                            "label_id": 1,
                            "attributes": {"state": "court_partial"},
                        },
                    ],
                }
            ],
        }
        with zipfile.ZipFile(export, "w") as archive:
            archive.writestr("annotations/default.json", json.dumps(document))
        return export

    def prepare_verified_court(self, video: Path) -> Path:
        self.run_cli(
            "sample-court",
            "--source-id",
            "bilibili:BV1abc123",
            "--view-id",
            "club-a-camera-1",
            "--scene",
            "court_complete",
            "--window",
            "0:8",
            "--input",
            str(video),
        )
        frames = sorted((self.root / "local/frames/court/club-a-camera-1").glob("*.jpg"))
        self.assertEqual(3, len(frames))
        export = self.court_export()
        imported = self.run_cli(
            "import-cvat",
            "--target",
            "court",
            "--source-id",
            "bilibili:BV1abc123",
            "--view-id",
            "club-a-camera-1",
            "--export",
            str(export),
            "--reviewer",
            "tester",
        )
        controls = Path(imported.stdout.strip())
        self.run_cli(
            "fit-court",
            "--source-id",
            "bilibili:BV1abc123",
            "--view-id",
            "club-a-camera-1",
            "--controls",
            str(controls),
            "--item-id",
            "frame-1",
            "--frame",
            str(frames[0]),
        )
        draft = json.loads(
            (self.root / "annotations/draft/court/club-a-camera-1.json").read_text()
        )
        self.assertEqual("pending_review", draft["review_status"])
        self.assertEqual(6, len(draft["canonical_points"]))
        self.assertTrue(
            any(point["visibility"] == "outside" for point in draft["canonical_points"])
        )
        self.run_cli(
            "review-court-fit",
            "--view-id",
            "club-a-camera-1",
            "--decision",
            "accepted",
            "--reason",
            "overlay matches visible lines",
            "--reviewer",
            "tester",
        )
        verified = self.root / "annotations/verified/court/club-a-camera-1.json"
        geometry = json.loads(verified.read_text())
        self.assertEqual("verified", geometry["review_status"])
        self.assertFalse(geometry["allow_inferred_training"])
        self.assertTrue(
            all(point["source"] == "manual" for point in geometry["training_points"])
        )
        status = json.loads(self.run_cli("status").stdout)
        self.assertEqual(0, status["pending_court_fit_reviews"])
        return verified

    def court_proposal(self, frame: Path, uncertain: bool = False) -> Path:
        proposal = Path(self.temp.name) / (
            "court-proposal-uncertain.json" if uncertain else "court-proposal.json"
        )
        proposal.write_text(
            json.dumps(
                {
                    "item_id": frame.stem,
                    "points": [
                        {
                            "point_id": "far_left_short_service",
                            "x": 100,
                            "y": 72,
                            "confidence": 0.92,
                            "uncertain": uncertain,
                        },
                        {
                            "point_id": "far_right_short_service",
                            "x": 514,
                            "y": 72,
                            "confidence": 0.91,
                            "uncertain": False,
                        },
                        {
                            "point_id": "near_left_short_service",
                            "x": 100,
                            "y": 468,
                            "confidence": 0.89,
                            "uncertain": False,
                        },
                        {
                            "point_id": "near_right_short_service",
                            "x": 514,
                            "y": 468,
                            "confidence": 0.9,
                            "uncertain": False,
                        },
                    ],
                }
            ),
            encoding="utf-8",
        )
        return proposal

    def test_search_cache_is_scoped_by_purpose_and_dedupes_urls(self) -> None:
        self.run_cli(
            "record-search",
            "--purpose",
            "court",
            "--query",
            "same query",
            "--results",
            str(self.results),
        )
        self.run_cli(
            "record-search",
            "--purpose",
            "people",
            "--query",
            "same query",
            "--results",
            str(self.results),
        )
        sources = json.loads((self.root / "manifests/sources.json").read_text())
        self.assertEqual(2, len(sources["sources"]))
        first = next(item for item in sources["sources"] if item["platform"] == "bilibili")
        self.assertEqual(["court", "people"], first["purposes"])
        cache = json.loads((self.root / "manifests/search-cache.json").read_text())
        self.assertEqual(2, len(cache["queries"]))
        self.run_cli(
            "record-search",
            "--purpose",
            "court",
            "--query",
            " same  query ",
            "--results",
            str(self.results),
            expected=2,
        )

    def test_preview_windows_adapt_to_duration(self) -> None:
        self.assertEqual([(0.0, 10.0)], curate.automatic_preview_windows(10))
        self.assertEqual(2, len(curate.automatic_preview_windows(20)))
        self.assertEqual(3, len(curate.automatic_preview_windows(100)))

    def test_bilibili_capture_is_bounded_and_impersonated(self) -> None:
        source = {
            "platform": "bilibili",
            "canonical_url": "https://www.bilibili.com/video/BV1abc123/",
        }
        command = curate.yt_dlp_section_command(source, [(10, 18)], Path("output.mp4"))
        self.assertIn("--download-sections", command)
        self.assertIn("*10-18", command)
        self.assertIn("--impersonate", command)
        self.assertIn("chrome", command)

    def test_preview_failure_is_cached(self) -> None:
        self.seed_and_accept()
        args = Namespace(
            dataset_root=str(self.root),
            source_id="bilibili:BV1abc123",
            retry=False,
        )
        with mock.patch.object(
            curate, "_run_preview", side_effect=curate.CurateError("no public formats")
        ) as preview:
            with self.assertRaises(curate.CurateError):
                curate.cmd_preview(args)
            with self.assertRaisesRegex(curate.CurateError, "failure is cached"):
                curate.cmd_preview(args)
            self.assertEqual(1, preview.call_count)
        source = source_by_id(
            json.loads((self.root / "manifests/sources.json").read_text()),
            "bilibili:BV1abc123",
        )
        self.assertIn("no public formats", source["preview_failure"]["error"])

    def test_model_court_proposal_requires_human_review_and_preserves_raw_output(
        self,
    ) -> None:
        self.seed_and_accept()
        video = self.make_video(duration=8)
        self.run_cli(
            "sample-court",
            "--source-id",
            "bilibili:BV1abc123",
            "--view-id",
            "club-a-camera-1",
            "--scene",
            "court_partial",
            "--window",
            "0:8",
            "--input",
            str(video),
        )
        frame = next((self.root / "local/frames/court/club-a-camera-1").glob("*.jpg"))
        proposal_input = self.court_proposal(frame)
        recorded = self.run_cli(
            "record-court-proposal",
            "--source-id",
            "bilibili:BV1abc123",
            "--view-id",
            "club-a-camera-1",
            "--frame",
            str(frame),
            "--proposal",
            str(proposal_input),
            "--producer",
            "claude-code",
            "--model",
            "vision-model",
            "--model-version",
            "2026-07",
            "--prompt-version",
            "court-points-v1",
        )
        proposal_path = Path(recorded.stdout.strip())
        original_hash = curate.sha256(proposal_path)
        draft_path = self.root / "annotations/draft/court-controls/club-a-camera-1.json"
        self.assertFalse(draft_path.exists())
        overlay = self.run_cli(
            "render-court-proposal",
            "--proposal",
            str(proposal_path),
        )
        self.assertTrue(Path(overlay.stdout.strip()).is_file())
        self.assertEqual(original_hash, curate.sha256(proposal_path))

        needs_review_correction = self.court_proposal(frame, uncertain=True)
        self.run_cli(
            "review-court-proposal",
            "--proposal",
            str(proposal_path),
            "--decision",
            "needs_review",
            "--reviewer",
            "tester",
            "--reason",
            "visual confirmation required",
            "--corrected",
            str(needs_review_correction),
        )
        self.assertFalse(draft_path.exists())
        needs_review = json.loads(
            proposal_path.with_suffix(".review.json").read_text()
        )
        self.assertTrue(needs_review["corrected_sha256"])
        self.assertEqual(4, len(needs_review["corrected_points"]))
        self.assertTrue(
            any(point["uncertain"] for point in needs_review["corrected_points"])
        )
        self.run_cli(
            "review-court-proposal",
            "--proposal",
            str(proposal_path),
            "--decision",
            "accepted",
            "--reviewer",
            "tester",
            "--reason",
            "all four points visually confirmed",
            "--recheck",
        )
        self.assertEqual(original_hash, curate.sha256(proposal_path))
        draft = json.loads(draft_path.read_text())
        self.assertEqual("model_assisted_human_verified", draft["annotation_origin"])
        self.assertTrue(
            all(point["source"] == "manual" for point in draft["items"][0]["points"])
        )
        status = json.loads(self.run_cli("status").stdout)
        self.assertEqual(10, status["targets"]["pipeline_pilot"]["verified_views"])
        self.assertEqual(
            30,
            status["targets"]["initial_model_baseline"]["verified_views_minimum"],
        )
        self.assertEqual(1, status["court_proposals"]["decisions"]["accepted"])
        self.assertEqual(0, status["verified_views"])
        self.assertEqual(10, status["pilot_gaps"]["independent_views"])
        self.assertEqual(30, status["baseline_gaps"]["independent_views"])
        self.assertEqual(12, status["baseline_gaps"]["split_groups"])
        self.run_cli("validate")

        review_path = proposal_path.with_suffix(".review.json")
        review = json.loads(review_path.read_text())
        review_without_reviewer = dict(review)
        review_without_reviewer.pop("reviewer")
        review_path.write_text(json.dumps(review_without_reviewer), encoding="utf-8")
        invalid_review = self.run_cli("validate", expected=2)
        self.assertIn("invalid court proposal review envelope", invalid_review.stderr)
        review_path.write_text(json.dumps(review), encoding="utf-8")

        draft["items"][0]["points"][0]["source"] = "geometry_inferred"
        draft_path.write_text(json.dumps(draft), encoding="utf-8")
        review["promoted_draft_sha256"] = curate.sha256(draft_path)
        review_path.write_text(json.dumps(review), encoding="utf-8")
        invalid_promotion = self.run_cli("validate", expected=2)
        self.assertIn("invalid promoted court draft semantics", invalid_promotion.stderr)

    def test_uncertain_model_point_cannot_be_promoted(self) -> None:
        self.seed_and_accept()
        video = self.make_video(duration=8)
        self.run_cli(
            "sample-court",
            "--source-id",
            "bilibili:BV1abc123",
            "--view-id",
            "club-a-camera-1",
            "--scene",
            "court_partial",
            "--window",
            "0:8",
            "--input",
            str(video),
        )
        frame = next((self.root / "local/frames/court/club-a-camera-1").glob("*.jpg"))
        recorded = self.run_cli(
            "record-court-proposal",
            "--source-id",
            "bilibili:BV1abc123",
            "--view-id",
            "club-a-camera-1",
            "--frame",
            str(frame),
            "--proposal",
            str(self.court_proposal(frame, uncertain=True)),
            "--producer",
            "trae-cli",
            "--model",
            "vision-model",
            "--model-version",
            "2026-07",
            "--prompt-version",
            "court-points-v1",
        )
        self.run_cli(
            "review-court-proposal",
            "--proposal",
            recorded.stdout.strip(),
            "--decision",
            "accepted",
            "--reviewer",
            "tester",
            "--reason",
            "must fail",
            expected=2,
        )
        status = json.loads(self.run_cli("status").stdout)
        self.assertEqual(1, status["court_proposals"]["with_uncertain_points"])
        self.assertEqual(1, status["court_proposals"]["decisions"]["pending"])
        proposal_path = Path(recorded.stdout.strip())
        proposal = json.loads(proposal_path.read_text())
        proposal["points"][0]["x"] += 1
        proposal_path.write_text(json.dumps(proposal), encoding="utf-8")
        invalid_identity = self.run_cli("validate", expected=2)
        self.assertIn("court proposal identity hash mismatch", invalid_identity.stderr)

    def test_partial_court_fit_and_people_cvat_round_trip(self) -> None:
        self.seed_and_accept()
        video = self.make_video()
        self.prepare_verified_court(video)

        court_bundle = self.run_cli(
            "build-cvat",
            "--target",
            "court",
            "--source-id",
            "bilibili:BV1abc123",
            "--view-id",
            "club-a-camera-1",
        )
        with zipfile.ZipFile(Path(court_bundle.stdout.strip())) as archive:
            labels = json.loads(archive.read("labels.json"))
        self.assertEqual("court_control_point", labels["labels"][0]["name"])

        self.run_cli(
            "sample-people",
            "--source-id",
            "bilibili:BV1abc123",
            "--view-id",
            "club-a-camera-1",
            "--scene",
            "extra_people",
            "--segment",
            "10:20",
            "--input",
            str(video),
        )
        people_bundle = self.run_cli(
            "build-cvat",
            "--target",
            "people",
            "--source-id",
            "bilibili:BV1abc123",
            "--view-id",
            "club-a-camera-1",
        )
        with zipfile.ZipFile(Path(people_bundle.stdout.strip())) as archive:
            labels = json.loads(archive.read("labels.json"))
        self.assertEqual("person", labels["labels"][0]["name"])

        export = Path(self.temp.name) / "people-datumaro.zip"
        document = {
            "categories": {"label": {"labels": [{"name": "person"}]}},
            "items": [
                {
                    "id": "frame-1",
                    "annotations": [
                        {
                            "id": 1,
                            "type": "bbox",
                            "label_id": 0,
                            "bbox": [1, 2, 3, 4],
                            "attributes": {
                                "track_id": 7,
                                "role": "participant",
                                "court_side": "near",
                                "occluded": False,
                                "outside": False,
                            },
                        }
                    ],
                }
            ],
        }
        with zipfile.ZipFile(export, "w") as archive:
            archive.writestr("annotations/default.json", json.dumps(document))
        self.run_cli(
            "import-cvat",
            "--target",
            "people",
            "--source-id",
            "bilibili:BV1abc123",
            "--view-id",
            "club-a-camera-1",
            "--export",
            str(export),
            "--status",
            "verified",
            "--reviewer",
            "tester",
        )
        self.run_cli("validate")

    def test_people_sampling_requires_verified_court(self) -> None:
        self.seed_and_accept()
        video = self.make_video(duration=12)
        self.run_cli(
            "sample-people",
            "--source-id",
            "bilibili:BV1abc123",
            "--view-id",
            "club-a-camera-1",
            "--scene",
            "clean",
            "--segment",
            "0:10",
            "--input",
            str(video),
            expected=2,
        )

    def test_degenerate_fit_stays_unresolved(self) -> None:
        self.seed_and_accept()
        video = self.make_video(duration=8)
        frame = Path(self.temp.name) / "frame.jpg"
        curate.extract_frame(video, 1, frame)
        controls = Path(self.temp.name) / "collinear.json"
        controls.write_text(
            json.dumps(
                {
                    "points": [
                        {"point_id": "far_left_baseline", "x": 10, "y": 10},
                        {"point_id": "far_center_baseline", "x": 20, "y": 10},
                        {"point_id": "far_right_baseline", "x": 30, "y": 10},
                        {"point_id": "net_left", "x": 40, "y": 10},
                    ]
                }
            ),
            encoding="utf-8",
        )
        self.run_cli(
            "fit-court",
            "--source-id",
            "bilibili:BV1abc123",
            "--view-id",
            "club-a-camera-1",
            "--controls",
            str(controls),
            "--frame",
            str(frame),
        )
        draft = json.loads(
            (self.root / "annotations/draft/court/club-a-camera-1.json").read_text()
        )
        self.assertEqual("court_partial_unresolved", draft["scene_state"])
        self.assertEqual([], draft["canonical_points"])
        self.run_cli(
            "review-court-fit",
            "--view-id",
            "club-a-camera-1",
            "--decision",
            "accepted",
            "--reason",
            "should fail",
            "--reviewer",
            "tester",
            expected=2,
        )

    def test_validate_rejects_split_group_leakage(self) -> None:
        self.seed_and_accept()
        second = json.loads((self.root / "manifests/sources.json").read_text())
        youtube = next(item for item in second["sources"] if item["platform"] == "youtube")
        youtube.update(
            {
                "status": "accepted",
                "capture_context": "personal",
                "competition_level": "amateur",
                "purposes": ["court"],
                "view_id": "club-a-camera-2",
                "split_group_id": "club-a",
            }
        )
        (self.root / "manifests/sources.json").write_text(
            json.dumps(second), encoding="utf-8"
        )
        splits = {"train": ["bilibili:BV1abc123"], "validation": [], "test": ["youtube:example"]}
        path = self.root / "manifests/splits.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(splits), encoding="utf-8")
        self.run_cli("validate", expected=2)

    def test_preview_accepts_low_resolution_and_cleans_raw_media(self) -> None:
        self.seed_and_accept()
        video = self.make_video(duration=20, size="640x360")
        self.run_cli(
            "preview",
            "--source-id",
            "bilibili:BV1abc123",
            "--input",
            str(video),
        )
        source = source_by_id(
            json.loads((self.root / "manifests/sources.json").read_text()),
            "bilibili:BV1abc123",
        )
        self.assertEqual(360, source["media_metadata"]["height"])
        self.assertEqual(2, len(source["artifacts"]["previews"]) - 1)
        self.assertFalse(list(Path(self.temp.name).rglob("raw-*.mp4")))


    def native_video(self, fps: int) -> Path:
        video = Path(self.temp.name) / f"native-{fps}.mp4"
        subprocess.run([
            curate.find_ffmpeg(), "-v", "error", "-f", "lavfi", "-i",
            f"color=c=green:s=320x180:r={fps}:d=60", "-c:v", "libx264",
            "-preset", "ultrafast", "-y", str(video),
        ], check=True)
        return video

    def collect_native(self, fps: int, expected: int) -> dict:
        video = self.native_video(fps)
        self.run_cli(
            "sample-rally", "--url", "https://www.bilibili.com/video/BVnative/",
            "--sample-id", "native", "--group", "personal", "--view-id", "one-view",
            "--window", "0:60", "--input", str(video), expected=expected,
        )
        return json.loads((self.root / "manifests/rally-samples.json").read_text())["samples"][0]

    def test_native_rate_complete_decode_and_separate_review(self) -> None:
        self.seed_and_accept()
        source_path = self.root / "manifests/sources.json"
        original = source_path.read_bytes()
        result = self.collect_native(25, 0)
        self.assertEqual(25, result["media"]["fps"])
        self.assertAlmostEqual(60, result["media"]["duration_s"], places=1)
        self.assertTrue(result["media"]["decode_complete"])
        self.assertEqual("needs_visual_review", result["status"])
        self.run_cli("review-rally", "--sample-id", "native", "--decision", "accepted",
                     "--reviewer", "agent", "--reason", "Synthetic fixture", "--phone-confirmed", expected=2)
        self.assertEqual(original, source_path.read_bytes())

    def test_low_rate_is_retained_as_failed_not_upsampled(self) -> None:
        result = self.collect_native(10, 2)
        self.assertEqual(10, result["media"]["fps"])
        self.assertEqual("failed", result["status"])
        self.run_cli("review-rally", "--sample-id", "native", "--decision", "accepted",
                     "--reviewer", "agent", "--reason", "Must reject", expected=2)


def source_by_id(document: dict, source_id: str) -> dict:
    return next(item for item in document["sources"] if item["source_id"] == source_id)


if __name__ == "__main__":
    unittest.main()
