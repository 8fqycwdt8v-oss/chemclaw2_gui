"""Contract for a specialised view.

Every module in `app/views/` (except `_`-prefixed) must export the seven
attributes used to construct a `View`. The registry (`__init__.py`)
validates at import time.

Two render surfaces deliberately separate concerns:

- `render_card(state)` is the always-visible dock card. Compact (~1 row),
  shows state-at-a-glance, must NOT call backend services every rerun
  beyond what a `@st.cache_data`-wrapped api_client function already caches.
- `render(state)` is the full-focus dialog. Opens when the user clicks
  Expand on a card or quick-opens via a command. Only one dialog open at
  a time per Streamlit session.

`matches(state)` is the auto-pin heuristic. Pure function over a small
state dict (see `views_dock.build_state`). Runs on every rerun, so keep
it cheap: index into the dict, no I/O.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class View:
    id: str
    label: str
    icon: str
    commands: tuple[str, ...]
    matches: Callable[[dict[str, Any]], bool]
    render_card: Callable[[dict[str, Any]], None]
    render: Callable[[dict[str, Any]], None]
