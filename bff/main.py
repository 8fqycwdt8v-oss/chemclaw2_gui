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
def health() -> dict[str, bool]:
    return {"ok": True}


app.include_router(chat.router)
app.include_router(wiki.router)
app.include_router(search.router)
