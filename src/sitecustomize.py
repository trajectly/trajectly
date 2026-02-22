from __future__ import annotations

import os

if os.getenv("TRAJECTLY_REPLAY_GUARD") == "1":
    from trajectly.replay_guard import activate

    activate()
