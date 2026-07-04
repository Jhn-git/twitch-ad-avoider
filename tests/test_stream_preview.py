"""Tests for single-channel stream preview fetching."""

from src.stream_preview import fetch_image_bytes, fetch_stream_preview_info


class _FakeResponse:
    def __init__(self, json_data=None, content=b"", status=200):
        self._json_data = json_data
        self.content = content
        self.status_code = status

    def raise_for_status(self):
        if self.status_code >= 400:
            raise Exception(f"HTTP {self.status_code}")

    def json(self):
        return self._json_data


def test_fetch_stream_preview_info_live_channel(monkeypatch):
    """A live channel's title and preview image URL are parsed out of the GQL response."""
    payload = {
        "data": {
            "user": {
                "stream": {
                    "title": "Chill stream",
                    "previewImageURL": "https://example.com/preview.jpg",
                }
            }
        }
    }
    call_kwargs = {}

    def fake_post(*args, **kwargs):
        call_kwargs.update(kwargs)
        return _FakeResponse(payload)

    monkeypatch.setattr(
        "src.stream_preview.requests.post",
        fake_post,
    )

    info = fetch_stream_preview_info("ninja", timeout=17)

    assert info.channel == "ninja"
    assert info.is_live is True
    assert info.title == "Chill stream"
    assert info.preview_image_url == "https://example.com/preview.jpg"
    assert call_kwargs["timeout"] == 17


def test_fetch_stream_preview_info_offline_channel(monkeypatch):
    """A null stream node means the channel is offline."""
    payload = {"data": {"user": {"stream": None}}}
    monkeypatch.setattr(
        "src.stream_preview.requests.post", lambda *a, **k: _FakeResponse(payload)
    )

    info = fetch_stream_preview_info("ninja")

    assert info.is_live is False
    assert info.title is None
    assert info.preview_image_url is None


def test_fetch_stream_preview_info_invalid_channel_skips_request(monkeypatch):
    """Invalid channel names never reach the network layer."""

    def fail_post(*args, **kwargs):
        raise AssertionError("GQL request should not run for an invalid channel")

    monkeypatch.setattr("src.stream_preview.requests.post", fail_post)

    info = fetch_stream_preview_info("bad;channel")

    assert info.is_live is False


def test_fetch_stream_preview_info_degrades_on_request_error(monkeypatch):
    """Network failures never raise; they degrade to an offline result."""

    def raise_error(*args, **kwargs):
        raise ConnectionError("boom")

    monkeypatch.setattr("src.stream_preview.requests.post", raise_error)

    info = fetch_stream_preview_info("ninja")

    assert info.is_live is False


def test_fetch_image_bytes_returns_content(monkeypatch):
    call_kwargs = {}

    def fake_get(*args, **kwargs):
        call_kwargs.update(kwargs)
        return _FakeResponse(content=b"binary-image-data")

    monkeypatch.setattr(
        "src.stream_preview.requests.get",
        fake_get,
    )

    result = fetch_image_bytes("https://example.com/preview.jpg", timeout=19)

    assert result == b"binary-image-data"
    assert call_kwargs["timeout"] == 19


def test_fetch_image_bytes_returns_none_on_failure(monkeypatch):
    def raise_error(*args, **kwargs):
        raise ConnectionError("boom")

    monkeypatch.setattr("src.stream_preview.requests.get", raise_error)

    result = fetch_image_bytes("https://example.com/preview.jpg")

    assert result is None
