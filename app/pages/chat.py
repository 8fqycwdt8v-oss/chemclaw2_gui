import streamlit as st

from app.components.chat_view import chat_fragment

st.title("Chat")

plan_mode = st.toggle(
    "Plan mode",
    value=False,
    help=(
        "Agent plans without executing tools. Useful for previewing what a "
        "complex request would do before authorising it."
    ),
)

chat_fragment(plan_mode=plan_mode)
