"""Small pure helpers for text formatting and parsing.

Tested in isolation — no Streamlit dependency — so the chat citation parser
and the wiki freshness formatter can be exercised without booting Streamlit.
"""

import re
from datetime import UTC, datetime

# Match `[wiki:slug]` where slug follows chemclaw2's slug rules
# (^[a-z0-9][a-z0-9-]*[a-z0-9]?$ — see api/routes/wiki.py:_SLUG_RE).
# Captures unique slugs in order of first appearance.
_WIKI_REF_RE = re.compile(r"\[wiki:([a-z0-9](?:[a-z0-9-]*[a-z0-9])?)\]")


def extract_wiki_refs(text: str) -> list[str]:
    """Return distinct wiki slugs referenced via `[wiki:slug]` in order of first appearance."""
    seen: dict[str, None] = {}
    for match in _WIKI_REF_RE.finditer(text):
        slug = match.group(1)
        if slug not in seen:
            seen[slug] = None
    return list(seen)


def relative_time(ts: str | datetime | None, *, now: datetime | None = None) -> str:
    """Format an ISO 8601 timestamp (or datetime) as "5m ago" / "2h ago" / "3d ago".

    Falls back to "—" on None or unparseable input. Stale-but-not-ancient
    (≥ 30 days) renders as the ISO date for clarity.
    """
    if ts is None:
        return "—"
    dt = ts if isinstance(ts, datetime) else _parse_iso(ts)
    if dt is None:
        return "—"
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    now_dt = now or datetime.now(UTC)
    delta = now_dt - dt
    secs = int(delta.total_seconds())
    if secs < 0:
        return "just now"
    if secs < 60:
        return f"{secs}s ago"
    if secs < 3600:
        return f"{secs // 60}m ago"
    if secs < 86_400:
        return f"{secs // 3600}h ago"
    if secs < 30 * 86_400:
        return f"{secs // 86_400}d ago"
    return dt.date().isoformat()


def _parse_iso(s: str) -> datetime | None:
    try:
        # Python's fromisoformat handles `2026-05-17T20:00:00+00:00` and `...Z` (3.11+).
        return datetime.fromisoformat(s.replace("Z", "+00:00"))
    except (ValueError, TypeError):
        return None
