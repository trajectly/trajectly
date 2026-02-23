from __future__ import annotations

import os

if os.getenv("TRAJECTLY_REPLAY_GUARD") == "1":
    # Import-time hook used by subprocess replays. Keeping this in
    # `sitecustomize` ensures the guard is active before user code runs.
    from trajectly.replay_guard import activate

    activate()
