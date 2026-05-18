"""Campaign progress view.

Lists the user's synthesis campaigns and lets them drill into a single
campaign to see step-by-step status. Activates when the agent has invoked
a campaign tool in the current session.
"""

from __future__ import annotations

from typing import Any

import streamlit as st

from app.components.api_client import get_campaign, list_campaigns

ID = "campaign"
LABEL = "Campaign progress"
ICON = "🧪"
COMMANDS = ("campaign", "campaigns", "bo")

_CAMPAIGN_TOOL_NAMES = {"start_synthesis_campaign", "confirm_synthesis_plan"}

_STATUS_EMOJI = {
    "pending": "⏳",
    "running": "🔄",
    "complete": "✅",
    "failed": "❌",
    "cancelled": "🚫",
}


def matches(state: dict[str, Any]) -> bool:
    recent = state.get("chat_recent_tool_uses") or []
    return any(t in _CAMPAIGN_TOOL_NAMES for t in recent)


def render_card(state: dict[str, Any]) -> None:
    recent = state.get("chat_recent_tool_uses") or []
    active = sum(1 for t in recent if t in _CAMPAIGN_TOOL_NAMES)
    st.write(f"{ICON} **{LABEL}** · {active} campaign tool{'s' if active != 1 else ''} used")


def _step_table(steps: list[dict]) -> None:
    if not steps:
        st.caption("No steps yet.")
        return
    for step in sorted(steps, key=lambda s: s.get("step_idx", 0)):
        emoji = _STATUS_EMOJI.get(step.get("status", ""), "•")
        label = step.get("reaction_smiles") or f"Step {step.get('step_idx', '?')}"
        with st.expander(f"{emoji} {label}", expanded=step.get("status") == "running"):
            cols = st.columns(2)
            with cols[0]:
                st.caption(f"Status: **{step.get('status', '?')}**")
                if step.get("conditions"):
                    st.caption(f"Conditions: {step['conditions']}")
            with cols[1]:
                if step.get("result"):
                    st.caption("Result")
                    st.json(step["result"], expanded=False)
            if step.get("retry_count"):
                st.caption(f"Retries: {step['retry_count']}")


def render(state: dict[str, Any]) -> None:
    selected_id = st.session_state.get("_campaign_view_id")

    if selected_id:
        if st.button("← All campaigns", key="campaign_back"):
            del st.session_state["_campaign_view_id"]
            st.rerun()
        try:
            data = get_campaign(selected_id)
        except Exception as exc:  # noqa: BLE001
            st.error(f"Failed to load campaign: {exc}")
            return
        campaign = data.get("campaign") or data
        status = campaign.get("status", "?")
        emoji = _STATUS_EMOJI.get(status, "•")
        st.subheader(f"{emoji} {campaign.get('target_smiles') or selected_id}")
        st.caption(
            f"Session: {campaign.get('session_id', '—')}  ·  "
            f"Created: {campaign.get('created_at', '—')}"
        )
        _step_table(data.get("steps") or [])
        return

    try:
        data = list_campaigns()
    except Exception as exc:  # noqa: BLE001
        st.error(f"Failed to load campaigns: {exc}")
        return

    campaigns = data.get("campaigns") or []
    if not campaigns:
        st.info("No campaigns yet. Ask the agent to start a synthesis campaign.")
        return

    for c in campaigns:
        status = c.get("status", "?")
        emoji = _STATUS_EMOJI.get(status, "•")
        target = c.get("target_smiles") or c.get("id", "?")
        col1, col2 = st.columns([5, 1])
        with col1:
            st.write(f"{emoji} **{target}**")
            st.caption(f"{status}  ·  {c.get('updated_at', '')}")
        with col2:
            if st.button("Open", key=f"campaign_open_{c['id']}"):
                st.session_state["_campaign_view_id"] = c["id"]
                st.rerun()
