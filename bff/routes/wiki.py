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


class WikiPatch(BaseModel):
    needs_review: bool | None = None
    archived: bool | None = None
    maturity: str | None = None
    project: str | None = None


@router.get("/wiki")
async def list_pages(
    cursor: str | None = Query(default=None),
    project: str | None = Query(default=None),
    include_archived: bool = Query(default=False),
    projects: bool = Query(default=False),
    user: dict[str, str] = Depends(require_user),
) -> Any:
    # chemclaw2's response shape varies by mode:
    #   projects=true  → {"projects": [...]}
    #   q=...          → plain list (not exposed here)
    #   default        → {"pages": [...], "nextCursor": ...}
    # Pass params through unchanged; don't try to normalise.
    params: dict[str, Any] = {}
    if projects:
        params["projects"] = "true"
    else:
        if cursor:
            params["cursor"] = cursor
        if project:
            params["project"] = project
        if include_archived:
            params["include_archived"] = "true"
    async with client(user["sub"], user["token"]) as c:
        r = await c.get("/api/wiki", params=params or None)
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


@router.patch("/wiki/{slug}")
async def patch_page_metadata(
    slug: str,
    body: WikiPatch,
    user: dict[str, str] = Depends(require_user),
) -> dict[str, Any]:
    """Metadata-only update. exclude_none so chemclaw2's no-op detection works."""
    async with client(user["sub"], user["token"]) as c:
        r = await c.patch(f"/api/wiki/{slug}", json=body.model_dump(exclude_none=True))
        if r.status_code == 404:
            raise HTTPException(404, "Not found")
        r.raise_for_status()
        return r.json()
