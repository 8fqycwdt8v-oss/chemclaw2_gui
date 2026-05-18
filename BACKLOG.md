# BACKLOG

Append-only log of deferred work. One bullet per item, prefixed by area. Resolve by deleting the line in the same PR that lands the work (or moves it elsewhere).

## chemclaw2 backend changes (GUI is ready when these ship)

- [chemclaw2/chat/partials] Set `include_partial_messages=True` in `chemclaw2/api/agent/runner.py:ClaudeAgentOptions` so the GUI can render token-by-token streaming. The GUI's `chat_view.dispatch_events` already handles whatever partial envelopes the SDK emits; today bubbles arrive whole because the option is off.
- [chemclaw2/chat/wiki-refs] Append to `BASE_SYSTEM_PROMPT` in `chemclaw2/api/agent/runner.py`: *"When you cite an org wiki page, embed `[wiki:slug]` (lowercase-with-hyphens) so the UI can offer a direct navigation link."* The GUI's `extract_wiki_refs` (`app/components/text_utils.py`) parses these into a "📚 Referenced wiki pages" expander. Until shipped, only fires when the agent happens to use the syntax.
- [chemclaw2/chat/view-intent] Emit `{type: "view", view_id, payload?}` SSE envelopes when a tool's result deserves a specialised UI surface. The GUI dispatch is already wired in `chat_view.dispatch_events` (handles the new envelope and renders an "Open in <View>" button below the assistant turn). Currently a no-op because chemclaw2 doesn't emit. Suggested trigger points: after `start_synthesis_campaign` → `{view_id:"campaign"}`; after `record_contradiction` → `{view_id:"contradictions"}`; when the deep-research subagent finishes → `{view_id:"research"}`.

## GUI follow-ups (no backend dependency)

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
