"""Notifications view.

Proactive alerts surfaced by chemclaw2 — campaign convergence, similar new
compounds, contradiction flags, etc. Activates whenever there are unread
notifications. matches() reads from a per-user 30s cache so the heuristic
doesn't hit the backend on every rerun.
"""

from __future__ import annotations

import json
from typing import Any

import streamlit as st

from app.components.api_client import (
    cached_unread_notifications,
    get_notifications,
    mark_notifications_read,
)

ID = "notifications"
LABEL = "Notifications"
ICON = "🔔"
COMMANDS = ("notifications", "alerts", "inbox")


def _safe_unread_count() -> int:
    """Tolerant of un-initialised auth — `matches()` must never raise per the
    registry contract (tests/test_views_registry.py). The cached fetch reads
    `st.user.sub` which raises before sign-in. Treat any failure as zero."""
    try:
        return cached_unread_notifications().get("unread_count", 0)
    except Exception:  # noqa: BLE001
        return 0


def matches(state: dict[str, Any]) -> bool:
    return _safe_unread_count() > 0


def render_card(state: dict[str, Any]) -> None:
    count = _safe_unread_count()
    label = "unread alert" if count == 1 else "unread alerts"
    st.write(f"{ICON} **{LABEL}** · {count} {label}")


def _format_payload(payload: Any) -> str:
    """Render the notification's `type`-specific JSONB payload as a one-liner."""
    if not isinstance(payload, dict):
        return str(payload)
    # Heuristics for the common payload shapes; falls back to a compact JSON dump.
    if "message" in payload:
        return str(payload["message"])
    if "title" in payload:
        return str(payload["title"])
    return json.dumps(payload, separators=(",", ":"))[:200]


def render(state: dict[str, Any]) -> None:
    show_all = st.toggle("Include read", value=False, key="notifications_show_all")
    try:
        data = get_notifications(unread_only=not show_all, limit=50)
    except Exception as exc:  # noqa: BLE001
        st.error(f"Failed to load notifications: {exc}")
        return

    items = data.get("notifications") or []
    if not items:
        st.success("Inbox zero.")
        return

    unread_ids = [n["id"] for n in items if not n.get("read")]
    if unread_ids and st.button("Mark all read", key="notifications_mark_all"):
        mark_notifications_read(all_=True)
        st.rerun()

    for n in items:
        read = n.get("read")
        with st.container(border=True):
            cols = st.columns([10, 1])
            with cols[0]:
                kind = n.get("type", "notice")
                prefix = "" if read else "**•** "
                st.write(f"{prefix}`{kind}` · {_format_payload(n.get('payload'))}")
                st.caption(str(n.get("created_at", "")))
            with cols[1]:
                if not read and st.button("✓", key=f"notif_read_{n['id']}", help="Mark read"):
                    mark_notifications_read(ids=[n["id"]])
                    st.rerun()
