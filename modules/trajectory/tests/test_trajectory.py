import json
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest

from modules.trajectory import analyzer
from modules.trajectory.court import _euclidean_camera, transform


FIXTURES = json.loads((Path(__file__).with_name("real-observation-regressions.json")).read_text())


def test_camera_uses_observed_net_height_without_image_vertical_posts():
    # Synthetic geometry checks camera mathematics only, not video accuracy.
    focal = 2000.
    k = np.array([[focal, 0, 960], [0, focal, 540], [0, 0, 1]])
    rotation = np.array([[1, 0, 0], [0, .4, -np.sqrt(.84)], [0, -np.sqrt(.84), -.4]])
    truth = k @ np.column_stack((rotation, [-2.59, 1., 30.]))
    homography = truth[:, [0, 1, 3]]
    net_world = np.array([[-.46, 6.7, 1.55, 1], [5.64, 6.7, 1.55, 1]])
    net = net_world @ truth.T
    net = net[:, :2] / net[:, 2:3]
    projection, diagnostic = _euclidean_camera(homography, net.ravel())
    assert projection is not None, diagnostic
    assert diagnostic["focal_px"] == pytest.approx(focal, rel=.01)
    raised = np.array([[0, 3, 2, 1], [5, 11, 3, 1]])
    actual, expected = raised @ projection.T, raised @ truth.T
    assert np.max(abs(actual[:, :2] / actual[:, 2:] - expected[:, :2] / expected[:, 2:])) < 1
    bases = transform(homography, net_world[:, :2])
    assert np.max(abs(bases[:, 0] - net[:, 0])) > 2


def test_real_gap_around_contact_does_not_merge_both_opponents_flights():
    saved = FIXTURES["m1-a2-01-20261019-workerfix"]
    players = analyzer._players(saved["people"], np.linalg.inv(saved["image_from_court"]))
    hits, _ = analyzer._hits(saved["rows"], players)
    assert any(abs(hit["timestamp_ms"] - 50280) <= 40 and hit["player"]["side"] == "near" for hit in hits)


def test_real_landing_dwell_is_not_a_new_racket_hit():
    saved = FIXTURES["m1-short-a1-01-20261015"]
    players = analyzer._players(saved["people"], np.linalg.inv(saved["image_from_court"]))
    hits, valid = analyzer._hits(saved["rows"], players)
    assert not any(hit["timestamp_ms"] >= 9240 for hit in hits)
    landing = analyzer._detected_landing(valid, np.linalg.inv(saved["image_from_court"]), 9600)
    assert landing is not None
    assert np.isfinite(landing).all()


def test_missing_ball_points_and_height_reference_remain_unresolved():
    assert analyzer._landing([], [2, 10], None)[1]["reason"] == "net_height_reference_unavailable"
    assert analyzer._landing([], [2, 10], np.eye(3, 4))[1]["reason"] == "insufficient_flight_observations"
    assert analyzer._detected_landing([], np.eye(3), 1000) is None


def test_offline_analysis_excludes_next_hit_frame_and_prioritizes_visible_final_landing(monkeypatch, tmp_path):
    source, weight = tmp_path / "video.mp4", tmp_path / "ball.pt"
    source.write_bytes(b"video")
    weight.write_bytes(b"model")
    rows = [dict(timestamp_ms=t, x=100., y=100., confidence=.9) for t in (0, 40, 80, 120, 160)]
    meta = dict(reference_size=[1920, 1080], model_sha256=analyzer.file_sha256(weight), source_sha256="source")
    monkeypatch.setattr(analyzer, "_load_observations", lambda *args: (rows, meta))
    court = dict(image_from_court=np.eye(3).tolist(), diagnostics={})
    monkeypatch.setattr(analyzer, "_video_evidence", lambda *args: (court, []))
    monkeypatch.setattr(analyzer, "_players", lambda *args: [])
    hit = lambda t, side: dict(timestamp_ms=t, player=dict(xy=[2., 3. if side == "far" else 10.], side=side), score=1., reach=0.)
    monkeypatch.setattr(analyzer, "_hits", lambda *args: ([hit(0, "near"), hit(80, "far")], rows))
    calls = []
    def fit(flight, start, projection, receiver):
        calls.append([row["timestamp_ms"] for row in flight])
        return None, dict(reason="test_missing_height")
    monkeypatch.setattr(analyzer, "_landing", fit)
    monkeypatch.setattr(analyzer, "_detected_landing", lambda *args: [3., 12.])
    result = analyzer.analyze(source, SimpleNamespace(), [dict(start_ms=0, end_ms=160)], tmp_path / "points.jsonl", {"ball_track.pt": weight}, tmp_path, lambda *args: None)
    assert calls == [[0, 40]]
    assert [shot["end_kind"] for shot in result["shots"]] == ["next_hit", "detected_landing"]
    assert result["shots"][-1]["end_xy"] == [3., 12.]


