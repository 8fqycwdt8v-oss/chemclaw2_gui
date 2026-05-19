"""Tool permissions browser — admin-only.

Read-only v1 (chemclaw2 has POST/DELETE but we don't expose admin write
actions in the GUI yet — defer until there's a real admin UX brief).
Quick-open only; gracefully shows "admin required" on 403.
"""

from __future__ import annotations

from typing import Any

import httpx
import streamlit as st

from app.components.api_client import list_tool_permissions

ID = "tool_permissions"
LABEL = "Tool permissions"
ICON = "🛡️"
COMMANDS = ("permissions", "perms", "acl", "tools-acl")

_MODE_EMOJI = {"allow": "🟢", "ask": "🟡", "deny": "🔴"}


def matches(state: dict[str, Any]) -> bool:
    return False  # admin view; quick-open only


def render_card(state: dict[str, Any]) -> None:
    st.write(f"{ICON} **{LABEL}** · admin-only")


def render(state: dict[str, Any]) -> None:
    try:
        data = list_tool_permissions()
    except httpx.HTTPStatusError as exc:
        if exc.response.status_code == 403:
            st.error("Admin access required.")
            return
        st.error(f"Failed to load permissions: {exc}")
        return
    except httpx.HTTPError as exc:
        st.error(f"Failed to load permissions: {exc}")
        return

    perms = data.get("permissions") or []
    if not perms:
        st.info("No tool-permission overrides configured.")
        return

    st.caption(f"{len(perms)} permission rule{'s' if len(perms) != 1 else ''}")
    for p in perms:
        with st.container(border=True):
            cols = st.columns([1, 2, 3, 1])
            cols[0].caption(_MODE_EMOJI.get(p.get("mode", ""), "•"))
            cols[1].caption(f"**{p.get('scope', '?')}**\n`{p.get('scope_id', '?')}`")
            cols[2].caption(f"tool: `{p.get('tool_name', '?')}`")
            cols[3].caption(f"_{p.get('mode', '?')}_")
