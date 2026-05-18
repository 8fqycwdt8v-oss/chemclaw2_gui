"""Agent todos view — STUB.

Activation gated on chemclaw2 shipping `GET /api/todos/{session_id}`.
The `AgentTodo` table exists; sub-agents (deep-research) populate it;
but there's no HTTP route to read it. Tracked in BACKLOG.md →
[views/todos].

Until then `matches()` fires after the agent has done meaningful work
(3+ tool calls), but `render()` shows the "backend route missing" hint.
"""

from __future__ import annotations

from typing import Any

import streamlit as st

ID = "todos"
LABEL = "Agent todos"
ICON = "✅"
COMMANDS = ("todos", "tasks", "checklist")


def matches(state: dict[str, Any]) -> bool:
    return len(state.get("chat_recent_tool_uses") or []) >= 3


def render_card(state: dict[str, Any]) -> None:
    st.write(f"{ICON} **{LABEL}** · _backend route pending_")


def render(state: dict[str, Any]) -> None:
    st.warning(
        "Agent todo list is stored in the database but no HTTP route exposes "
        "it. Activate this view by shipping `GET /api/todos/{session_id}` "
        "on chemclaw2 — see [BACKLOG.md](./BACKLOG.md) entry `[views/todos]`."
    )
