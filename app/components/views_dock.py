"""Specialised-views dock.

Renders in the sidebar after the existing sign-out + backend-health blocks.
Three sections:

  🔎 Quick open — text input. Type a keyword that matches some view's
     `COMMANDS`; that view auto-pins and opens its dialog.
  📌 Active views — one card per view that either (a) self-matched the
     current state heuristically, or (b) was explicitly pinned by the user.
     Each card has Expand (open dialog) and Dismiss (unpin) actions.
  🪟 Dialog host — when `st.session_state.active_view_id` is set, opens
     that view's `render()` inside an `@st.dialog`. One dialog at a time
     per Streamlit session.

State maintained:
  dock_pinned: set[str]   — view IDs the user explicitly pinned
  active_view_id: str|None — currently-open dialog

State `build_state()` exposes to view matchers (deliberately small):
  chat_recent_tool_uses, chat_session_id, chat_assistant_text_last,
  wiki_current_slug, wiki_current_page, last_search_kind
"""

from __future__ import annotations

from typing import Any

import streamlit as st

from app.views import VIEWS
from app.views._base import View


def build_state() -> dict[str, Any]:
    """Snapshot the session_state keys view matchers are allowed to read.

    Keep this small — every key here becomes part of the matcher contract.
    """
    history = st.session_state.get("chat_history") or []
    last_assistant = next((text for role, text in reversed(history) if role == "assistant"), "")
    return {
        "chat_recent_tool_uses": st.session_state.get("chat_recent_tool_uses") or [],
        "chat_session_id": st.session_state.get("chat_session_id"),
        "chat_assistant_text_last": last_assistant,
        "wiki_current_slug": st.session_state.get("wiki_slug")
        if st.session_state.get("wiki_mode") in ("view", "edit")
        else None,
        "wiki_current_page": st.session_state.get("wiki_current_page"),
        "last_search_kind": st.session_state.get("last_search_kind"),
    }


def _init_state() -> None:
    if "dock_pinned" not in st.session_state:
        st.session_state.dock_pinned = set()
    if "active_view_id" not in st.session_state:
        st.session_state.active_view_id = None


def _active_views(state: dict[str, Any]) -> list[View]:
    pinned = st.session_state.dock_pinned
    return [v for v in VIEWS.values() if v.id in pinned or v.matches(state)]


def _handle_quick_open(query: str) -> None:
    keyword = query.strip().lower()
    if not keyword:
        return
    for view in VIEWS.values():
        if keyword in view.commands:
            st.session_state.dock_pinned.add(view.id)
            st.session_state.active_view_id = view.id
            return
    st.session_state.dock_open_error = f"No view matches `{keyword}`."


def render_dock() -> None:
    _init_state()
    state = build_state()

    st.caption("🔎 Quick open")
    query = st.text_input(
        "view command",
        key="dock_quick_open",
        label_visibility="collapsed",
        placeholder="campaign, todos, research…",
    )
    if query:
        _handle_quick_open(query)
        # Reset the input so a second use doesn't immediately reopen the dialog.
        st.session_state.dock_quick_open = ""
        st.rerun()
    if err := st.session_state.pop("dock_open_error", None):
        st.caption(f":red[{err}]")

    actives = _active_views(state)
    if actives:
        st.caption("📌 Active views")
        for view in actives:
            with st.container(border=True):
                view.render_card(state)
                c_expand, c_dismiss = st.columns(2)
                with c_expand:
                    if st.button("Expand", key=f"dock_expand_{view.id}"):
                        st.session_state.active_view_id = view.id
                        st.rerun()
                with c_dismiss:
                    if st.button("Dismiss", key=f"dock_dismiss_{view.id}"):
                        st.session_state.dock_pinned.discard(view.id)
                        if st.session_state.active_view_id == view.id:
                            st.session_state.active_view_id = None
                        st.rerun()

    # Dialog host. Lives in the main area (not the sidebar) — Streamlit's
    # dialog overlays the whole page regardless of where it's called from,
    # but invoking it from inside the sidebar context is fine.
    if st.session_state.active_view_id:
        view = VIEWS.get(st.session_state.active_view_id)
        if view is None:
            st.session_state.active_view_id = None
        else:
            _open_dialog(view, state)


def _open_dialog(view: View, state: dict[str, Any]) -> None:
    """Define + invoke the dialog inline so it closes over `view` cleanly."""

    @st.dialog(f"{view.icon} {view.label}", width="large")
    def _dialog() -> None:
        view.render(state)

    _dialog()
