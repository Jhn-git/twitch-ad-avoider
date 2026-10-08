"""Tests for Twitch status monitor input hardening."""

import requests

from src import status_monitor
from src.status_monitor import StatusMonitor


def test_check_channels_validates_before_batch_query(monkeypatch):
    """Invalid channels are not passed into the GraphQL query builder."""
    monitor = StatusMonitor()
    captured = {}

    def fake_batch_check(channels):
        captured["channels"] = channels
        return {channel: True for channel in channels}

    monkeypatch.setattr(monitor, "_batch_check", fake_batch_check)

    result = monitor.check_channels(["NINJA", "bad;channel"])

    assert captured["channels"] == ["ninja"]
    assert result == {"ninja": True}


def test_check_channels_all_invalid_skips_batch_query(monkeypatch):
    """All-invalid status checks fail closed without building a query."""
    monitor = StatusMonitor()

    def fail_batch_check(channels):
        raise AssertionError("batch query should not run for invalid channels")

    monkeypatch.setattr(monitor, "_batch_check", fail_batch_check)

    result = monitor.check_channels(["bad;channel"])

    assert result == {"bad;channel": False}


def test_check_channels_returns_empty_on_batch_failure(monkeypatch):
    """A failed batch request reports 'unknown', not 'everyone offline'."""
    monitor = StatusMonitor()

    def raising_batch_check(channels):
        raise ConnectionError("network unreachable")

    monkeypatch.setattr(monitor, "_batch_check", raising_batch_check)

    result = monitor.check_channels(["ninja", "shroud"])

    assert result == {}


def _http_error(status):
    response = requests.Response()
    response.status_code = status
    return requests.HTTPError(f"{status} error", response=response)


def _flaky_batch_check(failures, exc):
    calls = {"count": 0}

    def batch_check(channels):
        calls["count"] += 1
        if calls["count"] <= failures:
            raise exc
        return {channel: True for channel in channels}

    return batch_check, calls


def test_check_channels_retries_transient_connection_error(monkeypatch):
    """A dropped connection (e.g. DNS right after wake) is retried, not failed."""
    monitor = StatusMonitor()
    batch_check, calls = _flaky_batch_check(2, requests.ConnectionError("dns failed"))
    monkeypatch.setattr(monitor, "_batch_check", batch_check)
    monkeypatch.setattr(status_monitor.time, "sleep", lambda _: None)

    result = monitor.check_channels(["ninja"])

    assert result == {"ninja": True}
    assert calls["count"] == 3
    assert monitor.last_error_kind is None


def test_check_channels_retries_server_errors(monkeypatch):
    monitor = StatusMonitor()
    batch_check, calls = _flaky_batch_check(1, _http_error(503))
    monkeypatch.setattr(monitor, "_batch_check", batch_check)
    monkeypatch.setattr(status_monitor.time, "sleep", lambda _: None)

    assert monitor.check_channels(["ninja"]) == {"ninja": True}
    assert calls["count"] == 2


def test_check_channels_gives_up_and_classifies_offline(monkeypatch):
    monitor = StatusMonitor()
    batch_check, calls = _flaky_batch_check(99, requests.ConnectionError("dns failed"))
    monkeypatch.setattr(monitor, "_batch_check", batch_check)
    monkeypatch.setattr(status_monitor.time, "sleep", lambda _: None)

    assert monitor.check_channels(["ninja"]) == {}
    assert calls["count"] == status_monitor.MAX_ATTEMPTS
    assert monitor.last_error_kind == "offline"


def test_check_channels_classifies_timeout_and_server(monkeypatch):
    monkeypatch.setattr(status_monitor.time, "sleep", lambda _: None)
    for exc, kind in (
        (requests.ReadTimeout("slow"), "timeout"),
        (requests.ConnectTimeout("slow"), "timeout"),
        (_http_error(503), "server"),
    ):
        monitor = StatusMonitor()
        batch_check, _ = _flaky_batch_check(99, exc)
        monkeypatch.setattr(monitor, "_batch_check", batch_check)
        assert monitor.check_channels(["ninja"]) == {}
        assert monitor.last_error_kind == kind


def test_check_channels_does_not_retry_client_errors(monkeypatch):
    monitor = StatusMonitor()
    batch_check, calls = _flaky_batch_check(99, _http_error(400))
    monkeypatch.setattr(monitor, "_batch_check", batch_check)
    monkeypatch.setattr(status_monitor.time, "sleep", lambda _: None)

    assert monitor.check_channels(["ninja"]) == {}
    assert calls["count"] == 1
    assert monitor.last_error_kind == "other"
