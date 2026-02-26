# Compatibility shim — real code lives in trajectly.core.replay_guard
# Uses sys.modules aliasing so monkeypatch on this module affects core too.
from __future__ import annotations

import sys as _sys
from typing import TYPE_CHECKING

import trajectly.core.replay_guard as _mod

_sys.modules[__name__] = _mod

if TYPE_CHECKING:
    from trajectly.core.replay_guard import activate as activate
