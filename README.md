# chemclaw2_gui

Streamlit GUI + FastAPI BFF for [chemclaw2](https://github.com/8fqycwdt8v-oss/chemclaw2).

```
chemclaw2/            ← backend (TypeScript Next.js, sibling repo)
chemclaw2_mockdata/   ← local Postgres + mock services (sibling repo)
chemclaw2_gui/        ← this repo: Streamlit + FastAPI BFF
```

## Architecture

```
Browser ──HTTPS──▶ Streamlit (st.login OIDC) ──HTTP──▶ FastAPI BFF ──HTTP──▶ chemclaw2 backend
                                                          │
                                                          ▼
                                       JWT verify via Microsoft Entra ID JWKS
                                       RDKit fingerprint compute (compound/reaction)
                                       SSE pass-through for /chat
```

The GUI never talks to chemclaw2 directly; the BFF is the only thing that crosses that boundary. This is what lets the BFF grow into the real backend later without changing the GUI.

## Quick start (local dev)

### 1 — Prerequisites
- Python 3.12+
- [uv](https://docs.astral.sh/uv/) (`brew install uv` or `pipx install uv`)
- Docker + Docker Compose (for one-command spin-up)
- `chemclaw2` and `chemclaw2_mockdata` running locally (see those repos)
- A Microsoft Entra ID app registration (or Auth0 tenant) — see "Auth setup" below

### 2 — Install
```bash
uv sync
cp .env.example .env
cp .streamlit/secrets.toml.example .streamlit/secrets.toml
# Edit both — fill in Entra IDs, generate cookie_secret, set CHEMCLAW2_API_URL
```

> **Intel Mac caveat:** RDKit dropped Intel-Mac wheels after `2024.3.5`. If you're on an Intel Mac (`platform_machine == 'x86_64'`), `uv sync` will fail on the `rdkit` install. Workaround: skip rdkit locally (`uv sync --no-install-package rdkit`) and use Docker Compose for any test path that touches `bff/routes/search.py` or `app/pages/wiki.py`. Production deploys (Linux x86_64) and Apple-Silicon Macs are unaffected.

### 3 — Run with Docker Compose
```bash
docker compose up --build
```
- Streamlit: http://localhost:8501
- BFF: http://localhost:8000 (health: `/health`)

Or run each separately without Docker:
```bash
uv run uvicorn bff.main:app --reload --port 8000          # terminal 1
uv run streamlit run app/main.py                          # terminal 2
```

### 4 — Verify
```bash
curl http://localhost:8000/health        # → {"ok": true}
```
Open Streamlit, sign in via Entra, land on the chat page.

## Auth setup (Microsoft Entra ID)

1. In the [Entra admin center](https://entra.microsoft.com), **App registrations → New registration**.
2. Redirect URI: `http://localhost:8501/oauth2callback` (Web platform).
3. Copy the **Application (client) ID** and **Directory (tenant) ID** into `.streamlit/secrets.toml`.
4. **Certificates & secrets → New client secret**, copy the value into the same file.
5. Generate a cookie secret: `python -c "import secrets; print(secrets.token_urlsafe(32))"`.

For Auth0 instead, uncomment the `[auth.auth0]` block in `secrets.toml.example` and adjust `app/main.py:LOGIN_PROVIDER`.

## Auth bridge to chemclaw2

chemclaw2 (post-Python-migration, `api/auth.py`) uses Clerk JWT verification. This GUI authenticates the user via Microsoft Entra (or Auth0) through `st.login()`. The two IdPs don't trust each other's tokens. The BFF (`bff/chemclaw_client.py`) bridges them:

- **Dev (default):** sends `Authorization: Bearer mock:<entra-sub>` to chemclaw2. Works when chemclaw2's `CLERK_SECRET_KEY` is unset or starts with `sk_test_REPLACE` (its built-in mock mode).
- **Production:** set `CHEMCLAW2_SERVICE_SECRET` in `.env` AND implement the HMAC verifier in chemclaw2's `api/auth.py` (see "BACKLOG items in chemclaw2" below).

## BACKLOG items in chemclaw2 (recommended, not strictly blocking)

| # | Change in `chemclaw2` | Without it |
|---|---|---|
| 1 | Service-token auth path in `api/auth.py` accepting `Authorization: Bearer svc.<sub>.<iat>.<sig>` where `sig = hmac_sha256(f"{sub}:{iat}", CHEMCLAW2_SERVICE_SECRET).hexdigest()`. **Must enforce a maxAge window on `iat`** (recommended: 300s) to bound replay. | Production deploy must rely on chemclaw2's dev mock-token mode (`mock:<userId>`), which is not a production auth path. |
| 2 | chemclaw2's `claude-agent-sdk` query options pass `include_partial_messages=True` (the Python SDK equivalent of the old TS `includePartialMessages`). | Chat bubbles appear at end of turn, not token-by-token. GUI handles both cases. |
| 3 | `X-Accel-Buffering: no` on `/api/chat` SSE — already present in chemclaw2 commit; verify. | SSE may buffer behind some proxies. |

## Wiki content model

The GUI uses **markdown source** as the wiki source of truth. Pages saved by the GUI store:
- `contentText = <raw markdown>` (used by chemclaw2 for FTS)
- `content = {"version": "md1", "markdown": "<raw markdown>"}` (forward-compatible envelope)

Embed chemistry inline:
- `[mol:SMILES]` on its own line → rendered as a `streamlit-ketcher` block
- `[rxn:SMILES1>>SMILES2]` on its own line → rendered as RDKit reaction PNG

Citations: standard markdown footnotes (`[^cite-id]`) + a `## References` section. The GUI **omits** the `citations` field on save to preserve any backend-stored citations (passing `[]` would wipe them — see `chemclaw2/apps/web/app/api/wiki/[slug]/route.ts:91-93`).

## Repo layout

```
app/             Streamlit GUI
bff/             FastAPI backend-for-frontend
tests/           pytest unit tests
.streamlit/      Streamlit config + secrets template
```

## Deployment

The two containers are deployed as separate Azure Container Apps (or equivalent). Configure ingress so only Streamlit is publicly reachable; BFF only reachable from the Streamlit container or via private networking. Set env vars per `.env.example` as container app secrets.

## Conventions

- Format / lint: `uv run ruff check && uv run ruff format`
- Type check: `uv run mypy app bff`
- Tests: `uv run pytest`
