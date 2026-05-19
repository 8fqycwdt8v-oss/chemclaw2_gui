# chemclaw2_gui

Streamlit GUI for [chemclaw2](https://github.com/8fqycwdt8v-oss/chemclaw2).

```
chemclaw2/            ← backend (FastAPI Python, sibling repo)
chemclaw2_mockdata/   ← local Postgres + mock services (sibling repo)
chemclaw2_gui/        ← this repo
```

## Architecture

```
Browser ──HTTPS──▶ Streamlit (st.login OIDC; chemistry compute) ──HTTP──▶ chemclaw2 backend
```

Single container. Streamlit handles auth via `st.login()` (Microsoft Entra ID by default), computes RDKit/DRFP fingerprints in-process, and calls chemclaw2 directly over HTTP — no BFF in between.

## Quick start (local dev)

### 1 — Prerequisites
- Python 3.12+
- [uv](https://docs.astral.sh/uv/) (`brew install uv` or `pipx install uv`)
- Docker + Docker Compose (for one-command spin-up)
- `chemclaw2` and `chemclaw2_mockdata` running locally (see those repos)
- A Microsoft Entra ID app registration (or Auth0 tenant) — see "Auth setup"

### 2 — Install
```bash
uv sync
cp .env.example .env
cp .streamlit/secrets.toml.example .streamlit/secrets.toml
# Edit both — fill in Entra IDs, generate cookie_secret, set CHEMCLAW2_API_URL
```

> **Intel Mac caveat:** RDKit dropped Intel-Mac wheels after `2024.3.5`. If you're on an Intel Mac (`platform_machine == 'x86_64'`), `uv sync` will fail on `rdkit`. Workaround: skip rdkit locally (`uv sync --no-install-package rdkit`) and use Docker Compose for any path that touches `app/components/chem.py` or `app/pages/wiki.py`. Production deploys (Linux x86_64) and Apple-Silicon Macs are unaffected.

### 3 — Run with Docker Compose
```bash
docker compose up --build
```
Streamlit serves at http://localhost:8501.

Or run without Docker:
```bash
uv run streamlit run app/main.py
```

### 4 — Verify
Open Streamlit, sign in via Entra, land on the chat page.

## Auth setup (Microsoft Entra ID)

1. In the [Entra admin center](https://entra.microsoft.com), **App registrations → New registration**.
2. Redirect URI: `http://localhost:8501/oauth2callback` (Web platform).
3. Copy the **Application (client) ID** and **Directory (tenant) ID** into `.streamlit/secrets.toml`.
4. **Certificates & secrets → New client secret**, copy the value into the same file.
5. Generate a cookie secret: `python -c "import secrets; print(secrets.token_urlsafe(32))"`.

For Auth0 instead, uncomment the `[auth.auth0]` block in `secrets.toml.example` and set `STREAMLIT_LOGIN_PROVIDER=auth0` in `.env`.

## Auth bridge to chemclaw2

chemclaw2's `api/auth.py` verifies Clerk JWTs. This GUI authenticates via Entra (or Auth0). The two IdPs don't trust each other's tokens, so Streamlit translates the identity at request time:

- **Dev (default):** Streamlit sends `Authorization: Bearer mock:<entra-sub>`. chemclaw2 accepts this when its `CLERK_SECRET_KEY` is unset or starts with `sk_test_REPLACE` (its built-in mock mode — see `chemclaw2/api/auth.py`).
- **Production:** set `CHEMCLAW2_SERVICE_SECRET` in `.env` (must match the secret on chemclaw2). Streamlit sends `Bearer svc.<sub>.<iat>.<sig>` where `sig = hmac_sha256(f"{sub}:{iat}", CHEMCLAW2_SERVICE_SECRET).hexdigest()`. chemclaw2's verifier (shipped in [chemclaw2 PR #87](https://github.com/8fqycwdt8v-oss/chemclaw2/pull/87) — `_verify_svc_token` in `api/auth.py`) enforces a 300s `iat` maxAge window and uses `hmac.compare_digest` for timing-safe signature verification.

**Contract is locked by [`tests/test_api_client.py`](tests/test_api_client.py) (sub regex + HMAC construction) on this side, and `tests/test_auth_svc_token.py` on the chemclaw2 side. Any drift fails CI on both repos.**

Streamlit's `st.login()` already verifies the user's IdP id_token against the IdP JWKS, so re-verifying server-side adds no security and is omitted.

## BACKLOG items in chemclaw2 (recommended, not strictly blocking)

| # | Change in `chemclaw2` | Without it |
|---|---|---|
| 1 | chemclaw2's `claude-agent-sdk` query options pass `include_partial_messages=True`. | Chat bubbles appear at end of turn, not token-by-token. GUI handles both cases. |
| 2 | Add `[wiki:slug]` system-prompt hint so the agent emits clickable wiki references. | The GUI's `extract_wiki_refs` (text_utils.py) parses these into a "📚 Referenced wiki pages" expander; fires only when the agent happens to use the syntax. |
| 3 | Emit `{type:"view", view_id, payload?}` SSE envelopes for agent-driven view triggers. GUI dispatch is wired (`chat_view.dispatch_events`) and renders "Open in &lt;View&gt;" buttons — no-op until chemclaw2 emits. |

The service-token verifier (originally BACKLOG #1) shipped in chemclaw2 PR #87 — production auth is now real, set `CHEMCLAW2_SERVICE_SECRET` to use it.

## Wiki content model

The GUI uses **markdown source** as the wiki source of truth. Pages saved by the GUI store:
- `content_text = <raw markdown>` (used by chemclaw2 for FTS)
- `content = {"version": "md1", "markdown": "<raw markdown>"}` (forward-compatible envelope)

Embed chemistry inline:
- `[mol:SMILES]` on its own line → rendered as a `streamlit-ketcher` block
- `[rxn:SMILES1>>SMILES2]` on its own line → rendered as RDKit reaction PNG

Citations: the GUI renders the page's `citations` array as a `## References` footer. The GUI **omits** the `citations` field when saving so chemclaw2 preserves what's already stored (passing `[]` would wipe them — see `chemclaw2/api/db/queries/wiki.py:upsert_wiki_page` semantics).

## Repo layout

```
app/             Streamlit GUI (main + 3 pages + 4 components)
tests/           pytest unit tests (SSE dispatch + wiki render)
.streamlit/      Streamlit config + secrets template
```

## Deployment (Fly.io)

`fly.toml` ships a production config: single Streamlit machine in `fra`, one warm instance (Streamlit cold-start is multi-second), healthcheck on `/_stcore/health`, autoscale up on demand.

```bash
# First-time setup
fly launch --no-deploy --copy-config           # uses the committed fly.toml
fly secrets set \
  CHEMCLAW2_API_URL="https://chemclaw2.fly.dev" \
  CHEMCLAW2_SERVICE_SECRET="$(openssl rand -hex 32)" \
  STREAMLIT_LOGIN_PROVIDER="microsoft"

# Mount the Streamlit secrets file (cookie_secret + OIDC client_id/secret)
fly secrets set --stage STREAMLIT_SECRETS_TOML="$(cat .streamlit/secrets.toml)"
# … then add a startup wrapper that writes /app/.streamlit/secrets.toml from
# the env var on boot (one-shot; see "Secret rotation" below).

fly deploy
```

**Cross-repo invariant**: `CHEMCLAW2_SERVICE_SECRET` MUST be identical on the chemclaw2 Fly app and this one. Setting one without the other instantly breaks auth.

```bash
# Read the secret-fingerprint to compare without exposing the value
fly ssh console -a chemclaw2     -C 'sha256sum /app/.env 2>/dev/null'
fly ssh console -a chemclaw2-gui -C 'env | grep CHEMCLAW2_SERVICE_SECRET | sha256sum'
```

### Secret rotation runbook

| Secret | Rotation steps | Blast radius |
|---|---|---|
| `CHEMCLAW2_SERVICE_SECRET` | Generate new value → `fly secrets set` on **both** apps (chemclaw2 + chemclaw2_gui) in quick succession → confirm both rolled to the new image (`fly status`) → existing in-flight requests fail with 401 for ~30s; users retry transparently. | Brief 401 window during rollout. Coordinate the two `secrets set` calls — both must propagate before users hit the next request. |
| Streamlit `cookie_secret` | Generate `python -c "import secrets; print(secrets.token_urlsafe(32))"` → update `secrets.toml` → `fly secrets set STREAMLIT_SECRETS_TOML=…` → deploy → **all signed-in users are logged out** (cookies signed with old secret no longer verify). | All sessions invalidated. Plan around a low-traffic window. |
| Entra/Auth0 `client_secret` | Rotate in the IdP first (Certificates & secrets → New client secret), update `secrets.toml`, redeploy. Old secret stays valid in Entra until you delete it — overlap window lets you roll forward then deactivate. | Zero downtime if you overlap secrets in the IdP. |
| Clerk JWT verification on chemclaw2 | Not our concern; chemclaw2 owns its Clerk integration. | n/a |

## CI

`.github/workflows/ci.yml` runs on every push and PR: ruff lint + format-check + pytest (57 tests at last count) + a fingerprint-invariant assertion that catches RDKit/drfp upgrades silently changing bit lengths.

## Conventions

- Format / lint: `uv run ruff check && uv run ruff format`
- Tests: `uv run pytest`
