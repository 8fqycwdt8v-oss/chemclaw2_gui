"""Cross-page navigation helpers.

Centralises the session_state contract for navigating to the wiki page —
three call sites (subscriptions view, deep-research report, future agent
view-intent) all needed the same incantation. One helper, one place to
update if the wiki page path or state keys change.
"""

from __future__ import annotations

import streamlit as st


def navigate_to_wiki(slug: str | None = None, *, mode: str = "view") -> None:
    """Switch to the wiki page in the given mode.

    - mode="view" with a slug opens that page.
    - mode="new" opens the new-page form (slug ignored).
    - mode="list" returns to the page list.

    Also clears `active_view_id` so any open dock dialog closes on arrival.
    """
    if slug is not None:
        st.session_state["wiki_slug"] = slug
    st.session_state["wiki_mode"] = mode
    st.session_state["active_view_id"] = None
    st.switch_page("pages/wiki.py")
