"""Chat fragment: SSE parser + bubble renderer.

Handles the four `SDKMessage` envelope types emitted by chemclaw2's
`/api/chat` endpoint (see `chemclaw2/apps/web/lib/streaming.ts`).
Works whether the backend has `includePartialMessages: true` (token-
by-token streaming) or not (bubble-at-end-of-turn).
"""

import json
import uuid
from collections.abc import Iterator
from typing import Any

import streamlit as st

from app.components.api_client import stream_chat


def _parse_sse(stream: Iterator[bytes]) -> Iterator[dict[str, Any] | str]:
    """Yield each `data:` payload from an SSE byte stream as parsed JSON,
    or the literal string for sentinels like `[DONE]`."""
    buffer = ""
    for chunk in stream:
        buffer += chunk.decode("utf-8", errors="replace")
        while "\n\n" in buffer:
            event, buffer = buffer.split("\n\n", 1)
            for line in event.splitlines():
                if not line.startswith("data:"):
                    continue
                payload = line[5:].strip()
                if payload == "[DONE]":
                    yield "[DONE]"
                    return
                try:
                    yield json.loads(payload)
                except json.JSONDecodeError:
                    continue


def _render_assistant_blocks(message: dict[str, Any]) -> None:
    for block in message.get("content", []) or []:
        if block.get("type") == "text":
            st.markdown(block.get("text", ""))
        elif block.get("type") == "tool_use":
            name = block.get("name", "tool")
            st.info(f"→ {name}(…)")


def _consume(prompt: str, session_id: str | None) -> str | None:
    """Stream one assistant turn into the current chat_message container.
    Returns the new session_id surfaced by chemclaw2 (if any)."""
    placeholder = st.empty()
    buffer = ""
    final_session_id: str | None = None
    for event in _parse_sse(stream_chat(prompt, session_id)):
        if event == "[DONE]":
            break
        if not isinstance(event, dict):
            continue
        kind = event.get("type")
        if kind == "stream_event":
            inner = event.get("event", {})
            if inner.get("type") == "content_block_delta":
                delta = inner.get("delta", {})
                if delta.get("type") == "text_delta":
                    buffer += delta.get("text", "")
                    placeholder.markdown(buffer)
        elif kind == "assistant":
            buffer = ""
            placeholder.empty()
            _render_assistant_blocks(event.get("message", {}))
        elif kind == "result":
            # chemclaw2 backend emits `session_id` (snake_case).
            final_session_id = event.get("session_id") or final_session_id
        elif kind == "error":
            st.error(f"Backend error (id: {event.get('errorId', '?')})")
    return final_session_id


@st.fragment
def chat_fragment() -> None:
    """Streamlit fragment encapsulating the chat input and history.

    Wrapping in `@st.fragment` (stable since v1.38) prevents the surrounding
    app from re-running on every user message — only this fragment re-runs.
    """
    if "chat_history" not in st.session_state:
        st.session_state.chat_history = []  # list[(role, text)]
    if "chat_session_id" not in st.session_state:
        st.session_state.chat_session_id = str(uuid.uuid4())

    for role, text in st.session_state.chat_history:
        with st.chat_message(role):
            st.markdown(text)

    prompt = st.chat_input("Ask ChemClaw…")
    if not prompt:
        return

    st.session_state.chat_history.append(("user", prompt))
    with st.chat_message("user"):
        st.markdown(prompt)
    with st.chat_message("assistant"):
        new_session = _consume(prompt, st.session_state.chat_session_id)
        if new_session:
            st.session_state.chat_session_id = new_session
    # We don't append the assistant turn to history here because the rendered
    # content lives in placeholders; on the next fragment rerun, only the
    # user message is replayed. This is a known v1 trade-off — full
    # transcript persistence is deferred until we add backend-side history fetch.
