"""Thin httpx wrappers around the FastAPI BFF.

The BFF in turn proxies to the chemclaw2 backend. Auth is the user's id_token
from `st.user`, attached as Bearer on every call.
"""

from collections.abc import Iterator
from typing import Any

import httpx
import streamlit as st

from app.config import BFF_URL, REQUEST_TIMEOUT_S


def _headers() -> dict[str, str]:
    # The id_token is exposed via st.user.tokens when secrets.toml's [auth] block
    # sets expose_tokens = "id" (or includes "id" in a list).
    tokens = getattr(st.user, "tokens", None)
    token = tokens["id"] if tokens and "id" in tokens else None
    if not token:
        raise RuntimeError(
            "No id_token on st.user.tokens — check `expose_tokens` in [auth] of secrets.toml."
        )
    return {"Authorization": f"Bearer {token}"}


def _client() -> httpx.Client:
    return httpx.Client(base_url=BFF_URL, timeout=REQUEST_TIMEOUT_S, headers=_headers())


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
        params["include_archived"] = True
    with _client() as c:
        r = c.get("/wiki", params=params or None)
        r.raise_for_status()
        return r.json()


def list_projects() -> list[str]:
    """Fetch the distinct project names known to chemclaw2."""
    with _client() as c:
        r = c.get("/wiki", params={"projects": True})
        r.raise_for_status()
        data = r.json()
    projects = data.get("projects") or []
    return [p for p in projects if isinstance(p, str)]


def get_wiki_page(slug: str) -> dict[str, Any]:
    with _client() as c:
        r = c.get(f"/wiki/{slug}")
        r.raise_for_status()
        return r.json()


def upsert_wiki_page(slug: str, title: str, markdown: str) -> dict[str, Any]:
    """Create or update. POST is an upsert; PATCH is metadata-only on chemclaw2."""
    body = {
        "slug": slug,
        "title": title,
        "content": {"version": "md1", "markdown": markdown},
        "content_text": markdown,
    }
    with _client() as c:
        r = c.post("/wiki", json=body)
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
        r = c.patch(f"/wiki/{slug}", json=body)
        r.raise_for_status()
        return r.json()


def search_text(q: str, limit: int = 20) -> dict[str, Any]:
    with _client() as c:
        r = c.get("/search", params={"q": q, "limit": limit})
        r.raise_for_status()
        return r.json()


def search_compound(smiles: str, limit: int = 20, min_score: float = 0.4) -> dict[str, Any]:
    with _client() as c:
        r = c.post(
            "/search/compound",
            json={"smiles": smiles, "limit": limit, "min_score": min_score},
        )
        r.raise_for_status()
        return r.json()


def search_reaction(
    reaction_smiles: str, limit: int = 20, min_score: float = 0.4
) -> dict[str, Any]:
    with _client() as c:
        r = c.post(
            "/search/reaction",
            json={"reaction_smiles": reaction_smiles, "limit": limit, "min_score": min_score},
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
    """Open an SSE stream from the BFF /chat endpoint. Yields raw bytes."""
    body: dict[str, Any] = {"prompt": prompt}
    if session_id:
        body["session_id"] = session_id
    if plan_mode:
        body["plan_mode"] = True
    if override_justification:
        body["override_justification"] = override_justification
    with httpx.stream(
        "POST",
        f"{BFF_URL}/chat",
        json=body,
        headers=_headers(),
        timeout=httpx.Timeout(None, connect=10),
    ) as r:
        r.raise_for_status()
        yield from r.iter_bytes()
