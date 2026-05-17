"""Chat fragment: SSE parser + dispatcher + Streamlit renderer.

chemclaw2's `/api/chat` SSE stream (see `chemclaw2/api/agent/runner.py`)
emits flat envelope types per AssistantMessage content block:
  - {type: "text", text: str}                                  per text block
  - {type: "tool_use", name: str}                              per tool invocation
  - {type: "result", session_id, stop_reason}                  end-of-turn
  - {type: "error", message, blocked?, override_available?}    error
  - `[DONE]` sentinel string                                   stream terminator

The dispatcher is a pure function (`dispatch_events`) so it's testable
without booting Streamlit. The fragment is the thin Streamlit-aware layer.
"""

import json
import uuid
from collections.abc import Iterable, Iterator
from dataclasses import dataclass, field
from typing import Any

import streamlit as st

from app.components.api_client import stream_chat


@dataclass
class ChatTurnResult:
    """The structured outcome of one assistant turn after SSE consumption."""

    assistant_text: str = ""
    tool_uses: list[str] = field(default_factory=list)
    session_id: str | None = None
    blocked: dict[str, Any] | None = None  # full error envelope when blocked
    error: str | None = None  # non-blocking error message
    done: bool = False


def parse_sse(stream: Iterable[bytes]) -> Iterator[dict[str, Any] | str]:
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


def dispatch_events(events: Iterable[dict[str, Any] | str]) -> ChatTurnResult:
    """Reduce an event stream into a ChatTurnResult. Pure function, no I/O.

    Mirrors the runtime renderer's semantics so tests can lock in dispatch
    behavior without Streamlit. The runtime renderer calls this OR streams
    incrementally via the same envelope types — both must agree.
    """
    result = ChatTurnResult()
    text_parts: list[str] = []
    for event in events:
        if event == "[DONE]":
            result.done = True
            break
        if not isinstance(event, dict):
            continue
        kind = event.get("type")
        if kind == "text":
            text_parts.append(event.get("text", ""))
        elif kind == "tool_use":
            result.tool_uses.append(event.get("name", ""))
        elif kind == "result":
            result.session_id = event.get("session_id") or result.session_id
        elif kind == "error":
            if event.get("blocked") and event.get("override_available"):
                result.blocked = event
            else:
                result.error = event.get("message") or "Unknown error"
    result.assistant_text = "".join(text_parts)
    return result


def _consume(
    prompt: str,
    session_id: str | None,
    *,
    plan_mode: bool = False,
    override_justification: str | None = None,
) -> ChatTurnResult:
    """Stream one assistant turn into the current chat_message container.

    Renders incrementally: each `text` event extends a live markdown placeholder;
    each `tool_use` event renders an info pill inline; errors and blocks are
    rendered immediately. Returns the same `ChatTurnResult` `dispatch_events`
    would produce — verified by tests.
    """
    placeholder = st.empty()
    text_buffer: list[str] = []
    result = ChatTurnResult()
    stream = stream_chat(
        prompt,
        session_id,
        plan_mode=plan_mode,
        override_justification=override_justification,
    )
    for event in parse_sse(stream):
        if event == "[DONE]":
            result.done = True
            break
        if not isinstance(event, dict):
            continue
        kind = event.get("type")
        if kind == "text":
            text_buffer.append(event.get("text", ""))
            placeholder.markdown("".join(text_buffer))
        elif kind == "tool_use":
            name = event.get("name", "tool")
            result.tool_uses.append(name)
            st.info(f"→ {name}(…)")
        elif kind == "result":
            result.session_id = event.get("session_id") or result.session_id
        elif kind == "error":
            if event.get("blocked") and event.get("override_available"):
                result.blocked = event
                st.warning(event.get("message", "Request blocked."))
            else:
                result.error = event.get("message") or "Unknown error"
                st.error(result.error)
    result.assistant_text = "".join(text_buffer)
    return result


def _render_history() -> None:
    """Replay the conversation transcript stored in session_state."""
    for role, text in st.session_state.chat_history:
        with st.chat_message(role):
            st.markdown(text)


def _handle_blocked(blocked: dict[str, Any], original_prompt: str) -> None:
    """Render the override-justification flow inside the current chat_message.

    User chooses Submit (re-runs prompt with override) or Cancel.
    Stores intent in session_state so the next fragment rerun resumes correctly.
    """
    st.session_state.pending_blocked = {
        "prompt": original_prompt,
        "reason": blocked.get("message", ""),
    }


def _justification_form() -> None:
    """The override-justification form, shown when a prompt was blocked."""
    pending = st.session_state.pending_blocked
    with st.chat_message("assistant"):
        st.warning(pending["reason"])
        with st.form(key="override_form", clear_on_submit=True):
            justification = st.text_area(
                "Justification (20-2000 chars)",
                help="Explain the legitimate research need. Logged for audit.",
                max_chars=2000,
            )
            c1, c2 = st.columns(2)
            with c1:
                submitted = st.form_submit_button("Submit override", type="primary")
            with c2:
                cancelled = st.form_submit_button("Cancel")
        if cancelled:
            st.session_state.pending_blocked = None
            st.session_state.chat_history.append(
                ("assistant", f"_(blocked: {pending['reason']} — override declined)_")
            )
            st.rerun()
        elif submitted:
            if len(justification.strip()) < 20:
                st.error("Justification must be at least 20 characters.")
                return
            # Re-issue the prompt with the override.
            st.session_state.chat_history.append(("user", pending["prompt"]))
            with st.chat_message("user"):
                st.markdown(pending["prompt"])
            with st.chat_message("assistant"):
                result = _consume(
                    pending["prompt"],
                    st.session_state.chat_session_id,
                    plan_mode=st.session_state.get("plan_mode", False),
                    override_justification=justification.strip(),
                )
                _commit_turn(result)
            st.session_state.pending_blocked = None
            st.rerun()


def _commit_turn(result: ChatTurnResult) -> None:
    """Persist the assistant turn into chat_history and update session id."""
    if result.session_id:
        st.session_state.chat_session_id = result.session_id
    if result.assistant_text:
        st.session_state.chat_history.append(("assistant", result.assistant_text))


@st.fragment
def chat_fragment(plan_mode: bool = False) -> None:
    """Streamlit fragment encapsulating the chat input and history.

    Wrapping in `@st.fragment` (stable since v1.38) prevents the surrounding
    app from re-running on every user message — only this fragment re-runs.
    """
    if "chat_history" not in st.session_state:
        st.session_state.chat_history = []  # list[(role, text)]
    if "chat_session_id" not in st.session_state:
        st.session_state.chat_session_id = str(uuid.uuid4())
    if "pending_blocked" not in st.session_state:
        st.session_state.pending_blocked = None
    # Stash plan_mode in session_state so the override-resubmit flow can read it.
    st.session_state.plan_mode = plan_mode

    _render_history()

    # If a prior prompt was blocked, show the justification form first.
    if st.session_state.pending_blocked:
        _justification_form()
        return

    prompt = st.chat_input("Ask ChemClaw…")
    if not prompt:
        return

    st.session_state.chat_history.append(("user", prompt))
    with st.chat_message("user"):
        st.markdown(prompt)
    with st.chat_message("assistant"):
        result = _consume(prompt, st.session_state.chat_session_id, plan_mode=plan_mode)
        if result.blocked:
            _handle_blocked(result.blocked, prompt)
            # Trigger a rerun so the form renders cleanly under the warning.
            st.rerun()
        _commit_turn(result)
