import os


def _required(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        raise RuntimeError(f"Missing required env var: {name}")
    return value


# IdP — built into the JWKS URI used by bff/auth.py
IDP_DOMAIN: str = _required("CHEMCLAW2_IDP_DOMAIN")
IDP_AUDIENCE: str = _required("CHEMCLAW2_IDP_AUDIENCE")

# Backend
CHEMCLAW2_API_URL: str = _required("CHEMCLAW2_API_URL")
# Empty disables HMAC service-token mode; BFF falls back to forwarding the user id_token as Bearer.
CHEMCLAW2_SERVICE_SECRET: str = os.environ.get("CHEMCLAW2_SERVICE_SECRET", "")
