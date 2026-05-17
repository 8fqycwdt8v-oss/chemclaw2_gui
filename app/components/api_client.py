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
import time
from collections.abc import Iterator
from typing import Any

import httpx
import streamlit as st

from app.config import CHEMCLAW2_API_URL, CHEMCLAW2_SERVICE_SECRET, REQUEST_TIMEOUT_S


def _user_sub() -> str:
    sub = getattr(st.user, "sub", None)
    if not sub:
        raise RuntimeError("st.user has no `sub` claim — is the user signed in?")
    return str(sub)


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
    return httpx.Client(
        base_url=CHEMCLAW2_API_URL, timeout=REQUEST_TIMEOUT_S, headers=_auth_header()
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
    """Fetch the distinct project names known to chemclaw2."""
    with _client() as c:
        r = c.get("/api/wiki", params={"projects": "true"})
        r.raise_for_status()
        data = r.json()
    projects = data.get("projects") or []
    return [p for p in projects if isinstance(p, str)]


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
        return r.json()


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
        return r.json()


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
