import os

CHEMCLAW2_API_URL: str = os.environ.get("CHEMCLAW2_API_URL", "http://localhost:8080")
# Optional. When set, requests use HMAC service-token auth (svc.<sub>.<iat>.<sig>);
# requires chemclaw2 to implement the verifier (BACKLOG item). When empty, requests
# use `Bearer mock:<sub>`, which chemclaw2 accepts in dev mode (CLERK_SECRET_KEY
# unset or starts with "sk_test_REPLACE").
CHEMCLAW2_SERVICE_SECRET: str = os.environ.get("CHEMCLAW2_SERVICE_SECRET", "")
LOGIN_PROVIDER: str = os.environ.get("STREAMLIT_LOGIN_PROVIDER", "microsoft")
REQUEST_TIMEOUT_S: float = float(os.environ.get("STREAMLIT_REQUEST_TIMEOUT_S", "30"))
