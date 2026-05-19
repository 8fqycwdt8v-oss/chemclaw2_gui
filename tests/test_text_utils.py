from datetime import UTC, datetime, timedelta

from app.components.text_utils import _WIKI_REF_RE, extract_wiki_refs, relative_time


def test_extract_wiki_refs_returns_distinct_in_order() -> None:
    text = (
        "See [wiki:aspirin-synthesis] and [wiki:ibuprofen-overview], "
        "also [wiki:aspirin-synthesis] again."
    )
    assert extract_wiki_refs(text) == ["aspirin-synthesis", "ibuprofen-overview"]


def test_extract_wiki_refs_rejects_invalid_slugs() -> None:
    # Uppercase, underscores, leading hyphens — all rejected per chemclaw2 slug rules.
    text = "[wiki:Aspirin] [wiki:_under] [wiki:-lead] [wiki:valid-slug]"
    assert extract_wiki_refs(text) == ["valid-slug"]


def test_extract_wiki_refs_empty_when_no_match() -> None:
    assert extract_wiki_refs("plain text with no refs") == []


def test_wiki_ref_regex_rejects_single_char_slugs() -> None:
    # chemclaw2's _SLUG_RE is ^[a-z0-9][a-z0-9-]*[a-z0-9]$ (≥2 chars).
    # pages/wiki.py:SLUG_RE matches. Lock this regex too — drift here
    # produces dead links (ref parses, page won't exist).
    assert extract_wiki_refs("[wiki:a] [wiki:1]") == []
    assert extract_wiki_refs("[wiki:ab] [wiki:a1]") == ["ab", "a1"]


def test_wiki_ref_regex_matches_chemclaw2_slug_re_pattern() -> None:
    # Authoritative chemclaw2 pattern documented in CLAUDE.md gotchas.
    # Locks the wiki-ref capture group against that source. If chemclaw2's
    # _SLUG_RE changes, this test should be updated in the same PR that
    # updates _WIKI_REF_RE.
    chemclaw2_slug_pattern = r"[a-z0-9][a-z0-9-]*[a-z0-9]"
    assert chemclaw2_slug_pattern in _WIKI_REF_RE.pattern


def test_relative_time_seconds() -> None:
    now = datetime(2026, 5, 17, 12, 0, 0, tzinfo=UTC)
    assert relative_time(now - timedelta(seconds=10), now=now) == "10s ago"


def test_relative_time_minutes_hours_days() -> None:
    now = datetime(2026, 5, 17, 12, 0, 0, tzinfo=UTC)
    assert relative_time(now - timedelta(minutes=5), now=now) == "5m ago"
    assert relative_time(now - timedelta(hours=2), now=now) == "2h ago"
    assert relative_time(now - timedelta(days=3), now=now) == "3d ago"


def test_relative_time_falls_back_to_iso_date_for_ancient() -> None:
    now = datetime(2026, 5, 17, 12, 0, 0, tzinfo=UTC)
    old = now - timedelta(days=90)
    assert relative_time(old, now=now) == old.date().isoformat()


def test_relative_time_iso_string_input() -> None:
    now = datetime(2026, 5, 17, 12, 0, 0, tzinfo=UTC)
    # ISO with explicit Z suffix
    assert relative_time("2026-05-17T11:55:00Z", now=now) == "5m ago"
    # ISO with offset
    assert relative_time("2026-05-17T11:55:00+00:00", now=now) == "5m ago"


def test_relative_time_naive_timestamp_assumed_utc() -> None:
    now = datetime(2026, 5, 17, 12, 0, 0, tzinfo=UTC)
    assert relative_time("2026-05-17T11:55:00", now=now) == "5m ago"


def test_relative_time_handles_none() -> None:
    assert relative_time(None) == "—"


def test_relative_time_handles_unparseable() -> None:
    assert relative_time("not a date") == "—"
