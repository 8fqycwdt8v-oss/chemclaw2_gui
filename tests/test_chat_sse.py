"""Chat SSE dispatch — lock in the contract against chemclaw2's flat envelope shape.

These tests cover the pure functions (`parse_sse`, `dispatch_events`) so they
run without booting Streamlit. They mirror the runtime renderer's semantics
exactly — when both pass, we know the live UI will behave the same way.
"""

from app.components.chat_view import dispatch_events, parse_sse


def _sse(*lines: str) -> list[bytes]:
    """Convenience: build a list of SSE byte chunks from raw `data:` lines."""
    body = "".join(f"data: {line}\n\n" for line in lines)
    return [body.encode()]


def test_parse_sse_yields_each_data_payload() -> None:
    chunks = _sse('{"type":"text","text":"hello"}', '{"type":"text","text":" world"}')
    events = list(parse_sse(chunks))
    assert events == [{"type": "text", "text": "hello"}, {"type": "text", "text": " world"}]


def test_parse_sse_stops_at_done_sentinel() -> None:
    chunks = _sse('{"type":"text","text":"a"}', "[DONE]", '{"type":"text","text":"b"}')
    events = list(parse_sse(chunks))
    assert events == [{"type": "text", "text": "a"}, "[DONE]"]


def test_parse_sse_handles_chunk_boundaries_mid_event() -> None:
    # Split one SSE event across two byte chunks
    chunks = [b'data: {"type":"text","tex', b't":"split"}\n\n']
    events = list(parse_sse(chunks))
    assert events == [{"type": "text", "text": "split"}]


def test_parse_sse_skips_malformed_json() -> None:
    chunks = _sse("{not json", '{"type":"text","text":"ok"}')
    events = list(parse_sse(chunks))
    assert events == [{"type": "text", "text": "ok"}]


def test_dispatch_concatenates_text_blocks() -> None:
    events = [
        {"type": "text", "text": "Hello "},
        {"type": "text", "text": "world."},
        {"type": "result", "session_id": "s-1", "stop_reason": "end_turn"},
        "[DONE]",
    ]
    r = dispatch_events(events)
    assert r.assistant_text == "Hello world."
    assert r.session_id == "s-1"
    assert r.done is True
    assert r.error is None
    assert r.blocked is None


def test_dispatch_captures_tool_uses_in_order() -> None:
    events = [
        {"type": "text", "text": "Looking that up. "},
        {"type": "tool_use", "name": "wiki_lookup"},
        {"type": "tool_use", "name": "web_search"},
        {"type": "text", "text": "Done."},
        {"type": "result", "session_id": "s-2"},
        "[DONE]",
    ]
    r = dispatch_events(events)
    assert r.tool_uses == ["wiki_lookup", "web_search"]
    assert r.assistant_text == "Looking that up. Done."


def test_dispatch_marks_blocked_when_override_available() -> None:
    events = [
        {
            "type": "error",
            "message": "Request blocked: synthesis instructions for scheduled/"
            "controlled substances are not permitted.",
            "blocked": True,
            "override_available": True,
        },
        "[DONE]",
    ]
    r = dispatch_events(events)
    assert r.blocked is not None
    assert r.blocked["blocked"] is True
    assert r.error is None  # blocked-with-override is NOT a plain error


def test_dispatch_treats_plain_error_as_error() -> None:
    events = [
        {"type": "error", "message": "An internal error occurred"},
        "[DONE]",
    ]
    r = dispatch_events(events)
    assert r.error == "An internal error occurred"
    assert r.blocked is None


def test_dispatch_blocked_without_override_is_plain_error() -> None:
    # Per chemclaw2/api/agent/runner.py line 82, the inline gate emits blocked:true
    # WITHOUT override_available. That path should surface as a plain error so the
    # GUI doesn't show an override form for a request that can't be retried.
    events = [
        {"type": "error", "message": "blocked", "blocked": True},
        "[DONE]",
    ]
    r = dispatch_events(events)
    assert r.error == "blocked"
    assert r.blocked is None


def test_dispatch_handles_no_done_sentinel() -> None:
    # Stream cut off mid-flight (e.g., proxy timeout). Should still return a
    # well-formed result with done=False.
    events = [{"type": "text", "text": "partial"}]
    r = dispatch_events(events)
    assert r.assistant_text == "partial"
    assert r.done is False


def test_dispatch_captures_session_id_from_session_start() -> None:
    # chemclaw2 emits `session_start` early in the stream so the client knows
    # the resumed session_id before end-of-turn. Both this and `result` should
    # populate session_id; result wins if different (shouldn't be, but tested).
    events = [
        {"type": "session_start", "session_id": "s-early"},
        {"type": "text", "text": "hi"},
        {"type": "result", "session_id": "s-final"},
        "[DONE]",
    ]
    r = dispatch_events(events)
    assert r.session_id == "s-final"


def test_dispatch_session_start_alone_still_captured() -> None:
    # If the stream is cut between session_start and result, we still know
    # the session_id from the early envelope.
    events = [
        {"type": "session_start", "session_id": "s-only"},
        {"type": "text", "text": "interrupted"},
    ]
    r = dispatch_events(events)
    assert r.session_id == "s-only"
    assert r.done is False


def test_dispatch_view_intent_collected() -> None:
    # chemclaw2 may emit `{type:"view", view_id, payload?}` to request the
    # GUI open a specialised view. The dispatcher collects them; the chat
    # fragment renders Open buttons after the turn.
    events = [
        {"type": "text", "text": "Started campaign CAMP-42."},
        {"type": "view", "view_id": "campaign", "payload": {"id": "CAMP-42"}},
        {"type": "result", "session_id": "s"},
        "[DONE]",
    ]
    r = dispatch_events(events)
    assert r.view_intents == [{"view_id": "campaign", "payload": {"id": "CAMP-42"}}]


def test_dispatch_view_intent_without_payload_defaults_to_empty_dict() -> None:
    events = [
        {"type": "view", "view_id": "research"},
        "[DONE]",
    ]
    r = dispatch_events(events)
    assert r.view_intents == [{"view_id": "research", "payload": {}}]


def test_dispatch_view_intent_skips_malformed() -> None:
    # Missing or non-string view_id → silently ignored. The contract is the
    # backend's job to keep; defensive on our side because corrupt envelopes
    # shouldn't crash the chat fragment.
    events = [
        {"type": "view"},  # no view_id
        {"type": "view", "view_id": 123},  # wrong type
        {"type": "view", "view_id": ""},  # empty
        {"type": "view", "view_id": "good", "payload": {"x": 1}},
        "[DONE]",
    ]
    r = dispatch_events(events)
    assert r.view_intents == [{"view_id": "good", "payload": {"x": 1}}]


def test_dispatch_multiple_view_intents_preserved_in_order() -> None:
    events = [
        {"type": "view", "view_id": "campaign"},
        {"type": "text", "text": "..."},
        {"type": "view", "view_id": "todos"},
        "[DONE]",
    ]
    r = dispatch_events(events)
    assert [vi["view_id"] for vi in r.view_intents] == ["campaign", "todos"]
