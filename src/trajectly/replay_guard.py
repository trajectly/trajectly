from __future__ import annotations

import os
import socket
from typing import Any


class NetworkBlockedError(RuntimeError):
    pass


_PATCHED = False


def _blocked(*_args: Any, **_kwargs: Any) -> None:
    raise NetworkBlockedError(
        "Trajectly replay mode blocks network access. "
        "Use recorded fixtures or disable replay mode."
    )


def activate() -> None:
    global _PATCHED
    if _PATCHED:
        return
    socket.create_connection = _blocked  # type: ignore[assignment]
    socket.socket.connect = _blocked  # type: ignore[method-assign]
    socket.socket.connect_ex = _blocked  # type: ignore[assignment,method-assign]
    socket.socket.sendto = _blocked  # type: ignore[assignment,method-assign]
    _PATCHED = True
    os.environ["TRAJECTLY_REPLAY_GUARD_ACTIVE"] = "1"
