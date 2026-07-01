"""Tests for Katch keyword matching."""

from katch.keyword_matcher import KeywordMatcher


def test_keyword_matcher_finds_phrase_across_punctuation() -> None:
    matcher = KeywordMatcher(["dead by daylight"], cooldown_seconds=20)

    matches = matcher.match("I was playing Dead-by-Daylight again tonight.", 12.0)

    assert [match.keyword for match in matches] == ["dead by daylight"]
    assert matches[0].matched_text == "dead by daylight"


def test_keyword_matcher_applies_cooldown() -> None:
    matcher = KeywordMatcher(["juice box"], cooldown_seconds=10)

    first = matcher.match("juice box spotted", 5.0)
    second = matcher.match("another juice box moment", 10.0)
    third = matcher.match("juice box returns", 16.0)

    assert len(first) == 1
    assert second == []
    assert len(third) == 1
