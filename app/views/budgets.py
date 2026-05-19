"""Project budget view — user-scoped.

chemclaw2 enforces `project_key == f"chemclaw2:{user_id}"` (api/routes/budgets.py:
_check_ownership), so each user has exactly one budget they can see.

Quick-open only — admin views pattern. Don't auto-pin.
"""

from __future__ import annotations

from typing import Any

import httpx
import streamlit as st

from app.components.api_client import get_my_budget

ID = "budgets"
LABEL = "Project budget"
ICON = "💰"
COMMANDS = ("budget", "budgets", "spend")


def matches(state: dict[str, Any]) -> bool:
    # Quick-open only. matches() could check whether a budget exists, but
    # that's a network hit per rerun — defer until users ask for auto-pin.
    return False


def render_card(state: dict[str, Any]) -> None:
    st.write(f"{ICON} **{LABEL}**")


def _bar(label: str, used: int | None, cap: int | None) -> None:
    used_i = int(used or 0)
    cap_i = int(cap or 0)
    if cap_i <= 0:
        st.caption(f"**{label}**: no cap · used {used_i:,}")
        return
    pct = min(1.0, used_i / cap_i)
    color = "🔴" if pct >= 0.9 else "🟡" if pct >= 0.7 else "🟢"
    st.caption(f"**{label}**: {color} {used_i:,} / {cap_i:,} ({pct:.0%})")
    st.progress(pct)


def render(state: dict[str, Any]) -> None:
    try:
        data = get_my_budget()
    except httpx.HTTPError as exc:
        st.error(f"Failed to load budget: {exc}")
        return

    budget = data.get("budget")
    spend = data.get("spend") or {}

    if not budget:
        st.info("No budget set. An admin can configure one via `PUT /api/budgets/{project_key}`.")
        return

    period = budget.get("period", "?")
    st.subheader(f"Current {period} budget")
    _bar("Tool calls", spend.get("tool_calls"), budget.get("tool_calls_cap"))
    _bar("Experiments", spend.get("experiments"), budget.get("experiments_cap"))
    _bar("Tokens", spend.get("tokens"), budget.get("tokens_cap"))
