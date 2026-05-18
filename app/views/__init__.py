"""Auto-discovering view registry.

Drop a Python module under `app/views/` exporting `ID`, `LABEL`, `ICON`,
`COMMANDS`, `matches`, `render_card`, `render` and it joins the registry on
the next reload — no central registration call.

The dock (`app/components/views_dock.py`) imports `VIEWS` from here.
"""

from __future__ import annotations

import importlib
import pkgutil

from app.views._base import View

VIEWS: dict[str, View] = {}


def _load() -> None:
    for _, name, _is_pkg in pkgutil.iter_modules(__path__):
        if name.startswith("_"):
            continue
        module = importlib.import_module(f"app.views.{name}")
        # Fail-loud if a view module is missing a required attribute. Better
        # than silently dropping it — a misnamed export is always a bug.
        view = View(
            id=module.ID,
            label=module.LABEL,
            icon=module.ICON,
            commands=tuple(module.COMMANDS),
            matches=module.matches,
            render_card=module.render_card,
            render=module.render,
        )
        if view.id in VIEWS:
            raise RuntimeError(f"Duplicate view id: {view.id} in {name}")
        VIEWS[view.id] = view


_load()
