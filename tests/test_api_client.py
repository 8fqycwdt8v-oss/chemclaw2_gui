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


def test_post_feedback_rejects_invalid_score(monkeypatch: pytest.MonkeyPatch) -> None:
    # Backend's FeedbackBody has score: Literal[1, -1]. Guard client-side so
    # bad inputs fail fast with a clear message instead of a 422 round-trip.
    import pytest as _pytest

    with _pytest.raises(ValueError, match="score must be"):
        api_client.post_feedback("session-1", 0, 0)
    with _pytest.raises(ValueError, match="score must be"):
        api_client.post_feedback("session-1", 0, 2)
    with _pytest.raises(ValueError, match="score must be"):
        api_client.post_feedback("session-1", 0, -2)


def test_hmac_token_matches_chemclaw2_verifier_contract(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Cross-repo contract lock.

    chemclaw2's `_verify_svc_token` (api/auth.py, PR #87) enforces:
      - exactly 4 dot-separated parts; parts[0] == "svc"
      - parts[1] (sub) matches ^[A-Za-z0-9_\\-|]{1,255}$
      - parts[2] (iat) is a valid int within ±300s of `time.time()`
      - parts[3] (sig) == hmac_sha256(f"{sub}:{iat}", secret).hexdigest()

    If anyone changes our construction in a way that would fail any of those
    checks, this test breaks immediately — before chemclaw2 rejects in prod.
    """
    import hashlib
    import hmac
    import re
    import time as real_time

    monkeypatch.setattr(api_client, "_user_sub", lambda: "abc-123|user")
    monkeypatch.setattr(api_client, "CHEMCLAW2_SERVICE_SECRET", "shared-secret")

    header = api_client._auth_header()["Authorization"]
    assert header.startswith("Bearer ")
    token = header.removeprefix("Bearer ")

    parts = token.split(".")
    assert len(parts) == 4, f"svc token must have exactly 4 parts, got {len(parts)}"
    prefix, sub, iat_str, sig = parts

    # Constraint 1: prefix
    assert prefix == "svc"

    # Constraint 2: sub regex — identical to chemclaw2 `_SVC_SUB_RE`
    assert re.fullmatch(r"^[A-Za-z0-9_\-|]{1,255}$", sub)

    # Constraint 3: iat is int, within ±300s of now
    iat = int(iat_str)
    assert abs(int(real_time.time()) - iat) <= 300

    # Constraint 4: sig matches HMAC of f"{sub}:{iat}"
    expected = hmac.new(
        b"shared-secret", f"{sub}:{iat}".encode(), hashlib.sha256
    ).hexdigest()
    assert hmac.compare_digest(expected, sig)
