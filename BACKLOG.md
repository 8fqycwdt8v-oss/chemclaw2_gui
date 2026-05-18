# BACKLOG

Append-only log of deferred work. One bullet per item, prefixed by area. Resolve by deleting the line in the same PR that lands the work (or moves it elsewhere).

## chemclaw2 backend changes for GUI feature completeness

- [chat] Set `include_partial_messages=True` in `chemclaw2/api/agent/runner.py:ClaudeAgentOptions` so the GUI can render token-by-token streaming. Today bubbles arrive whole.
- [chat] Add a system-prompt instruction to chemclaw2's `BASE_SYSTEM_PROMPT` teaching the agent to emit `[wiki:slug]` when citing org wiki pages. The GUI parses these into clickable deep-link buttons (`extract_wiki_refs` in `app/components/text_utils.py`). Until shipped, the "📚 Referenced wiki pages" expander only renders for prompts where the agent happens to use the syntax.
- [chat] (Optional Phase 2) Add `{type: "view", view_id, payload}` SSE envelope so the agent can explicitly trigger a specialised view. Dispatch target is `app/views/__init__.py:VIEWS`. Until shipped, view activation is heuristic (context matchers) + user (quick-open) only.
- [views/notifications] `GET /api/notifications` + `PATCH /api/notifications` are implemented in chemclaw2 but not yet wired in the GUI. Add `get_notifications()` to `api_client.py` and a `app/views/notifications.py` view.

## GUI follow-ups (no backend dependency)

- [wiki] Revision history view — `version` column exists on `wiki_pages` but no history endpoint yet on chemclaw2.
- [chat] Hard cancellation via Streamlit Stop button is documented but a custom in-context cancel button only works between SSE events (Streamlit limitation). Investigate `httpx.AsyncClient` + thread cancellation if users actually hit this.
- [search] Render compound similarity results with inline RDKit SVG thumbnails instead of bare dataframe.
- [search] Cross-project scope toggle on similarity search — blocked on chemclaw2 search accepting a `project` filter.
- [views] Persist `dock_pinned` to a browser storage (`st.cache_data` is in-memory; survives reruns but not browser refresh).

## Known limitations (documented; not necessarily fixed)

- [streamlit] No `beforeunload` guard for unsaved wiki edits — pure-Streamlit can't hook the browser event without a custom JS component. Dirty marker + Discard confirmation is best-effort.
- [streamlit] `st.dialog` allows only one open at a time per session. The views dock uses pinnable cards for multi-open + one focused dialog at a time.
- [intel-mac] RDKit dropped Intel-Mac wheels after 2024.3.5. Local dev uses `uv sync --no-install-package rdkit`; full validation via Docker.

## How to use this file

- **Adding an item**: one bullet, area-prefixed in `[brackets]`. Keep it under 2 lines. If you need a paragraph, the right place is a design doc.
- **Resolving an item**: delete the line in the same commit that fixes it. Don't accumulate "DONE" markers.
- **Stale check**: every contributor should skim this on PR open. Items that no longer apply get deleted.
