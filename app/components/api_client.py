"""Direct httpx calls to the chemclaw2 backend.

Auth: Streamlit's st.login already verified the user's IdP id_token, so we
trust st.user.sub. We send either:

  - `Bearer svc.<sub>.<iat>.<sig>` when CHEMCLAW2_SERVICE_SECRET is set
    (requires chemclaw2 to implement HMAC verifier — BACKLOG item).
  - `Bearer mock:<sub>` otherwise (chemclaw2 accepts in dev mode when
    CLERK_SECRET_KEY is unset/sk_test_REPLACE*; see chemclaw2/api/auth.py:53-58).

This replaces what the now-deleted FastAPI BFF used to do. The BFF added no
capability for a server-side Streamlit deployment — it just doubled JWKS
verification and proxied HTTP. Removed in favour of direct calls.
"""

import hashlib
import hmac
import re
import time
from collections.abc import Iterator
from typing import Any

import httpx
import streamlit as st

from app.config import CHEMCLAW2_API_URL, CHEMCLAW2_SERVICE_SECRET, REQUEST_TIMEOUT_S

# Allowlist for IdP subject claims. Entra (base64url-ish), Google (numeric),
# Auth0 (`provider|id`), and Okta (URL-safe ID) all fit. Excludes `.` and `:`
# which would break our token wire format `svc.<sub>.<iat>.<sig>` and our
# HMAC message `<sub>:<iat>`. Max length per OIDC spec is 255.
_SUB_RE = re.compile(r"^[A-Za-z0-9_\-|]{1,255}$")


def _user_sub() -> str:
    sub = getattr(st.user, "sub", None)
    if not sub:
        raise RuntimeError("st.user has no `sub` claim — is the user signed in?")
    sub_str = str(sub)
    if not _SUB_RE.match(sub_str):
        # Refuse to construct a token whose format depends on a sub we can't
        # safely embed. If a new IdP introduces other separators we'd see this
        # fail closed — preferable to silently signing an ambiguous message.
        raise RuntimeError("IdP sub contains characters incompatible with token format")
    return sub_str


def _auth_header() -> dict[str, str]:
    sub = _user_sub()
    if CHEMCLAW2_SERVICE_SECRET:
        # Production path. chemclaw2 BACKLOG item: verifier MUST enforce a
        # maxAge window on iat (recommended 300s) to bound replay.
        iat = int(time.time())
        msg = f"{sub}:{iat}".encode()
        sig = hmac.new(CHEMCLAW2_SERVICE_SECRET.encode(), msg, hashlib.sha256).hexdigest()
        return {"Authorization": f"Bearer svc.{sub}.{iat}.{sig}"}
    # Dev-mode default — chemclaw2 accepts when its CLERK_SECRET_KEY is
    # unset/sk_test_REPLACE*. Production must set CHEMCLAW2_SERVICE_SECRET.
    return {"Authorization": f"Bearer mock:{sub}"}


def _client() -> httpx.Client:
    # retries=2 covers connection-level failures (network blips during rolling
    # deploys, transient DNS) without affecting HTTP-status errors. Anything
    # that returns an HTTP response (including 5xx) does NOT retry — that's
    # surfaced to the caller as an HTTPError so the UI can show a real message.
    return httpx.Client(
        base_url=CHEMCLAW2_API_URL,
        timeout=REQUEST_TIMEOUT_S,
        headers=_auth_header(),
        transport=httpx.HTTPTransport(retries=2),
    )


def list_wiki_pages(
    cursor: str | None = None,
    project: str | None = None,
    include_archived: bool = False,
) -> dict[str, Any]:
    params: dict[str, Any] = {}
    if cursor:
        params["cursor"] = cursor
    if project:
        params["project"] = project
    if include_archived:
        params["include_archived"] = "true"
    with _client() as c:
        r = c.get("/api/wiki", params=params or None)
        r.raise_for_status()
        return r.json()


def list_projects() -> list[str]:
    """Wrapper that supplies the per-user cache key.

    Today chemclaw2 returns the same projects list for everyone, so a global
    cache would be technically safe — but the cache *must* key on user identity
    so that if chemclaw2 ever scopes projects per tenant or role, the GUI can't
    silently leak across users.
    """
    return _list_projects_cached(user_sub=_user_sub())


@st.cache_data(ttl=60, show_spinner=False)
def _list_projects_cached(user_sub: str) -> list[str]:
    """Per-user cache. `st.cache_data` includes args in the cache key UNLESS
    the name starts with `_` (which is Streamlit's "don't hash this" marker).
    Hence `user_sub` (no leading underscore) — each user gets their own slot.

    60s TTL covers fragment-rerun storms; busted on writes via
    `list_projects.clear()`.
    """
    del user_sub  # only used as the cache key; the request itself reads
    # `st.user` via `_auth_header()` inside `_client()`.
    with _client() as c:
        r = c.get("/api/wiki", params={"projects": "true"})
        r.raise_for_status()
        data = r.json()
    projects = data.get("projects") or []
    return [p for p in projects if isinstance(p, str)]


# Re-export `.clear()` so call sites that bust the cache after a write
# (upsert_wiki_page / patch_wiki_page) don't need to know about the
# inner cached function. `.clear()` with no args wipes ALL keys; that's
# fine on a write (rare event), no need for per-user precision.
list_projects.clear = _list_projects_cached.clear  # type: ignore[attr-defined]


def get_wiki_page(slug: str) -> dict[str, Any]:
    with _client() as c:
        r = c.get(f"/api/wiki/{slug}")
        r.raise_for_status()
        return r.json()


