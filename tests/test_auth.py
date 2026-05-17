"""Auth verification — happy path and rejection paths.

We avoid network by constructing a local RSA keypair, registering it as a
fake JWKS via monkeypatch, and minting tokens with python-jose.
"""

import os

# bff.auth reads config at import time; set env before importing it.
os.environ.setdefault("CHEMCLAW2_IDP_DOMAIN", "fake.example.com")
os.environ.setdefault("CHEMCLAW2_IDP_AUDIENCE", "api://test-audience")
os.environ.setdefault("CHEMCLAW2_API_URL", "http://nope")

from typing import Any  # noqa: E402

import pytest  # noqa: E402
from cryptography.hazmat.primitives import serialization  # noqa: E402
from cryptography.hazmat.primitives.asymmetric import rsa  # noqa: E402
from fastapi import HTTPException  # noqa: E402
from jose import jwk, jwt  # noqa: E402

from bff import auth as bff_auth  # noqa: E402


@pytest.fixture
def rsa_keypair() -> tuple[str, dict[str, Any]]:
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    private_pem = key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    ).decode()
    public_pem = key.public_key().public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    ).decode()
    public_jwk = jwk.construct(public_pem, algorithm="RS256").to_dict()
    public_jwk["kid"] = "test-kid"
    public_jwk["alg"] = "RS256"
    public_jwk["use"] = "sig"
    return private_pem, public_jwk


@pytest.fixture(autouse=True)
def stub_jwks(
    rsa_keypair: tuple[str, dict[str, Any]], monkeypatch: pytest.MonkeyPatch
) -> None:
    """Replace bff_auth._jwks with a stub that mimics lru_cache's interface.

    Production code calls `_jwks.cache_clear()` on the kid-not-found rotation
    path. The plain lambda lacks that attribute, so we attach a no-op.
    """
    _, public_jwk = rsa_keypair

    def fake_jwks() -> dict[str, Any]:
        return {"keys": [public_jwk]}

    fake_jwks.cache_clear = lambda: None  # type: ignore[attr-defined]
    monkeypatch.setattr(bff_auth, "_jwks", fake_jwks)


def _mint(private_pem: str, *, sub: str = "user-1", aud: str = "api://test-audience") -> str:
    return jwt.encode(
        {"sub": sub, "email": "u@example.com", "aud": aud, "iat": 0, "exp": 9999999999},
        private_pem,
        algorithm="RS256",
        headers={"kid": "test-kid"},
    )


def test_valid_token_returns_claims(rsa_keypair: tuple[str, dict[str, Any]]) -> None:
    private_pem, _ = rsa_keypair
    claims = bff_auth.verify_token(_mint(private_pem))
    assert claims["sub"] == "user-1"
    assert claims["email"] == "u@example.com"


def test_wrong_audience_rejected(rsa_keypair: tuple[str, dict[str, Any]]) -> None:
    private_pem, _ = rsa_keypair
    token = _mint(private_pem, aud="api://other")
    with pytest.raises(HTTPException) as exc:
        bff_auth.verify_token(token)
    assert exc.value.status_code == 401


def test_tampered_signature_rejected(rsa_keypair: tuple[str, dict[str, Any]]) -> None:
    private_pem, _ = rsa_keypair
    token = _mint(private_pem)
    # Reverse the signature segment — guaranteed to invalidate it.
    header, payload, sig = token.split(".")
    bad = f"{header}.{payload}.{sig[::-1]}"
    with pytest.raises(HTTPException) as exc:
        bff_auth.verify_token(bad)
    assert exc.value.status_code == 401


def test_tampered_payload_rejected(rsa_keypair: tuple[str, dict[str, Any]]) -> None:
    private_pem, _ = rsa_keypair
    token = _mint(private_pem)
    # Swap payload for one minted with a different audience; signature no longer matches.
    other = _mint(private_pem, aud="api://other")
    header, _, sig = token.split(".")
    _, other_payload, _ = other.split(".")
    bad = f"{header}.{other_payload}.{sig}"
    with pytest.raises(HTTPException) as exc:
        bff_auth.verify_token(bad)
    assert exc.value.status_code == 401


def test_malformed_token_rejected() -> None:
    with pytest.raises(HTTPException) as exc:
        bff_auth.verify_token("not-a-jwt")
    assert exc.value.status_code == 401