def test_analyze_applies_court_constraints_before_saving_and_counts(monkeypatch, tmp_path):
    source, weight = tmp_path / "video.mp4", tmp_path / "ball.pt"
    source.write_bytes(b"video")
    weight.write_bytes(b"model")
    rows = [dict(timestamp_ms=t, x=100., y=100., confidence=.9) for t in (0, 40, 80, 120)]
    meta = dict(reference_size=[1920, 1080], model_sha256=analyzer.file_sha256(weight), source_sha256="source")
    monkeypatch.setattr(analyzer, "_load_observations", lambda *args: (rows, meta))
    monkeypatch.setattr(analyzer, "_video_evidence", lambda *args: (dict(image_from_court=np.eye(3).tolist(), diagnostics={}), []))
    player_tracks = [
        dict(timestamp_ms=0., players=[dict(side="near", xy=[2., 10.])]),
        dict(timestamp_ms=80., players=[dict(side="far", xy=[3., 2.])]),
    ]
    monkeypatch.setattr(analyzer, "_players", lambda *args: player_tracks)
    def hit(timestamp, xy, side):
        return dict(timestamp_ms=timestamp, player=dict(xy=xy, side=side), score=1., reach=0.)
    monkeypatch.setattr(analyzer, "_hits", lambda *args: ([hit(0, [2., 2.], "near"), hit(80, [3., 10.], "far")], rows))
    monkeypatch.setattr(analyzer, "_landing", lambda flight, start, projection, receiver: (
        ([2., 3.] if start[1] < 6.7 else None), dict(reason="test_endpoint")))
    monkeypatch.setattr(analyzer, "_detected_landing", lambda *args: None)

    result = analyzer.analyze(source, SimpleNamespace(), [dict(start_ms=0, end_ms=120)], tmp_path / "points.jsonl",
                              {"ball_track.pt": weight}, tmp_path, lambda *args: None)

    assert result["shots"][0]["start_xy"] == [2., 10.]
    assert result["shots"][0]["end_kind"] == "predicted_landing"
    assert result["shots"][0]["diagnostics"]["court_constraint"]["start_estimate"]["method"] == "exact"
    assert result["diagnostics"]["court_constraint_actions"] == {"replace_end_with_next_hit": 0, "hide_arrow": 0}
    assert result["diagnostics"]["court_constraint_start_estimates"] == 1
    assert result["diagnostics"]["court_constraint_start_repairs"] == 1
    saved = json.loads((tmp_path / "shot-paths.json").read_text())
    assert saved["shots"] == result["shots"]
    assert saved["diagnostics"]["end_kind_counts"]["predicted_landing"] == 1


def test_real_long_gap_does_not_create_fake_opponent_contact():
    saved = FIXTURES["m1-a2-01-20261019-workerfix"]
    players = analyzer._players(saved["late_people"], np.linalg.inv(saved["image_from_court"]))
    hits, _ = analyzer._hits(saved["late_rows"], players)
    times = [hit["timestamp_ms"] for hit in hits]
    assert 79880 not in times and 84800 not in times
    assert 81080 in times and 82320 in times and 83080 in times and 84920 in times


