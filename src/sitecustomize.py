from __future__ import annotations

import os

if os.getenv("TRAJECTLY_REPLAY_GUARD") == "1":
    # Import-time hook used by subprocess replays. Keeping this in
    # `sitecustomize` ensures the guard is active before user code runs.
    from trajectly.replay_guard import activate

    activate()

if os.getenv("TRAJECTLY_DETERMINISM_ACTIVE") == "1":
    # Determinism hooks patch clock/random/filesystem/subprocess behavior
    # for replay-safe execution before user agent modules are imported.
    from trajectly.determinism import activate_from_env

    activate_from_env()
