"""Wiki proxy. Critical: NEVER forward the `citations` field on POST/PUT.

The chemclaw2 backend (`chemclaw2/apps/web/app/api/wiki/[slug]/route.ts:91-93`)
reuses existing citations only when the caller omits the field. Passing `[]`
wipes them. Strip the field on the way in regardless of what the GUI sends.
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
    contentText: str
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
async def create_page(
    body: WikiUpsert, user: dict[str, str] = Depends(require_user)
) -> dict[str, Any]:
    async with client(user["sub"], user["token"]) as c:
        r = await c.post("/api/wiki", json=body.model_dump())
        r.raise_for_status()
        return r.json()


@router.put("/wiki/{slug}")
async def update_page(
    slug: str, body: WikiUpsert, user: dict[str, str] = Depends(require_user)
) -> dict[str, Any]:
    async with client(user["sub"], user["token"]) as c:
        r = await c.put(f"/api/wiki/{slug}", json=body.model_dump())
        r.raise_for_status()
        return r.json()
