from typing import Any

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from bff.auth import require_user
from bff.chemclaw_client import client

router = APIRouter()


class ChatRequest(BaseModel):
    prompt: str
    sessionId: str | None = None


@router.post("/chat")
async def chat(
    body: ChatRequest,
    user: dict[str, str] = Depends(require_user),
) -> StreamingResponse:
    """SSE pass-through: stream chemclaw2's /api/chat events straight back to Streamlit.

    We never parse the events here — the GUI dispatches by envelope type. This
    keeps the BFF independent of SDK version changes in chemclaw2.
    """
    async def proxy() -> Any:
        async with (
            client(user["sub"], user["token"], timeout=None) as c,
            c.stream("POST", "/api/chat", json=body.model_dump(exclude_none=True)) as r,
        ):
            r.raise_for_status()
            async for chunk in r.aiter_bytes():
                yield chunk

    return StreamingResponse(
        proxy(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache, no-store",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )
