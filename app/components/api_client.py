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
    # st.user.id_token is exposed only when secrets.toml sets expose_tokens = ["id"].
    token = getattr(st.user, "id_token", None)
    if not token:
        raise RuntimeError("No id_token on st.user; check expose_tokens in secrets.toml.")
    return {"Authorization": f"Bearer {token}"}


def _client() -> httpx.Client:
    return httpx.Client(base_url=BFF_URL, timeout=REQUEST_TIMEOUT_S, headers=_headers())


def list_wiki_pages(cursor: str | None = None) -> dict[str, Any]:
    with _client() as c:
        r = c.get("/wiki", params={"cursor": cursor} if cursor else None)
        r.raise_for_status()
        return r.json()


def get_wiki_page(slug: str) -> dict[str, Any]:
    with _client() as c:
        r = c.get(f"/wiki/{slug}")
        r.raise_for_status()
        return r.json()


def upsert_wiki_page(slug: str, title: str, markdown: str) -> dict[str, Any]:
    """Create or update. Always omits citations to preserve existing ones."""
    body = {
        "slug": slug,
        "title": title,
        "content": {"version": "md1", "markdown": markdown},
        "contentText": markdown,
    }
    with _client() as c:
        r = c.put(f"/wiki/{slug}", json=body) if _exists(c, slug) else c.post("/wiki", json=body)
        r.raise_for_status()
        return r.json()


def _exists(client: httpx.Client, slug: str) -> bool:
    r = client.get(f"/wiki/{slug}")
    return r.status_code == 200


def search_text(q: str, limit: int = 20) -> dict[str, Any]:
    with _client() as c:
        r = c.get("/search", params={"q": q, "limit": limit})
        r.raise_for_status()
        return r.json()


def search_compound(smiles: str, limit: int = 20) -> dict[str, Any]:
    with _client() as c:
        r = c.post("/search/compound", json={"smiles": smiles, "limit": limit})
        r.raise_for_status()
        return r.json()


def search_reaction(reaction_smiles: str, limit: int = 20) -> dict[str, Any]:
    with _client() as c:
        r = c.post("/search/reaction", json={"reaction_smiles": reaction_smiles, "limit": limit})
        r.raise_for_status()
        return r.json()


def stream_chat(prompt: str, session_id: str | None = None) -> Iterator[bytes]:
    """Open an SSE stream from the BFF /chat endpoint. Yields raw bytes."""
    body: dict[str, Any] = {"prompt": prompt}
    if session_id:
        body["sessionId"] = session_id
    with httpx.stream(
        "POST",
        f"{BFF_URL}/chat",
        json=body,
        headers=_headers(),
        timeout=httpx.Timeout(None, connect=10),
    ) as r:
        r.raise_for_status()
        yield from r.iter_bytes()
