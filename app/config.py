import os


def _required(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        raise RuntimeError(f"Missing required env var: {name}")
    return value


BFF_URL: str = os.environ.get("STREAMLIT_BFF_URL", "http://localhost:8000")
LOGIN_PROVIDER: str = os.environ.get("STREAMLIT_LOGIN_PROVIDER", "microsoft")
REQUEST_TIMEOUT_S: float = float(os.environ.get("STREAMLIT_REQUEST_TIMEOUT_S", "30"))
