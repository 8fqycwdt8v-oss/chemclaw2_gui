"""Contradiction triage view.

Shows unresolved contradictions flagged by the agent on the currently-open
wiki page. Activates whenever a wiki page is open.
"""

from __future__ import annotations

from typing import Any

import streamlit as st

from app.components.api_client import get_wiki_contradictions

ID = "contradictions"
LABEL = "Contradiction triage"
ICON = "⚖️"
COMMANDS = ("contradictions", "disputes", "conflict")

_WINNER_LABEL = {"a": "A wins", "b": "B wins", "inconclusive": "Inconclusive"}


def matches(state: dict[str, Any]) -> bool:
    return state.get("wiki_current_slug") is not None


def render_card(state: dict[str, Any]) -> None:
    slug = state.get("wiki_current_slug")
    if slug:
        st.write(f"{ICON} **{LABEL}** · `{slug}`")
    else:
        st.write(f"{ICON} **{LABEL}**")


def render(state: dict[str, Any]) -> None:
    slug = state.get("wiki_current_slug")
    if not slug:
        st.info("Open a wiki page to see its contradictions.")
        return

    show_resolved = st.toggle("Show resolved", value=False, key="contradictions_show_resolved")

    try:
        data = get_wiki_contradictions(slug, resolved=show_resolved)
    except Exception as exc:  # noqa: BLE001
        st.error(f"Could not load contradictions for `{slug}`: {exc}")
        return

    items = data.get("contradictions") or []
    if not items:
        label = "resolved" if show_resolved else "open"
        st.success(f"No {label} contradictions on `{slug}`.")
        return

    for item in items:
        winner = item.get("proposed_winner", "inconclusive")
        winner_label = _WINNER_LABEL.get(winner, winner)
        a, b = item.get("citation_a", "?"), item.get("citation_b", "?")
        header = f"**{winner_label}** — _{a}_ vs _{b}_"
        with st.expander(header, expanded=not item.get("resolved_by")):
            if item.get("reason"):
                st.write(item["reason"])
            if item.get("resolved_by"):
                st.caption(f"✅ Resolved by {item['resolved_by']}")
            else:
                st.caption("_Unresolved — ask the agent to investigate further._")