def upsert_wiki_page(slug: str, title: str, markdown: str) -> dict[str, Any]:
    """Create or update. POST is an upsert on chemclaw2."""
    body = {
        "slug": slug,
        "title": title,
        "content": {"version": "md1", "markdown": markdown},
        "content_text": markdown,
        # citations intentionally omitted — passing [] would wipe existing
        # rows; omission lets chemclaw2 reuse what's already stored.
    }
    with _client() as c:
        r = c.post("/api/wiki", json=body)
        r.raise_for_status()
        result: dict[str, Any] = r.json()
    # New page may have introduced a new project — bust the projects cache so
    # the wiki sidebar dropdown picks it up on next render.
    list_projects.clear()
    return result


def patch_wiki_page(
    slug: str,
    *,
    needs_review: bool | None = None,
    archived: bool | None = None,
    maturity: str | None = None,
    project: str | None = None,
) -> dict[str, Any]:
    """PATCH metadata fields. Only non-None values are sent."""
    body: dict[str, Any] = {}
    if needs_review is not None:
        body["needs_review"] = needs_review
    if archived is not None:
        body["archived"] = archived
    if maturity is not None:
        body["maturity"] = maturity
    if project is not None:
        body["project"] = project
    with _client() as c:
        r = c.patch(f"/api/wiki/{slug}", json=body)
        r.raise_for_status()
        result: dict[str, Any] = r.json()
    # Re-assigning project may add/remove a name from the global set.
    if project is not None:
        list_projects.clear()
    return result


def search_text(q: str, limit: int = 20) -> dict[str, Any]:
    with _client() as c:
        r = c.get("/api/search", params={"q": q, "limit": limit})
        r.raise_for_status()
        return r.json()


def search_compound(smiles: str, limit: int = 20, min_score: float = 0.4) -> dict[str, Any]:
    # Deferred import: keeps rdkit/drfp out of the import chain on platforms
    # where rdkit wheels aren't available (Intel Mac dev). Production Linux
    # containers have rdkit and this no-ops.
    from app.components.chem import morgan_bits

    bits = morgan_bits(smiles)
    with _client() as c:
        r = c.post(
            "/api/search",
            json={"fingerprint_bits": bits, "limit": limit, "min_score": min_score},
        )
        r.raise_for_status()
        return r.json()


def search_reaction(
    reaction_smiles: str, limit: int = 20, min_score: float = 0.4
) -> dict[str, Any]:
    from app.components.chem import drfp_bits  # deferred — see search_compound

    bits = drfp_bits(reaction_smiles)
    with _client() as c:
        r = c.post(
            "/api/search",
            json={"rxn_fingerprint_bits": bits, "limit": limit, "min_score": min_score},
        )
        r.raise_for_status()
        return r.json()


@st.cache_data(ttl=30, show_spinner=False)
def get_backend_health() -> dict[str, Any]:
    """Fetch chemclaw2's /api/health. Unauthenticated route on chemclaw2's side,
    but we still send our usual headers — chemclaw2 just ignores them.

    Returns the raw payload (`ok`, `db`, `fingerprint_backlog`, `worker_warn`)
    or a synthetic `{ok: False, error: ...}` if chemclaw2 is unreachable.
    Cached for 30s so each fragment rerun doesn't pile on requests.
    """
    try:
        with _client() as c:
            r = c.get("/api/health", timeout=5)
            r.raise_for_status()
            data: dict[str, Any] = r.json()
            return data
    except Exception as exc:  # noqa: BLE001 — any failure → degraded health
        return {"ok": False, "error": str(exc)}


def get_todos(session_id: str) -> dict[str, Any]:
    """Fetch agent todos for a session. Returns {todos: [...]}."""
    with _client() as c:
        r = c.get(f"/api/todos/{session_id}")
        r.raise_for_status()
        return r.json()


def list_campaigns(cursor: str | None = None) -> dict[str, Any]:
    """List the current user's synthesis campaigns. Returns {campaigns: [...], nextCursor}."""
    params: dict[str, Any] = {}
    if cursor:
        params["cursor"] = cursor
    with _client() as c:
        r = c.get("/api/campaigns", params=params or None)
        r.raise_for_status()
        return r.json()


def get_campaign(campaign_id: str) -> dict[str, Any]:
    """Fetch a single campaign with its steps."""
    with _client() as c:
        r = c.get(f"/api/campaigns/{campaign_id}")
        r.raise_for_status()
        return r.json()


def get_wiki_contradictions(slug: str, resolved: bool = False) -> dict[str, Any]:
    """Fetch contradictions for a wiki page. Returns {contradictions: [...]}."""
    with _client() as c:
        r = c.get(f"/api/wiki/{slug}/contradictions", params={"resolved": str(resolved).lower()})
        r.raise_for_status()
        return r.json()


def stream_chat(
    prompt: str,
    session_id: str | None = None,
    *,
    plan_mode: bool = False,
    override_justification: str | None = None,
) -> Iterator[bytes]:
    """Open an SSE stream directly from chemclaw2's /api/chat."""
    body: dict[str, Any] = {"prompt": prompt}
    if session_id:
        body["session_id"] = session_id
    if plan_mode:
        body["plan_mode"] = True
    if override_justification:
        body["override_justification"] = override_justification
    with httpx.stream(
        "POST",
        f"{CHEMCLAW2_API_URL}/api/chat",
        json=body,
        headers=_auth_header(),
        timeout=httpx.Timeout(None, connect=10),
    ) as r:
        r.raise_for_status()
        yield from r.iter_bytes()
