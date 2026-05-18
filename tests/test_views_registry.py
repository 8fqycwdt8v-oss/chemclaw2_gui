"""Lock the view-registry discovery contract.

Adding a new view module is supposed to be a drop-in. These tests verify
that contract by importing the registry fresh and asserting shape +
discovery behavior.
"""

import importlib

import pytest

from app.views import VIEWS
from app.views._base import View


def test_registry_discovers_known_views() -> None:
    # Every starter view from the plan must be present.
    for view_id in ("research", "campaign", "contradictions", "todos"):
        assert view_id in VIEWS, f"View `{view_id}` was not auto-discovered"


def test_every_view_satisfies_the_contract() -> None:
    for view_id, view in VIEWS.items():
        assert isinstance(view, View), f"{view_id} not a View instance"
        assert view.id == view_id
        assert view.label, f"{view_id} missing LABEL"
        assert view.icon, f"{view_id} missing ICON"
        assert view.commands, f"{view_id} has no COMMANDS"
        assert all(c == c.lower() for c in view.commands), (
            f"{view_id} has non-lowercase commands: {view.commands}"
        )
        assert callable(view.matches)
        assert callable(view.render_card)
        assert callable(view.render)


def test_view_ids_are_unique() -> None:
    # The registry raises on duplicate during _load; here we just confirm
    # the post-condition holds for the current set.
    ids = [v.id for v in VIEWS.values()]
    assert len(ids) == len(set(ids)), f"duplicate view ids in registry: {ids}"


def test_commands_are_unique_across_views() -> None:
    # Quick-open routing picks the first matching view; overlapping commands
    # would cause ambiguous behavior.
    seen: dict[str, str] = {}
    for view in VIEWS.values():
        for cmd in view.commands:
            assert cmd not in seen, (
                f"command `{cmd}` claimed by both `{seen[cmd]}` and `{view.id}`"
            )
            seen[cmd] = view.id


def test_matches_is_a_pure_function_of_state_dict() -> None:
    # Calling matches() with an empty state must not raise. View matchers
    # are evaluated on every Streamlit rerun, including before the user
    # has done anything that would populate state.
    empty_state: dict = {}
    for view in VIEWS.values():
        try:
            result = view.matches(empty_state)
        except Exception as exc:  # noqa: BLE001 — surface any failure as a test failure
            pytest.fail(f"{view.id}.matches({{}}) raised {exc!r}")
        assert isinstance(result, bool), (
            f"{view.id}.matches() returned {type(result).__name__}, expected bool"
        )


def test_underscore_modules_are_skipped() -> None:
    # `_base` defines the View dataclass; it must NOT be loaded as a view.
    assert "_base" not in VIEWS
    # And it shouldn't appear under any other id either.
    assert all(v.label != "View" for v in VIEWS.values())


def test_registry_is_importable_repeatedly() -> None:
    # Reimporting should be idempotent — no duplicate-id RuntimeError.
    import app.views as views_module

    importlib.reload(views_module)
    assert len(views_module.VIEWS) == len(VIEWS)
