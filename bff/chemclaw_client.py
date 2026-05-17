"""HTTP client to the chemclaw2 backend.

Two modes:
  1. HMAC service token (CHEMCLAW2_SERVICE_SECRET set, chemclaw2 BACKLOG item #1 shipped).
  2. Bearer passthrough (CHEMCLAW2_SERVICE_SECRET empty — forwards the user id_token).

Mode 2 only works if chemclaw2 trusts the same IdP. Mode 1 is the production path.
"""

import hashlib
import hmac
import time

import httpx

from bff.config import CHEMCLAW2_API_URL, CHEMCLAW2_SERVICE_SECRET


def _auth_header(user_sub: str, user_token: str) -> dict[str, str]:
    if CHEMCLAW2_SERVICE_SECRET:
        iat = int(time.time())
        msg = f"{user_sub}:{iat}".encode()
        sig = hmac.new(CHEMCLAW2_SERVICE_SECRET.encode(), msg, hashlib.sha256).hexdigest()
        return {"Authorization": f"Bearer svc.{user_sub}.{iat}.{sig}"}
    return {"Authorization": f"Bearer {user_token}"}


def client(user_sub: str, user_token: str, timeout: float | None = 30) -> httpx.AsyncClient:
    return httpx.AsyncClient(
        base_url=CHEMCLAW2_API_URL,
        headers=_auth_header(user_sub, user_token),
        timeout=timeout,
    )
