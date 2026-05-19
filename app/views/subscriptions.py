"""Subscriptions view.

Lists the user's wiki page subscriptions with a "fresh updates" badge when
the page has advanced past `last_seen_version`. Click navigates to the page
(which auto-marks-seen — see `app/pages/wiki.py:_auto_mark_seen`).

matches() activates when the user has at least one subscription with fresh
updates. Uses the same per-user cached subscription slug set the wiki page
uses for its Subscribe button — no extra network hits.
"""

from __future__ import annotations

from typing import Any

import streamlit as st

from app.components.api_client import list_subscriptions
from app.components.nav import navigate_to_wiki

ID = "subscriptions"
LABEL = "Subscriptions"
ICON = "📬"
COMMANDS = ("subscriptions", "subs", "subscribed")


def _safe_subscriptions() -> list[dict[str, Any]]:
    """Tolerant of pre-auth state and backend errors — `matches()` must
    not raise (registry contract: tests/test_views_registry.py)."""
    try:
        return list_subscriptions().get("subscriptions") or []
    except Exception:  # noqa: BLE001
        return []


def _fresh_count(subs: list[dict[str, Any]]) -> int:
    """Count subscriptions where current_version > last_seen_version."""
    fresh = 0
    for s in subs:
        cur = s.get("current_version")
        seen = s.get("last_seen_version")
        if isinstance(cur, int) and isinstance(seen, int) and cur > seen:
            fresh += 1
    return fresh


def matches(state: dict[str, Any]) -> bool:
    return _fresh_count(_safe_subscriptions()) > 0


def render_card(state: dict[str, Any]) -> None:
    subs = _safe_subscriptions()
    fresh = _fresh_count(subs)
    total = len(subs)
    if fresh:
        st.write(f"{ICON} **{LABEL}** · {fresh} of {total} updated")
    else:
        st.write(f"{ICON} **{LABEL}** · {total}")


def render(state: dict[str, Any]) -> None:
    subs = _safe_subscriptions()
    if not subs:
        st.info("No subscriptions yet. Open a wiki page and click 🔔 Subscribe.")
        return
    for s in subs:
        slug = s.get("slug", "?")
        title = s.get("title", slug)
        cur = s.get("current_version", 0)
        seen = s.get("last_seen_version", 0)
        is_fresh = isinstance(cur, int) and isinstance(seen, int) and cur > seen
        badge = f" · **v{cur}** (you saw v{seen})" if is_fresh else f" · v{cur} ✓"
        col1, col2 = st.columns([5, 1])
        with col1:
            st.write(f"📄 **{title}**{badge}")
            st.caption(f"`{slug}`")
        with col2:
            if st.button("Open", key=f"sub_open_{slug}"):
                navigate_to_wiki(slug)
