# chemclaw2_gui

Single-container Streamlit GUI for chemclaw2. No backend, no BFF — Streamlit
calls chemclaw2's FastAPI directly.

## Hard rules

1. **Backend lives in chemclaw2.** Do not duplicate Claude Agent SDK orchestration, DB queries, or MCP server logic here. The GUI calls chemclaw2 over HTTP; chemistry compute (RDKit/DRFP fingerprints) happens in `app/components/chem.py` only because chemclaw2's `/api/search` accepts pre-computed bits.
2. **Markdown-source wiki, not Tiptap.** The trade-off was chosen deliberately. Do not reintroduce Tiptap/React rich-text components.
3. **No JS toolchain.** Pure Python. The only React assets in the build come bundled inside `streamlit-ketcher` and `streamlit-markdown`.
4. **Off-the-shelf over self-built.** If a Streamlit component or PyPI package covers a need, use it. If it doesn't, defer rather than build a custom React component.
5. **Minimum code.** Repo target is under 1,000 application LOC. Project-wide ceiling across chemclaw2 + chemclaw2_gui is 6,000 LOC at v1.

## Stack

| Layer | Tech |
|---|---|
| GUI | Streamlit (+ st.fragment for partial reruns) |
| Streaming chat | `streamlit-markdown` + `sseclient-py` |
| Molecule render | `streamlit-ketcher` (SMILES round-trip) + RDKit `Draw` (inline SVG/PNG) |
| Fingerprint compute | RDKit (Morgan/ECFP4) + drfp (reaction) — `app/components/chem.py` |
| HTTP client | `httpx` (sync + streaming) |
| Auth | Streamlit `st.login()` OIDC (Microsoft Entra ID default); request-time identity translation to chemclaw2 in `app/components/api_client.py` |
| Service-to-service | `Bearer mock:<sub>` in dev; HMAC-SHA256 `svc.<sub>.<iat>.<sig>` in prod (chemclaw2 BACKLOG item for the verifier) |

## Anti-features

- No custom Streamlit React components.
- No Tiptap / Quill / BlockNote / Slate.
- No second LLM SDK in the GUI. Agent calls go through chemclaw2.
- No database client. State is held in Streamlit session_state and chemclaw2's Postgres.
- No bespoke chat framework. `st.chat_message` + `st.fragment` + a hand-rolled SSE iterator is the whole thing.
- **No FastAPI / no BFF.** A BFF added zero capability for a server-side Streamlit deployment and doubled JWKS verification. Streamlit talks to chemclaw2 directly.

## Deliberate v1 limitations

- **No `beforeunload` guard for unsaved wiki edits.** Pure-Streamlit can't hook the browser's `beforeunload` event without a custom JS component (forbidden by anti-features). The wiki edit form catches the "accidentally clicked Back" case via a dirty marker + confirmation, but tab close / browser back still discards unsaved changes. Acceptable trade-off; revisit only if users actually lose work.
- **No token-by-token streaming.** chemclaw2 doesn't pass `include_partial_messages=True` to its claude-agent-sdk options today, so each text block arrives complete. The GUI renders incrementally per block but not per token. Flagged as a chemclaw2 BACKLOG item.

## Backend contract pinning

chemclaw2's HTTP contract is consumed at:
- `app/components/api_client.py` — every helper. Auth header construction, body shapes (snake_case `session_id`, `content_text`), URL paths (`/api/chat`, `/api/wiki`, `/api/search`).
- `app/components/chat_view.py:dispatch_events` — chemclaw2's FLAT SSE envelope types (`text`, `tool_use`, `result`, `error`, `[DONE]`).
- `app/components/chem.py` — Morgan/DRFP fingerprint format that matches what chemclaw2's MCP servers produce (so bits compare against stored bits).

When chemclaw2's API changes, these three files are the surface that moves. Don't add backwards-compatibility shims — just update.

## Backend prerequisites (chemclaw2 BACKLOG items, recommended)

1. Service-token auth path in `chemclaw2/api/auth.py` accepting `Bearer svc.<sub>.<iat>.<sig>` with a maxAge window on `iat`.
2. `include_partial_messages=True` in `chemclaw2/api/agent/runner.py:ClaudeAgentOptions` (for token-by-token streaming UX).
3. `X-Accel-Buffering: no` on `/api/chat` SSE response.

See `README.md` for details.
