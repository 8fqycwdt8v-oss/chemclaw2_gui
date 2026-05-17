import streamlit as st

from app.config import LOGIN_PROVIDER

st.set_page_config(page_title="ChemClaw", page_icon="⚗️", layout="wide")

if not st.user.is_logged_in:
    st.title("ChemClaw")
    st.write("Pharma R&D knowledge-intelligence agent.")
    st.button("Sign in", on_click=st.login, args=(LOGIN_PROVIDER,), type="primary")
    st.stop()

with st.sidebar:
    st.write(f"Signed in as **{st.user.email}**")
    st.button("Sign out", on_click=st.logout)

pages = [
    st.Page("pages/chat.py", title="Chat", icon="💬", default=True),
    st.Page("pages/wiki.py", title="Wiki", icon="📚"),
    st.Page("pages/search.py", title="Search", icon="🔎"),
]
st.navigation(pages).run()
