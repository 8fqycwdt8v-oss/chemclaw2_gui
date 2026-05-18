"""Agent todos view.

Shows the task list the agent populates during long-running work
(deep-research, synthesis campaigns). Activates heuristically after
3+ tool calls in a session.
"""

from __future__ import annotations

from typing import Any

import streamlit as st

from app.components.api_client import get_todos

ID = "todos"
LABEL = "Agent todos"
ICON = "✅"
COMMANDS = ("todos", "tasks", "checklist")


def matches(state: dict[str, Any]) -> bool:
    return len(state.get("chat_recent_tool_uses") or []) >= 3


def render_card(state: dict[str, Any]) -> None:
    tool_count = len(state.get("chat_recent_tool_uses") or [])
    st.write(f"{ICON} **{LABEL}** · {tool_count} tool call{'s' if tool_count != 1 else ''}")


def render(state: dict[str, Any]) -> None:
    session_id = state.get("chat_session_id")
    if not session_id:
        st.info("No active chat session — start a conversation to see agent tasks.")
        return
    try:
        data = get_todos(session_id)
    except Exception as exc:  # noqa: BLE001
        st.error(f"Could not load todos: {exc}")
        return
    todos = data.get("todos") or []
    if not todos:
        st.info("No tasks logged for this session yet.")
        return
    done = sum(1 for t in todos if t.get("status") == "done")
    st.caption(f"{done}/{len(todos)} completed")
    for todo in todos:
        checked = todo.get("status") == "done"
        label = todo.get("text", "")
        todo_key = todo.get("id", todo.get("position", 0))
        st.checkbox(label, value=checked, disabled=True, key=f"todo_{todo_key}")
