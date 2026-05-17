"""HTTP client to the chemclaw2 backend.

chemclaw2's auth (api/auth.py) verifies Clerk-issued JWTs against Clerk's
JWKS. The GUI authenticates via a different IdP (Entra/Auth0 via Streamlit
st.login), so we cannot forward the user's id_token to chemclaw2 — Clerk
would reject it. Three auth modes:

  1. HMAC service token (CHEMCLAW2_SERVICE_SECRET set; chemclaw2 BACKLOG
     item #1 must implement the verifier with a maxAge window).
  2. Clerk-mock dev token (`Bearer mock:<user_sub>`). chemclaw2 accepts
     this when its own CLERK_SECRET_KEY is unset or starts with
     `sk_test_REPLACE`. Use for local dev and integration testing.
  3. Bearer passthrough — forwards the user's IdP id_token. Only works if
     chemclaw2 is reconfigured to trust the GUI's IdP. NOT current default.

Mode selection: HMAC if secret set, else mock.
"""

import hashlib
import hmac
import time

import httpx

from bff.config import CHEMCLAW2_API_URL, CHEMCLAW2_SERVICE_SECRET


def _auth_header(user_sub: str, _user_token: str) -> dict[str, str]:
    # Service-token format: `Bearer svc.<sub>.<iat>.<sig>` where
    # sig = hmac_sha256(f"{sub}:{iat}", CHEMCLAW2_SERVICE_SECRET).hexdigest()
    # chemclaw2 BACKLOG item #1 MUST enforce a maxAge window on iat
    # (recommended: 300 seconds) to bound replay attacks.
    if CHEMCLAW2_SERVICE_SECRET:
        iat = int(time.time())
        msg = f"{user_sub}:{iat}".encode()
        sig = hmac.new(CHEMCLAW2_SERVICE_SECRET.encode(), msg, hashlib.sha256).hexdigest()
        return {"Authorization": f"Bearer svc.{user_sub}.{iat}.{sig}"}
    # Dev-mode fallback: chemclaw2 accepts `mock:<sub>` when its Clerk secret
    # is unset/test-placeholder. Production MUST set CHEMCLAW2_SERVICE_SECRET.
    return {"Authorization": f"Bearer mock:{user_sub}"}


def client(user_sub: str, user_token: str, timeout: float | None = 30) -> httpx.AsyncClient:
    return httpx.AsyncClient(
        base_url=CHEMCLAW2_API_URL,
        headers=_auth_header(user_sub, user_token),
        timeout=timeout,
    )
