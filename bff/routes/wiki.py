"""Wiki proxy.

chemclaw2's `POST /api/wiki` is an upsert (`upsert_wiki_page`), so both create
and update flow through POST. `PATCH /api/wiki/{slug}` is metadata-only
(needs_review, archived, maturity, project) — NOT content. The GUI only needs
the POST path for v1.

Field naming: chemclaw2 uses snake_case (`content_text`, not `contentText`).

`citations` is intentionally absent from `WikiUpsert` — Pydantic drops the
field, so the chemclaw2 backend uses its own existing-citations path
(`citations or []` defaults to existing rows when the field is omitted).
"""

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from bff.auth import require_user
from bff.chemclaw_client import client

router = APIRouter()


class WikiUpsert(BaseModel):
    slug: str
    title: str
    content: dict[str, Any]
    content_text: str
    # citations intentionally not exposed; see module docstring.


@router.get("/wiki")
async def list_pages(
    cursor: str | None = Query(default=None),
    user: dict[str, str] = Depends(require_user),
) -> dict[str, Any]:
    async with client(user["sub"], user["token"]) as c:
        r = await c.get("/api/wiki", params={"cursor": cursor} if cursor else None)
        r.raise_for_status()
        return r.json()


@router.get("/wiki/{slug}")
async def get_page(slug: str, user: dict[str, str] = Depends(require_user)) -> dict[str, Any]:
    async with client(user["sub"], user["token"]) as c:
        r = await c.get(f"/api/wiki/{slug}")
        if r.status_code == 404:
            raise HTTPException(404, "Not found")
        r.raise_for_status()
        return r.json()


@router.post("/wiki")
async def upsert_page(
    body: WikiUpsert, user: dict[str, str] = Depends(require_user)
) -> dict[str, Any]:
    """Create-or-update. chemclaw2's POST /api/wiki is an upsert by slug."""
    async with client(user["sub"], user["token"]) as c:
        r = await c.post("/api/wiki", json=body.model_dump())
        r.raise_for_status()
        return r.json()
