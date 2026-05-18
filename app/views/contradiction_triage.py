"""Contradiction triage view — STUB.

Activation gated on chemclaw2 extending `GET /api/wiki/{slug}` to return
`contradictions: WikiContradiction[]` (or adding a sibling route).
Tracked in BACKLOG.md → [views/contradictions].

Until then `matches()` fires whenever the user is on a wiki page (so the
card shows the BACKLOG pointer in context), but `render()` shows the
"backend route missing" message.
"""

from __future__ import annotations

from typing import Any

import streamlit as st

ID = "contradictions"
LABEL = "Contradiction triage"
ICON = "⚖️"
COMMANDS = ("contradictions", "disputes", "conflict")


def matches(state: dict[str, Any]) -> bool:
    # No backend signal today; activate as a hint only when user is on a wiki page.
    return state.get("wiki_current_slug") is not None


def render_card(state: dict[str, Any]) -> None:
    st.write(f"{ICON} **{LABEL}** · _backend field pending_")


def render(state: dict[str, Any]) -> None:
    slug = state.get("wiki_current_slug") or "_no page open_"
    st.warning(
        f"No contradictions data exposed for `{slug}`. "
        "Activate this view by adding `contradictions[]` to "
        "`GET /api/wiki/{{slug}}` on chemclaw2 — see "
        "[BACKLOG.md](./BACKLOG.md) entry `[views/contradictions]`."
    )
