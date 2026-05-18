"""Campaign progress view — STUB.

Activation gated on chemclaw2 shipping `GET /api/campaigns` and
`GET /api/campaigns/{id}`. Tracked in BACKLOG.md → [views/campaigns].

Until then `matches()` still fires when chat invokes a campaign tool
(so the user sees the card and the BACKLOG pointer), but `render()`
shows the "backend route missing" message rather than actual data.

When the routes ship: rewrite this module to call
`api_client.list_campaigns()` and `api_client.get_campaign(id)`. The
dock auto-picks up the change — no other GUI work needed.
"""

from __future__ import annotations

from typing import Any

import streamlit as st

ID = "campaign"
LABEL = "Campaign progress"
ICON = "🧪"
COMMANDS = ("campaign", "campaigns", "bo")

_CAMPAIGN_TOOL_NAMES = {"start_synthesis_campaign", "confirm_synthesis_plan"}


def matches(state: dict[str, Any]) -> bool:
    recent = state.get("chat_recent_tool_uses") or []
    return any(t in _CAMPAIGN_TOOL_NAMES for t in recent)


def render_card(state: dict[str, Any]) -> None:
    st.write(f"{ICON} **{LABEL}** · _backend route pending_")


def render(state: dict[str, Any]) -> None:
    st.warning(
        "Campaign data is reachable only via the agent today. "
        "Activate this view by shipping `GET /api/campaigns` and "
        "`GET /api/campaigns/{id}` on chemclaw2 — see "
        "[BACKLOG.md](./BACKLOG.md) entry `[views/campaigns]`."
    )
    st.caption(
        "Workaround: ask the chat agent — e.g. _\"list active campaigns\"_ or "
        "_\"show me the plan for the aspirin campaign\"_."
    )
