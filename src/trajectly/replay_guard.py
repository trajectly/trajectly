# Compatibility shim — real code lives in trajectly.core.replay_guard
# Uses sys.modules aliasing so monkeypatch on this module affects core too.
import sys as _sys

import trajectly.core.replay_guard as _mod  # noqa: E402

_sys.modules[__name__] = _mod
