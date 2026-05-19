# chemclaw2_gui

Single-container Streamlit GUI for chemclaw2. No backend, no BFF — Streamlit
calls chemclaw2's FastAPI directly.

```
app/main.py              entry: st.login gate, navigation, sidebar (health + dock)
app/pages/               chat, wiki, search Streamlit pages
app/components/          api_client (HTTP + auth), chat_view, wiki_render, chem, text_utils, views_dock
app/views/               specialised views auto-discovered by the dock — drop a file in to register
tests/                   pytest unit tests (pure-function level)
.streamlit/              config + secrets.toml.example
```

**Deferred work lives in [`BACKLOG.md`](./BACKLOG.md)** — append-only log, one bullet per item, area-prefixed. Resolve by deleting the line in the same commit. Read it before adding new TODO comments to code.

## Hard rules

1. **Backend lives in chemclaw2.** Do not duplicate Claude Agent SDK orchestration, DB queries, or MCP server logic here. The GUI calls chemclaw2 over HTTP; chemistry compute (RDKit/DRFP fingerprints) happens in `app/components/chem.py` only because chemclaw2's `/api/search` accepts pre-computed bits.
2. **Markdown-source wiki, not Tiptap.** The trade-off was chosen deliberately. Do not reintroduce Tiptap/React rich-text components.
3. **No JS toolchain.** Pure Python. The only React assets in the build come bundled inside `streamlit-ketcher` and `streamlit-markdown`.
4. **Off-the-shelf over self-built.** If a Streamlit component or PyPI package covers a need, use it. If it doesn't, defer rather than build a custom React component.
5. **Minimum code.** Repo target is under 2,000 application LOC. Project-wide ceiling across chemclaw2 + chemclaw2_gui is 6,000 LOC at v1.
6. **After any review (code review, security audit, parity audit), abstract general rules from the findings into this file.** If a bug or smell got past prior review, it's because no rule excluded it. Add the rule under `## Gotchas` (or invent a new section) so a future Claude session — or a future human — would not repeat the mistake. Examples already captured this way: the `@st.cache_data` underscore-arg exclusion (caught us in the security audit), the chemclaw2 contract-pinning surface (caught us during contract drift), the slug-regex sync. **The pattern is: review finding → permanent CLAUDE.md rule, not just a one-off fix.**

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

## Commands

```bash
# First-time setup. Intel Mac: append --no-install-package rdkit
# (rdkit dropped Intel wheels after 2024.3.5).
uv sync

# Tests — --no-sync skips rdkit reinstall attempts on every invocation.
uv run --no-sync pytest -q

# Lint + format
uv run --no-sync ruff check .
uv run --no-sync ruff format

# Streamlit dev (needs .streamlit/secrets.toml + .env populated).
uv run --no-sync streamlit run app/main.py

# Docker — production-realistic; uses Linux rdkit wheels.
docker compose up --build
```

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

## Gotchas

- **`@st.cache_data` excludes `_`-prefixed parameters from the cache key.** A function decorated `@st.cache_data` cached by `def f(_user_sub: str)` is *globally cached* regardless of the arg's value — Streamlit treats `_`-prefix as "don't hash this." Use `user_sub` (no underscore) when you want per-user caching. See `app/components/api_client.py:_list_projects_cached`.
- **Intel Mac dev: no RDKit wheel after 2024.3.5.** `uv sync --no-install-package rdkit` succeeds and the test suite still passes (chem helpers are deferred-imported in `api_client.py`). For full validation use Docker Compose.
- **Sibling repos.** Backend lives at `/Users/robertmoeckel/Documents/VSCode/chemclaw2` (FastAPI Python). Local-dev DB + mock services at `/Users/robertmoeckel/Documents/VSCode/chemclaw2_mockdata`. Both must be running for end-to-end testing.
- **chemclaw2 dev-mode auth.** When chemclaw2's `CLERK_SECRET_KEY` is unset or starts with `sk_test_REPLACE`, it accepts `Bearer mock:<userId>` — the GUI's default. Production must set both `CLERK_SECRET_KEY` on chemclaw2 *and* `CHEMCLAW2_SERVICE_SECRET` on this side, plus implement the HMAC verifier (chemclaw2 BACKLOG #1).
- **Slug regex must match chemclaw2's.** chemclaw2's `_SLUG_RE` (in `api/routes/wiki.py`) is `^[a-z0-9][a-z0-9-]*[a-z0-9]$`. Our `_WIKI_REF_RE` (text_utils.py) and `SLUG_RE` (pages/wiki.py) must stay aligned or refs won't resolve. Locked by `tests/test_text_utils.py::test_wiki_ref_regex_matches_chemclaw2_slug_re_pattern`.
- **View `matches()` must be exception-safe.** Locked by `tests/test_views_registry.py::test_matches_is_a_pure_function_of_state_dict` which runs `matches({})` for every registered view. If your `matches()` reads from anything that can fail when uninitialised (e.g., `st.user.sub` before sign-in, a cached API call that authenticates), wrap it. See `app/views/notifications.py:_safe_unread_count` for the pattern.
- **Admin / privileged views set `matches()` to return False unconditionally** — quick-open only. Auto-pinning an admin view for a non-admin user means every regular user sees a card they can't use (and clicking it shows a 403 message). Examples: `app/views/audit.py`, `app/views/tool_permissions.py`, `app/views/budgets.py`. Use the quick-open command palette to surface them by name.
- **Admin/privileged views must handle `httpx.HTTPStatusError(403)` gracefully.** chemclaw2's admin routes use `get_admin_user` and return 403 to non-admins. Render a clear "Admin access required" message — don't surface the raw exception. Pattern: `except httpx.HTTPStatusError as exc: if exc.response.status_code == 403: st.error("Admin access required.")`. Locked by `tests/test_admin_views_403.py` — parametrised over `audit`, `budgets`, `tool_permissions`. Add new admin views to the `ADMIN_VIEWS` list there.
- **Cross-page navigation: use `app/components/nav.py:navigate_to_wiki`.** Three call sites previously each set `wiki_slug` / `wiki_mode` / `active_view_id` then `st.switch_page("pages/wiki.py")`. Reach for the helper instead — if the contract (page path or state keys) changes, there's one place to update.

## Backend prerequisites (chemclaw2 BACKLOG items)

The service-token verifier shipped in chemclaw2 PR #87 — production auth is real;
set `CHEMCLAW2_SERVICE_SECRET` to use it. Cross-repo contract is locked by
`tests/test_api_client.py:test_hmac_token_matches_chemclaw2_verifier_contract`.

Still pending in chemclaw2 (GUI side is ready):
1. `include_partial_messages=True` in `chemclaw2/api/agent/runner.py:ClaudeAgentOptions` (token-by-token streaming).
2. Append to `BASE_SYSTEM_PROMPT` in `chemclaw2/api/agent/runner.py`: *"When you cite an org wiki page, embed `[wiki:slug]` (lowercase-with-hyphens) so the UI can offer a direct navigation link."* The GUI parses these into the "📚 Referenced wiki pages" expander.
3. Emit `{type:"view", view_id, payload?}` SSE envelopes for agent-driven view triggers. GUI dispatch is wired in `chat_view.dispatch_events`; renders "Open in &lt;View&gt;" buttons. No-op until chemclaw2 emits.

See `README.md` for details.
