# chemclaw2_gui

Streamlit GUI + FastAPI BFF for chemclaw2.

## Hard rules

1. **Backend lives in chemclaw2.** Do not duplicate Claude Agent SDK orchestration, DB queries, or MCP server logic here. The BFF is a thin proxy + auth bridge + fingerprint computer.
2. **Markdown-source wiki, not Tiptap.** The trade-off was chosen deliberately. Do not reintroduce Tiptap/React rich-text components.
3. **No JS toolchain.** Pure Python. The only React assets in the build come bundled inside `streamlit-ketcher` and `streamlit-markdown`.
4. **Off-the-shelf over self-built.** If a Streamlit component or PyPI package covers a need, use it. If it doesn't, defer rather than build a custom React component.
5. **Minimum code.** Target the whole repo well under 1,500 LOC. The project-wide ceiling across chemclaw2 + chemclaw2_gui is 6,000 LOC at v1.

## Stack

| Layer | Tech |
|---|---|
| GUI | Streamlit (+ st.fragment for partial reruns) |
| Streaming chat | `streamlit-markdown` + `sseclient-py` |
| Molecule render | `streamlit-ketcher` (SMILES round-trip) + RDKit `Draw` (inline SVG/PNG) |
| BFF | FastAPI + uvicorn |
| HTTP client | `httpx` (sync + streaming) |
| Auth | Streamlit `st.login()` OIDC (Microsoft Entra ID default) → FastAPI verifies JWT via JWKS (`python-jose`) |
| Service-to-service | HMAC-SHA256 shared secret with chemclaw2 backend (pending BACKLOG item) |

## Anti-features

- No custom Streamlit React components.
- No Tiptap / Quill / BlockNote / Slate.
- No second LLM SDK in the GUI. Agent calls go through chemclaw2.
- No database client. State is held in Streamlit session_state and chemclaw2's Postgres.
- No bespoke chat framework. `st.chat_message` + `st.fragment` + a hand-rolled SSE iterator is the whole thing.

## Backend prerequisites (chemclaw2 BACKLOG items, blocking)

1. Service-token auth path in `chemclaw2/apps/web/middleware.ts` accepting HMAC bearer.
2. `includePartialMessages: true` in `chemclaw2/apps/web/lib/agent.ts:buildQueryOptions` (for token-by-token streaming UX).
3. `X-Accel-Buffering: no` on `/api/chat` SSE response.

See `README.md` "Backend prerequisites" for details.
