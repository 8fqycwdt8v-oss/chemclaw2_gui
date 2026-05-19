"""Locks the CLAUDE.md invariant: admin/privileged views must surface a
clear "Admin access required." message when their API helper raises
httpx.HTTPStatusError(403), not bubble the raw exception.

Drift here is what prompted the original audit (budgets.py was missing
the 403 branch while audit.py and tool_permissions.py had it). This test
re-runs each registered admin view through a 403 and asserts they all
render the same message.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock, patch

import httpx
import pytest


def _make_403_error() -> httpx.HTTPStatusError:
    request = httpx.Request("GET", "https://example.invalid/api/x")
    response = httpx.Response(403, request=request)
    return httpx.HTTPStatusError("forbidden", request=request, response=response)


# (view_module_path, api_client_symbol_to_mock)
# These three modules are the admin/privileged views per CLAUDE.md.
ADMIN_VIEWS: list[tuple[str, str]] = [
    ("app.views.audit", "list_audit_overrides"),
    ("app.views.budgets", "get_my_budget"),
    ("app.views.tool_permissions", "list_tool_permissions"),
]


@pytest.mark.parametrize(("module_path", "api_symbol"), ADMIN_VIEWS)
def test_admin_view_renders_admin_required_on_403(module_path: str, api_symbol: str) -> None:
    import importlib

    view = importlib.import_module(module_path)

    # Patch the api_client helper to raise a 403 the moment the view calls it.
    with patch(f"{module_path}.{api_symbol}", side_effect=_make_403_error()):
        # Patch streamlit primitives used by render() so we can observe what
        # was shown without booting Streamlit. .error is the call we care about.
        fake_st: Any = MagicMock()
        # st.tabs / st.columns return iterables; default MagicMock works for
        # simple `with` patterns. Provide explicit returns to keep budgets.py's
        # `_bar` path inert when render() doesn't reach it.
        fake_st.tabs.return_value = (MagicMock(), MagicMock())

        with patch.object(view, "st", fake_st):
            view.render({})

        error_calls = [c.args[0] for c in fake_st.error.call_args_list if c.args]
        assert any("Admin access required" in msg for msg in error_calls), (
            f"{module_path}.render() did not surface 'Admin access required.' "
            f"on httpx.HTTPStatusError(403). Calls: {error_calls!r}"
        )
