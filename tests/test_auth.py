"""Auth verification — happy path and rejection paths.

We avoid network by constructing a local RSA keypair, registering it as a
fake JWKS via monkeypatch, and minting tokens with PyJWT.
"""

import os

# bff.auth reads config at import time; set env before importing it.
os.environ.setdefault("CHEMCLAW2_IDP_DOMAIN", "fake.example.com")
os.environ.setdefault("CHEMCLAW2_IDP_AUDIENCE", "api://test-audience")
os.environ.setdefault("CHEMCLAW2_API_URL", "http://nope")

import jwt  # noqa: E402
import pytest  # noqa: E402
from cryptography.hazmat.primitives import serialization  # noqa: E402
from cryptography.hazmat.primitives.asymmetric import rsa  # noqa: E402
from cryptography.hazmat.primitives.asymmetric.rsa import RSAPrivateKey  # noqa: E402
from fastapi import HTTPException  # noqa: E402
from jwt import PyJWK  # noqa: E402

from bff import auth as bff_auth  # noqa: E402


@pytest.fixture
def rsa_keypair() -> tuple[str, RSAPrivateKey]:
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    private_pem = key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    ).decode()
    return private_pem, key


@pytest.fixture(autouse=True)
def stub_jwks(
    rsa_keypair: tuple[str, RSAPrivateKey], monkeypatch: pytest.MonkeyPatch
) -> None:
    """Replace the PyJWK signing-key lookup with one that always returns our public key.

    Production code calls `_jwk_client.get_signing_key_from_jwt(token)`. We stub
    that method so tests don't need a live JWKS endpoint.
    """
    _, key = rsa_keypair
    pyjwk = PyJWK.from_json(
        '{"kty":"RSA","alg":"RS256","use":"sig","kid":"test-kid",'
        f'"n":"{_b64uint(key.public_key().public_numbers().n)}",'
        f'"e":"{_b64uint(key.public_key().public_numbers().e)}"}}'
    )

    def fake_lookup(_self: object, token: str) -> PyJWK:
        # Reject obviously-malformed tokens the same way PyJWT would.
        header = jwt.get_unverified_header(token)
        if header.get("kid") != "test-kid":
            from jwt.exceptions import PyJWKClientError

            raise PyJWKClientError("kid not found")
        return pyjwk

    monkeypatch.setattr(
        bff_auth._jwk_client,
        "get_signing_key_from_jwt",
        fake_lookup.__get__(bff_auth._jwk_client),
    )


def _b64uint(n: int) -> str:
    """Base64url-encode an unsigned int as a JWK n/e component."""
    import base64

    length = (n.bit_length() + 7) // 8
    return base64.urlsafe_b64encode(n.to_bytes(length, "big")).rstrip(b"=").decode()


def _mint(private_pem: str, *, sub: str = "user-1", aud: str = "api://test-audience") -> str:
    return jwt.encode(
        {"sub": sub, "email": "u@example.com", "aud": aud, "iat": 0, "exp": 9999999999},
        private_pem,
        algorithm="RS256",
        headers={"kid": "test-kid"},
    )


def test_valid_token_returns_claims(rsa_keypair: tuple[str, RSAPrivateKey]) -> None:
    private_pem, _ = rsa_keypair
    claims = bff_auth.verify_token(_mint(private_pem))
    assert claims["sub"] == "user-1"
    assert claims["email"] == "u@example.com"


def test_wrong_audience_rejected(rsa_keypair: tuple[str, RSAPrivateKey]) -> None:
    private_pem, _ = rsa_keypair
    token = _mint(private_pem, aud="api://other")
    with pytest.raises(HTTPException) as exc:
        bff_auth.verify_token(token)
    assert exc.value.status_code == 401


def test_tampered_signature_rejected(rsa_keypair: tuple[str, RSAPrivateKey]) -> None:
    private_pem, _ = rsa_keypair
    token = _mint(private_pem)
    # Reverse the signature segment — guaranteed to invalidate it.
    header, payload, sig = token.split(".")
    bad = f"{header}.{payload}.{sig[::-1]}"
    with pytest.raises(HTTPException) as exc:
        bff_auth.verify_token(bad)
    assert exc.value.status_code == 401


def test_tampered_payload_rejected(rsa_keypair: tuple[str, RSAPrivateKey]) -> None:
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


def test_unknown_kid_rejected(rsa_keypair: tuple[str, RSAPrivateKey]) -> None:
    private_pem, _ = rsa_keypair
    token = jwt.encode(
        {"sub": "u", "aud": "api://test-audience", "iat": 0, "exp": 9999999999},
        private_pem,
        algorithm="RS256",
        headers={"kid": "unknown-kid"},
    )
    with pytest.raises(HTTPException) as exc:
        bff_auth.verify_token(token)
    assert exc.value.status_code == 401
