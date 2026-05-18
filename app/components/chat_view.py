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
from app.components.text_utils import extract_wiki_refs


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
        elif kind in ("result", "session_start"):
            # chemclaw2 emits `session_start` early in the stream as an
            # optimization so the client can persist the resumed session_id
            # before end-of-turn, AND `result` at end-of-turn. Both carry it.
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

    Cancellation: between each SSE event we check `st.session_state.chat_cancel`.
    Streamlit's execution model means button widgets DO NOT fire callbacks
    mid-loop (the script doesn't yield to the event loop until it returns),
    so a Cancel button click is only consumed on the *next* fragment rerun.
    For a hard mid-stream interrupt, users rely on Streamlit's ⏸ Stop in
    the page menu — the `with httpx.stream(...)` context manager in
    `stream_chat` ensures the HTTP connection closes cleanly when the
    generator is garbage-collected on script termination.
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
        if st.session_state.get("chat_cancel"):
            text_buffer.append("\n\n_(cancelled)_")
            placeholder.markdown("".join(text_buffer))
            break
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
        elif kind in ("result", "session_start"):
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


def _reset_conversation() -> None:
    """Clear chat history + session id so the next prompt starts fresh."""
    st.session_state.chat_history = []
    st.session_state.chat_session_id = str(uuid.uuid4())
    st.session_state.pending_blocked = None
    st.session_state.chat_cancel = False


def _request_cancel() -> None:
    st.session_state.chat_cancel = True


def _render_history() -> None:
    """Replay the conversation transcript stored in session_state."""
    for i, (role, text) in enumerate(st.session_state.chat_history):
        with st.chat_message(role):
            st.markdown(text)
            if role == "assistant":
                _render_wiki_refs(text, key_prefix=f"hist_{i}")


def _render_wiki_refs(text: str, *, key_prefix: str) -> None:
    """If the assistant's reply mentions wiki pages via `[wiki:slug]`, surface
    them as clickable buttons that navigate to the wiki page.

    Streamlit's `st.markdown` already renders `[label](url)` syntax, but inline
    links can't cleanly trigger cross-page navigation in a multipage app. The
    expander + button pattern works reliably: the button click triggers a
    rerun, and `st.switch_page` lands the user on the right page.
    """
    refs = extract_wiki_refs(text)
    if not refs:
        return
    with st.expander(f"📚 Referenced wiki pages ({len(refs)})"):
        for slug in refs:
            if st.button(f"Open `{slug}`", key=f"{key_prefix}_ref_{slug}"):
                st.session_state.wiki_slug = slug
                st.session_state.wiki_mode = "view"
                st.switch_page("pages/wiki.py")


def _justification_form() -> None:
    """The override-justification form, shown when a prompt was blocked.

    The original user message has already been appended to chat_history
    (in `chat_fragment` before _consume ran) — we do NOT re-append it on
    submit, only re-issue the prompt to the agent with the justification.
    """
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


_RECENT_TOOL_USES_CAP = 20


def _commit_turn(result: ChatTurnResult) -> None:
    """Persist the assistant turn into chat_history and update session id."""
    if result.session_id:
        st.session_state.chat_session_id = result.session_id
    # Track recent tool_uses so the views dock can match on what the agent
    # has been doing (see app/views/*.matches). Capped to bound memory and
    # keep heuristics weighted toward recent activity.
    if result.tool_uses:
        recent = st.session_state.get("chat_recent_tool_uses") or []
        recent = (recent + list(result.tool_uses))[-_RECENT_TOOL_USES_CAP:]
        st.session_state.chat_recent_tool_uses = recent
    if result.assistant_text:
        st.session_state.chat_history.append(("assistant", result.assistant_text))
        # Render wiki-ref expander for the just-finished turn. On the next rerun
        # _render_history will replay it; this call surfaces it immediately
        # without waiting for the rerun.
        turn_idx = len(st.session_state.chat_history) - 1
        _render_wiki_refs(result.assistant_text, key_prefix=f"live_{turn_idx}")


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
    if "chat_cancel" not in st.session_state:
        st.session_state.chat_cancel = False
    # Stash plan_mode in session_state so the override-resubmit flow can read it.
    st.session_state.plan_mode = plan_mode

    # Toolbar: cancel + new-conversation. Buttons disabled when there's no
    # active conversation to act on.
    col_cancel, col_reset, _ = st.columns([1, 1, 6])
    with col_cancel:
        st.button(
            "🛑 Cancel",
            on_click=_request_cancel,
            disabled=not st.session_state.chat_history,
            help=(
                "Stops streaming between SSE events. For an immediate hard "
                "interrupt during a long tool call, use Streamlit's ⏸ Stop "
                "in the page menu."
            ),
        )
    with col_reset:
        st.button(
            "🔄 New conversation",
            on_click=_reset_conversation,
            disabled=not st.session_state.chat_history,
        )

    _render_history()

    # If a prior prompt was blocked, show the justification form first.
    if st.session_state.pending_blocked:
        _justification_form()
        return

    prompt = st.chat_input("Ask ChemClaw…")
    if not prompt:
        return

    # Clear any prior cancel before starting a new turn.
    st.session_state.chat_cancel = False

    st.session_state.chat_history.append(("user", prompt))
    with st.chat_message("user"):
        st.markdown(prompt)
    with st.chat_message("assistant"):
        result = _consume(prompt, st.session_state.chat_session_id, plan_mode=plan_mode)
    if result.blocked:
        # Stash and rerun so the justification form renders cleanly under the warning.
        st.session_state.pending_blocked = {
            "prompt": prompt,
            "reason": result.blocked.get("message", ""),
        }
        st.rerun()
    else:
        _commit_turn(result)
