"""Tests for the bits of api_client that don't need Streamlit boot —
specifically the sub-validation regex and HMAC token shape.
"""

import os

# Set required env before importing the module.
os.environ.setdefault("CHEMCLAW2_API_URL", "http://nope")

import pytest  # noqa: E402

from app.components import api_client  # noqa: E402


def test_sub_re_accepts_entra_guid_style() -> None:
    # Entra ID `sub` claim is a base64url-ish opaque string.
    assert api_client._SUB_RE.match("AAAAAAAAAAAAAAAAAAAA_BBBBBBB-CCC")


def test_sub_re_accepts_google_numeric() -> None:
    assert api_client._SUB_RE.match("104726847234234234234")


def test_sub_re_accepts_auth0_pipe_format() -> None:
    # Auth0 emits `provider|id`, e.g. `auth0|6123abc...` or `google-oauth2|123`.
    assert api_client._SUB_RE.match("auth0|6123abc4567def890")
    assert api_client._SUB_RE.match("google-oauth2|104726847234234234")


def test_sub_re_rejects_dot() -> None:
    # `.` would break the `svc.<sub>.<iat>.<sig>` wire format.
    assert api_client._SUB_RE.match("bad.sub.value") is None


def test_sub_re_rejects_colon() -> None:
    # `:` would create HMAC message ambiguity with `f"{sub}:{iat}"`.
    assert api_client._SUB_RE.match("bad:sub") is None


def test_sub_re_rejects_whitespace() -> None:
    assert api_client._SUB_RE.match("bad sub") is None
    assert api_client._SUB_RE.match("trailing ") is None


def test_sub_re_rejects_overlong() -> None:
    assert api_client._SUB_RE.match("a" * 256) is None
    assert api_client._SUB_RE.match("a" * 255) is not None


def test_sub_re_rejects_empty() -> None:
    assert api_client._SUB_RE.match("") is None


def test_auth_header_mock_format(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(api_client, "_user_sub", lambda: "user-1")
    monkeypatch.setattr(api_client, "CHEMCLAW2_SERVICE_SECRET", "")
    assert api_client._auth_header() == {"Authorization": "Bearer mock:user-1"}


def test_auth_header_hmac_format(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(api_client, "_user_sub", lambda: "user-1")
    monkeypatch.setattr(api_client, "CHEMCLAW2_SERVICE_SECRET", "shh")
    # Freeze time so we can compute the expected signature deterministically.
    monkeypatch.setattr(api_client.time, "time", lambda: 1_700_000_000)
    import hashlib
    import hmac

    expected_sig = hmac.new(
        b"shh", b"user-1:1700000000", hashlib.sha256
    ).hexdigest()
    assert api_client._auth_header() == {
        "Authorization": f"Bearer svc.user-1.1700000000.{expected_sig}"
    }
