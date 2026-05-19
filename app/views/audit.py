"""Audit trail browser — admin-only.

Quick-open only (matches=False per the "admin views" pattern in CLAUDE.md).
Gracefully degrades for non-admin users by surfacing the 403 as a clear
"requires admin" message rather than crashing.

Surfaces three chemclaw2 admin endpoints:
  - /api/audit/overrides   (agent overrides — scheduled-substance bypass etc.)
  - /api/audit/redactions  (tool-input redactions logged by the redaction hook)
"""

from __future__ import annotations

from typing import Any

import httpx
import streamlit as st

from app.components.api_client import list_audit_overrides, list_audit_redactions
from app.components.text_utils import relative_time

ID = "audit"
LABEL = "Audit trail"
ICON = "🔍"
COMMANDS = ("audit", "overrides", "redactions")


def matches(state: dict[str, Any]) -> bool:
    # Admin view — never auto-pin. Quick-open or pinned explicitly.
    return False


def render_card(state: dict[str, Any]) -> None:
    st.write(f"{ICON} **{LABEL}** · admin-only")


def _render_rows(rows: list[dict[str, Any]], empty_msg: str) -> None:
    if not rows:
        st.info(empty_msg)
        return
    for row in rows:
        with st.container(border=True):
            cols = st.columns([3, 2, 2, 5])
            cols[0].caption(f"`{row.get('user_id', '?')}`")
            cols[1].caption(f"`{row.get('gate_name', '—')}`")
            cols[2].caption(relative_time(row.get("created_at")))
            cols[3].write(row.get("justification") or row.get("redaction_summary") or "—")


def render(state: dict[str, Any]) -> None:
    tab_o, tab_r = st.tabs(["Overrides", "Redactions"])
    with tab_o:
        try:
            data = list_audit_overrides()
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code == 403:
                st.error("Admin access required.")
                return
            st.error(f"Failed to load overrides: {exc}")
            return
        except httpx.HTTPError as exc:
            st.error(f"Failed to load overrides: {exc}")
            return
        _render_rows(data.get("overrides") or [], "No overrides recorded.")

    with tab_r:
        try:
            data = list_audit_redactions()
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code == 403:
                st.error("Admin access required.")
                return
            st.error(f"Failed to load redactions: {exc}")
            return
        except httpx.HTTPError as exc:
            st.error(f"Failed to load redactions: {exc}")
            return
        _render_rows(data.get("redactions") or [], "No redactions recorded.")
