"""Deep-research report view.

chemclaw2's deep-research sub-agent (api/agent/runner.py: DEEP_RESEARCH_PROMPT)
returns a structured 3-6 section markdown report with inline `[N]` citation
markers. We detect this shape heuristically in the assistant's last reply
and offer a focused viewer + Save-to-wiki action.

No backend route needed — the report arrives as ordinary chat text.
"""

from __future__ import annotations

import re
from typing import Any

import streamlit as st

ID = "research"
LABEL = "Research report"
ICON = "📄"
COMMANDS = ("research", "report")

# A deep-research reply has ≥3 H2 headings and ≥1 inline citation marker.
# Heuristic, not a contract — false positives mean a spurious card the user
# can dismiss; false negatives mean they fall back to scrolling chat.
_HEADING_RE = re.compile(r"^##\s+\S", re.MULTILINE)
_CITATION_RE = re.compile(r"\[\^?\d+\]")


def matches(state: dict[str, Any]) -> bool:
    text = state.get("chat_assistant_text_last") or ""
    return len(_HEADING_RE.findall(text)) >= 3 and bool(_CITATION_RE.search(text))


def _section_count(text: str) -> int:
    return len(_HEADING_RE.findall(text))


def render_card(state: dict[str, Any]) -> None:
    text = state.get("chat_assistant_text_last") or ""
    st.write(f"{ICON} **{LABEL}** · {_section_count(text)} sections")


def render(state: dict[str, Any]) -> None:
    text = state.get("chat_assistant_text_last") or ""
    if not text:
        st.info("No research report in the current session.")
        return
    st.markdown(text)
    st.divider()
    col1, col2 = st.columns(2)
    with col1:
        # Quick-save: prefills the new-wiki-page form via session_state and
        # jumps to the wiki page. The user fills in slug+title and saves.
        if st.button("💾 Save to wiki", key="research_save_to_wiki"):
            st.session_state.wiki_mode = "new"
            st.session_state.wiki_prefill_markdown = text
            st.session_state.active_view_id = None  # close dialog
            st.switch_page("pages/wiki.py")
    with col2:
        st.download_button(
            "⬇ Download .md",
            data=text,
            file_name="research_report.md",
            mime="text/markdown",
            key="research_download_md",
        )
