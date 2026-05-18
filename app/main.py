import streamlit as st

from app.config import LOGIN_PROVIDER

st.set_page_config(page_title="ChemClaw", page_icon="⚗️", layout="wide")

if not st.user.is_logged_in:
    st.title("ChemClaw")
    st.write("Pharma R&D knowledge-intelligence agent.")
    st.button("Sign in", on_click=st.login, args=(LOGIN_PROVIDER,), type="primary")
    st.stop()


def _render_backend_health() -> None:
    """Show chemclaw2 backend liveness + fingerprint backlog. Cached 30s."""
    from app.components.api_client import get_backend_health

    h = get_backend_health()
    if not h.get("ok"):
        st.error(f"⚠️ Backend down: {h.get('error', 'unknown error')}")
        return
    db_ok = h.get("db")
    backlog = h.get("fingerprint_backlog") or {}
    pending = (backlog.get("compounds") or 0) + (backlog.get("reactions") or 0)
    status = "🟢 healthy" if db_ok else "🟠 degraded (db)"
    if h.get("worker_warn"):
        status = "🟠 worker backlog"
    with st.expander(f"Backend · {status}", expanded=False):
        st.caption(f"DB reachable: {'✓' if db_ok else '✗'}")
        st.caption(f"Pending fingerprints: {pending}")
        if h.get("worker_warn"):
            st.warning("Worker is behind. New compounds/reactions search may miss recent rows.")


with st.sidebar:
    # Entra ID may surface email under `preferred_username`; Auth0 uses `email`.
    label = st.user.get("email") or st.user.get("preferred_username") or "(no email claim)"
    st.write(f"Signed in as **{label}**")
    st.button("Sign out", on_click=st.logout)
    st.divider()
    _render_backend_health()
    st.divider()
    from app.components.views_dock import render_dock

    render_dock()

pages = [
    st.Page("pages/chat.py", title="Chat", icon="💬", default=True),
    st.Page("pages/wiki.py", title="Wiki", icon="📚"),
    st.Page("pages/search.py", title="Search", icon="🔎"),
]
st.navigation(pages).run()
