"""Wiki revision history view.

Activates whenever the user is on a wiki page. Lists revisions (one row per
version) and lets the user drill into a specific version to see its content.
Read-only — restore-to-version is a backend BACKLOG item (route exists for
read, not for restore).
"""

from __future__ import annotations

from typing import Any

import streamlit as st

from app.components.api_client import get_wiki_revision, get_wiki_revisions
from app.components.text_utils import relative_time

ID = "wiki_revisions"
LABEL = "Revision history"
ICON = "📜"
COMMANDS = ("revisions", "history", "versions")


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
        st.info("Open a wiki page to see its revision history.")
        return

    selected_version = st.session_state.get("_revisions_selected_version")
    if selected_version is not None:
        _render_single_version(slug, selected_version)
        return

    try:
        data = get_wiki_revisions(slug)
    except Exception as exc:  # noqa: BLE001
        st.error(f"Failed to load revisions for `{slug}`: {exc}")
        return

    revisions = data.get("revisions") or []
    if not revisions:
        st.info(f"No revision history for `{slug}` yet.")
        return

    st.caption(f"{len(revisions)} revision{'s' if len(revisions) != 1 else ''}")
    for rev in revisions:
        version = rev.get("version", "?")
        title = rev.get("title", slug)
        when = relative_time(rev.get("updated_at"))
        by = rev.get("updated_by") or "system"
        col1, col2 = st.columns([5, 1])
        with col1:
            st.write(f"**v{version}** · {title}")
            st.caption(f"{when} · by `{by}`")
        with col2:
            if st.button("View", key=f"rev_view_{version}"):
                st.session_state["_revisions_selected_version"] = version
                st.rerun()


def _render_single_version(slug: str, version: int) -> None:
    if st.button("← Back to history", key="rev_back"):
        del st.session_state["_revisions_selected_version"]
        st.rerun()
    try:
        rev = get_wiki_revision(slug, version)
    except Exception as exc:  # noqa: BLE001
        st.error(f"Failed to load v{version} of `{slug}`: {exc}")
        return
    st.subheader(f"v{rev.get('version')} · {rev.get('title', slug)}")
    st.caption(
        f"{relative_time(rev.get('updated_at'))} · by `{rev.get('updated_by') or 'system'}`"
    )
    st.divider()
    text = rev.get("content_text") or "_(empty)_"
    st.markdown(text)
