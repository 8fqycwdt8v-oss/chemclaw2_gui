"""OIDC id_token verification against the IdP's JWKS endpoint.

The Streamlit GUI forwards `Authorization: Bearer <id_token>` on every BFF call.
We verify signature, audience, and expiry against the IdP's published JWKS,
extract the user identity, and attach it to the request state. Routes consume
this via FastAPI dependency injection.

PyJWT's PyJWKClient handles JWKS fetching, caching, and key rotation. We pick
the signing key for each token based on its `kid` header.
"""

from typing import Any

import jwt
from fastapi import HTTPException, Request, status
from jwt import PyJWKClient
from jwt.exceptions import InvalidTokenError, PyJWKClientError

from bff.config import IDP_AUDIENCE, IDP_DOMAIN

_JWKS_URI = f"https://{IDP_DOMAIN}/.well-known/jwks.json"
_JWKS_CACHE_TTL_S = 3600

_jwk_client = PyJWKClient(_JWKS_URI, cache_keys=True, lifespan=_JWKS_CACHE_TTL_S)


def verify_token(token: str) -> dict[str, Any]:
    """Return the decoded claims if the token is valid; raise HTTPException otherwise."""
    try:
        signing_key = _jwk_client.get_signing_key_from_jwt(token).key
    except PyJWKClientError as exc:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Unknown signing key") from exc
    except InvalidTokenError as exc:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Malformed token") from exc

    try:
        return jwt.decode(  # type: ignore[no-any-return]
            token,
            signing_key,
            algorithms=["RS256"],
            audience=IDP_AUDIENCE,
            options={"require": ["exp", "iat", "sub"]},
        )
    except InvalidTokenError as exc:
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
