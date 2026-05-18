# BACKLOG

Append-only log of deferred work. One bullet per item, prefixed by area. Resolve by deleting the line in the same PR that lands the work (or moves it elsewhere).

## chemclaw2 backend routes the GUI wants (blocking specialised views)

- [views/campaigns] Need `GET /api/campaigns?status=` and `GET /api/campaigns/{id}` exposing `SynthesisCampaign` + nested `CampaignStep` rows. Today the data is reachable only via agent tools (`start_synthesis_campaign`, `confirm_synthesis_plan`). Without these, the `campaign_progress` view in `app/views/` stays in stub mode.
- [views/todos] Need `GET /api/todos/{session_id}` returning `AgentTodo` rows for the session. Subagents (deep-research) populate this table but the GUI can't read it. Stubs the `agent_todos` view.
- [views/contradictions] Need `GET /api/wiki/{slug}` extended to return `contradictions: WikiContradiction[]` (today returns only `citations[]`). OR a new `GET /api/wiki/{slug}/contradictions` route. Stubs the `contradiction_triage` view.
- [views/notifications] Need `GET /api/notifications` for proactive alerts (story 3.5, 3.10). Defer; not currently stubbed.

## chemclaw2 backend changes for GUI feature completeness

- [auth] Service-token verifier in `chemclaw2/api/auth.py` accepting `Bearer svc.<sub>.<iat>.<sig>` with a maxAge window on `iat` (recommended 300s). Until shipped, production must use chemclaw2's dev `mock:<sub>` path which is not a real production auth model.
- [chat] Set `include_partial_messages=True` in `chemclaw2/api/agent/runner.py:ClaudeAgentOptions` so the GUI can render token-by-token streaming. Today bubbles arrive whole.
- [chat] Add a system-prompt instruction to chemclaw2's `BASE_SYSTEM_PROMPT` teaching the agent to emit `[wiki:slug]` when citing org wiki pages. The GUI parses these into clickable deep-link buttons (`extract_wiki_refs` in `app/components/text_utils.py`). Until shipped, the "📚 Referenced wiki pages" expander only renders for prompts where the agent happens to use the syntax.
- [chat] (Optional Phase 2) Add `{type: "view", view_id, payload}` SSE envelope so the agent can explicitly trigger a specialised view. Dispatch target is `app/views/__init__.py:VIEWS`. Until shipped, view activation is heuristic (context matchers) + user (quick-open) only.

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
