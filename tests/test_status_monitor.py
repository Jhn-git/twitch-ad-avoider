"""Tests for Twitch status monitor input hardening."""

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
