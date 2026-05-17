from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from bff.routes import chat, search, wiki

app = FastAPI(title="chemclaw2-gui BFF", version="0.1.0")

# Streamlit container is the only legitimate origin. CORS isn't strictly required
# when the BFF is reached server-to-server from Streamlit, but allowing the same
# origin keeps things working if Streamlit ever calls the BFF from the browser.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["GET", "POST", "PUT"],
    allow_headers=["Authorization", "Content-Type"],
)


@app.get("/health")
async def health() -> dict[str, object]:
    """Liveness + downstream backend state.

    Per chemclaw2 CLAUDE.md observability rule #6 ("Health endpoints reflect
    downstream state"), we surface the backend's health (DB up, fingerprint
    backlog) alongside our own. If the backend is unreachable, this returns
    {ok: True, backend: {ok: False, error: ...}} — our own liveness still says
    OK because the BFF process itself is fine.
    """
    import httpx as _httpx

    from bff.config import CHEMCLAW2_API_URL

    backend: dict[str, object] = {"ok": False}
    try:
        async with _httpx.AsyncClient(timeout=5) as c:
            r = await c.get(f"{CHEMCLAW2_API_URL}/api/health")
            backend = r.json() if r.status_code == 200 else {"ok": False, "status": r.status_code}
    except Exception as exc:  # noqa: BLE001 — surface ANY downstream failure
        backend = {"ok": False, "error": str(exc)}
    return {"ok": True, "backend": backend}


app.include_router(chat.router)
app.include_router(wiki.router)
app.include_router(search.router)
