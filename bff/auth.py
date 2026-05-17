"""OIDC id_token verification against the IdP's JWKS endpoint.

The Streamlit GUI forwards `Authorization: Bearer <id_token>` on every BFF call.
We verify signature, audience, and expiry against the IdP's published JWKS,
extract the user identity, and attach it to the request state. Routes consume
this via FastAPI dependency injection.
"""

from functools import lru_cache
from typing import Any

import httpx
from fastapi import HTTPException, Request, status
from jose import jwt
from jose.exceptions import JWTError

from bff.config import IDP_AUDIENCE, IDP_DOMAIN

_JWKS_TTL_S = 3600


@lru_cache(maxsize=1)
def _jwks() -> dict[str, Any]:
    url = f"https://{IDP_DOMAIN}/.well-known/openid-configuration"
    discovery = httpx.get(url, timeout=10).raise_for_status().json()
    jwks_uri = discovery["jwks_uri"]
    return httpx.get(jwks_uri, timeout=10).raise_for_status().json()


def verify_token(token: str) -> dict[str, Any]:
    """Return the decoded claims if the token is valid; raise HTTPException otherwise."""
    try:
        unverified_header = jwt.get_unverified_header(token)
    except JWTError as exc:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Malformed token") from exc

    kid = unverified_header.get("kid")
    keys = [k for k in _jwks().get("keys", []) if k.get("kid") == kid]
    if not keys:
        # Refresh JWKS once in case of key rotation, then retry.
        _jwks.cache_clear()
        keys = [k for k in _jwks().get("keys", []) if k.get("kid") == kid]
    if not keys:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Unknown signing key")

    try:
        return jwt.decode(  # type: ignore[no-any-return]
            token,
            keys[0],
            algorithms=[unverified_header.get("alg", "RS256")],
            audience=IDP_AUDIENCE,
            options={"verify_at_hash": False},
        )
    except JWTError as exc:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid token") from exc


def require_user(request: Request) -> dict[str, str]:
    """FastAPI dependency: verify the Bearer token, return {sub, email, token}."""
    auth = request.headers.get("authorization", "")
    if not auth.lower().startswith("bearer "):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Missing bearer token")
    token = auth.split(" ", 1)[1].strip()
    claims = verify_token(token)
    sub = claims.get("sub")
    email = claims.get("email") or claims.get("preferred_username") or ""
    if not sub:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Token missing subject claim")
    return {"sub": sub, "email": email, "token": token}
