import streamlit as st

from app.config import LOGIN_PROVIDER

st.set_page_config(page_title="ChemClaw", page_icon="⚗️", layout="wide")

if not st.user.is_logged_in:
    st.title("ChemClaw")
    st.write("Pharma R&D knowledge-intelligence agent.")
    st.button("Sign in", on_click=st.login, args=(LOGIN_PROVIDER,), type="primary")
    st.stop()

with st.sidebar:
    # Entra ID may surface email under `preferred_username`; Auth0 uses `email`.
    label = st.user.get("email") or st.user.get("preferred_username") or "(no email claim)"
    st.write(f"Signed in as **{label}**")
    st.button("Sign out", on_click=st.logout)

pages = [
    st.Page("pages/chat.py", title="Chat", icon="💬", default=True),
    st.Page("pages/wiki.py", title="Wiki", icon="📚"),
    st.Page("pages/search.py", title="Search", icon="🔎"),
]
st.navigation(pages).run()
