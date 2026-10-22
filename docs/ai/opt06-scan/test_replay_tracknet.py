from dataclasses import dataclass

from replay_tracknet import consume_groups, group_is_candidate


@dataclass
class Frame:
    frame_id: int
    timestamp_ms: float
    image: int


def test_gate_uses_actual_group_timestamps_and_half_open_boundaries():
    assert group_is_candidate([Frame(0, 100, 0), Frame(1, 150, 1), Frame(2, 199, 2)], [(100, 200)])
    assert not group_is_candidate([Frame(3, 200, 3)], [(100, 200)])


def test_candidate_replay_keeps_native_groups_separate():
    frames = [Frame(i, t, i) for i, t in enumerate((0, 50, 99, 100, 150, 200))]
    calls = []

    def predict(images):
        calls.append(images)
        return [object(), object(), object()]

    total, executed, skipped, tail = consume_groups(iter(frames), predict, "candidate", [(100, 101)])

    assert total == 6
    assert calls == [[3, 4, 5]]
    assert executed == [3] and skipped == 1 and tail == []