@pytest.mark.parametrize("declared_count", [4200, 2421])
def test_truncated_log_cannot_reuse_original_complete_manifest(tmp_path, declared_count):
    source = tmp_path / "video.mp4"
    source.write_bytes(b"source")
    points = tmp_path / "points.jsonl"
    actual = FIXTURES["m1-short-a1-01-20261015"]["rows"][0]
    points.write_text(json.dumps(actual) + "\n")
    meta = dict(complete=True, source_sha256=analyzer.file_sha256(source),
                frame_count=declared_count, last_timestamp_ms=167960)
    points.with_suffix(".meta.json").write_text(json.dumps(meta))
    with pytest.raises(ValueError, match="行数或末时间"):
        analyzer._load_observations(points, source)


def test_log_last_timestamp_must_match_manifest(tmp_path):
    source = tmp_path / "video.mp4"
    source.write_bytes(b"source")
    points = tmp_path / "points.jsonl"
    rows = [dict(timestamp_ms=0), dict(timestamp_ms=40)]
    points.write_text("\n".join(json.dumps(row) for row in rows))
    meta = dict(complete=True, source_sha256=analyzer.file_sha256(source),
                frame_count=2, last_timestamp_ms=80)
    points.with_suffix(".meta.json").write_text(json.dumps(meta))
    with pytest.raises(ValueError, match="行数或末时间"):
        analyzer._load_observations(points, source)
    meta["last_timestamp_ms"] = 40
    points.with_suffix(".meta.json").write_text(json.dumps(meta))
    assert analyzer._load_observations(points, source)[0] == rows


def test_real_a1_occluded_return_does_not_erase_next_near_contact():
    saved = FIXTURES["m1-short-a1-01-20261015"]
    hits, _ = analyzer._hits(saved["round2_rows"], saved["round2_players"])
    assert any(25160 < hit["timestamp_ms"] < 25560 and hit["player"]["side"] == "far" for hit in hits)
    assert any(26320 <= hit["timestamp_ms"] <= 26360 and hit["player"]["side"] == "near" for hit in hits)
    assert all(hit["timestamp_ms"] in {row["timestamp_ms"] for row in saved["round2_rows"]} for hit in hits)


def test_real_a2_stalled_track_and_occluded_net_exchange_are_separate():
    saved = FIXTURES["m1-a2-01-20261019-workerfix"]
    hits, _ = analyzer._hits(saved["round2_rows"], saved["round2_players"])
    actual = {(hit["timestamp_ms"], hit["player"]["side"]) for hit in hits}
    assert {(74320, "far"), (75240, "near")} <= actual
    assert any(abs(t - 76120) <= 40 and side == "far" for t, side in actual)
    assert not any(hit["timestamp_ms"] == 75840 for hit in hits)


def test_real_a1_long_unobserved_flight_clears_previous_arrow(monkeypatch, tmp_path):
    saved = FIXTURES["m1-short-a1-01-20261015"]
    source, weight = tmp_path / "video.mp4", tmp_path / "ball.pt"
    source.write_bytes(b"video")
    weight.write_bytes(b"model")
    meta = dict(reference_size=[1920, 1080], model_sha256=analyzer.file_sha256(weight), source_sha256="source")
    monkeypatch.setattr(analyzer, "_load_observations", lambda *args: (saved["round2_rows"], meta))
    court = dict(image_from_court=saved["image_from_court"], diagnostics={})
    monkeypatch.setattr(analyzer, "_video_evidence", lambda *args: (court, []))
    monkeypatch.setattr(analyzer, "_players", lambda *args: saved["round2_players"])
    monkeypatch.setattr(analyzer, "_landing", lambda *args: (None, dict(reason="test_missing_height")))
    result = analyzer.analyze(source, SimpleNamespace(), [dict(start_ms=24480, end_ms=28600)], tmp_path / "points.jsonl", {"ball_track.pt": weight}, tmp_path, lambda *args: None)
    gaps = [shot for shot in result["shots"] if shot["end_kind"] == "unresolved" and shot["start_xy"] is None]
    assert any(shot["start_ms"] == 26640 and shot["end_ms"] == 28480 for shot in gaps)
    assert not any(shot["start_ms"] < 26640 < shot["end_ms"] and shot["end_kind"] != "unresolved" for shot in result["shots"])



