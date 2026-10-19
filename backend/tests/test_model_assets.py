import hashlib

import pytest
import requests

from app import model_assets


@pytest.mark.parametrize("failure", [b"download error page", requests.ReadTimeout("stalled")])
def test_failed_download_is_removed_retry_and_verified_offline_cache(tmp_path, monkeypatch, failure):
    content = b"pinned model content"
    monkeypatch.setattr(model_assets, "ASSETS", {"ball_track.pt": {
        "url": "https://model.example/checkpoint", "bytes": len(content),
        "sha256": hashlib.sha256(content).hexdigest(), "label": "测试模型",
    }})

    class Response:
        def __init__(self, payload):
            self.payload = payload

        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

        def raise_for_status(self):
            pass

        def iter_content(self, size):
            if isinstance(self.payload, Exception):
                raise self.payload
            yield self.payload

    attempts = iter([failure, content])
    monkeypatch.setattr(requests, "get", lambda *args, **kwargs: Response(next(attempts)))
    progress = []
    with pytest.raises(RuntimeError, match="准备处理失败"):
        model_assets.ensure_models("high", tmp_path, lambda *event: progress.append(event))
    assert not (tmp_path / "ball_track.pt").exists()
    assert not (tmp_path / "ball_track.pt.download").exists()
    paths = model_assets.ensure_models("high", tmp_path, lambda *event: progress.append(event))
    assert paths["ball_track.pt"].read_bytes() == content

    def offline(*args, **kwargs):
        pytest.fail("verified model cache must work without a network request")

    monkeypatch.setattr(requests, "get", offline)
    assert model_assets.ensure_models("high", tmp_path, lambda *event: None) == paths
    assert any(0 < fraction <= 1 for _, fraction in progress)