def test_real_f2_reappearance_does_not_change_observed_hitter_or_swallow_near_return():
    saved = FIXTURES["m1-a2-01-20261019-workerfix"]
    rows, players = saved["round3_rows"], saved["round3_players"]
    contact = next(row for row in rows if row["timestamp_ms"] == 76120)
    person, reach = analyzer._near_player(contact, players, np.array([p["timestamp_ms"] for p in players]))
    assert person["side"] == "far" and reach == 0
    hits, _ = analyzer._hits(rows, players)
    actual = {(hit["timestamp_ms"], hit["player"]["side"]) for hit in hits}
    assert (78000, "near") in actual
    # A cropped real window can choose the adjacent 25 fps observation.
    assert any(abs(t - 76120) <= 40 and side == "far" for t, side in actual)
    assert not any(76520 <= hit["timestamp_ms"] <= 76720 for hit in hits)
    assert not any(hit["timestamp_ms"] == 75840 for hit in hits)


def test_inferred_candidate_cannot_override_direct_contact_even_with_larger_score(monkeypatch):
    saved = FIXTURES["m1-a2-01-20261019-workerfix"]
    rows, players = saved["round3_rows"], saved["round3_players"]
    near = next(p for frame in players for p in frame["players"] if p["side"] == "near")
    row = dict(next(row for row in rows if row["timestamp_ms"] == 76120))
    inferred = dict(timestamp_ms=76120., row=row, player=near, score=999., reach=0.,
                    reason="occluded_contact_arc_intersection", contact_interval_ms=[75840, 76280])
    monkeypatch.setattr(analyzer, "_gap_contacts", lambda *args: [inferred])
    hits, _ = analyzer._hits(rows, players)
    contact = next(hit for hit in hits if abs(hit["timestamp_ms"] - 76120) <= 40)
    assert contact["player"]["side"] == "far"
    assert contact["reason"] == "observed_velocity_turn"


def test_real_net_turns_survive_missing_opponent_contact_and_do_not_become_landings(monkeypatch, tmp_path):
    saved = FIXTURES["m1-short-a1-01-20261015"]
    rows, players = saved["round3_rows"], saved["round3_players"]
    hits, _ = analyzer._hits(rows, players)
    assert any(hit["timestamp_ms"] == 107400 and hit["player"]["side"] == "near" for hit in hits)
    assert any(abs(hit["timestamp_ms"] - 108120) <= 40 and hit["player"]["side"] == "near" for hit in hits)
    assert all(hit["direct_turn_supported"] for hit in hits if hit["timestamp_ms"] == 107400 or abs(hit["timestamp_ms"] - 108120) <= 40)
    source, weight = tmp_path / "video.mp4", tmp_path / "ball.pt"
    source.write_bytes(b"video")
    weight.write_bytes(b"model")
    meta = dict(reference_size=[1920, 1080], model_sha256=analyzer.file_sha256(weight), source_sha256="source")
    monkeypatch.setattr(analyzer, "_load_observations", lambda *args: (rows, meta))
    monkeypatch.setattr(analyzer, "_video_evidence", lambda *args: (dict(image_from_court=saved["image_from_court"], diagnostics={}), []))
    monkeypatch.setattr(analyzer, "_players", lambda *args: players)
    monkeypatch.setattr(analyzer, "_landing", lambda *args: (None, dict(reason="test_missing_height")))
    result = analyzer.analyze(source, SimpleNamespace(), [dict(start_ms=106000, end_ms=108800)], tmp_path / "points.jsonl", {"ball_track.pt": weight}, tmp_path, lambda *args: None)
    for shot in result["shots"]:
        if shot["start_ms"] in (106440, 107400):
            assert shot["end_kind"] == "unresolved"
    assert any(shot["start_xy"] is None and shot["end_ms"] == 107400 for shot in result["shots"])


def test_real_tail_turn_outweighs_same_side_tracking_jitter():
    saved = FIXTURES["m1-short-a1-01-20261015"]
    hits, _ = analyzer._hits(saved["round3_tail_rows"], saved["round3_tail_players"])
    assert any(abs(hit["timestamp_ms"] - 150120) <= 40 and hit["player"]["side"] == "near" for hit in hits)
    assert any(abs(hit["timestamp_ms"] - 151120) <= 40 and hit["player"]["side"] == "far" for hit in hits)
    assert not any(150280 <= hit["timestamp_ms"] <= 150880 for hit in hits)
