from __future__ import annotations

import os
import socket
from typing import Any


class NetworkBlockedError(RuntimeError):
    pass


_PATCHED = False
_ALLOWLIST: tuple[str, ...] = ()
_ORIGINAL_CREATE_CONNECTION: Any = socket.create_connection
_ORIGINAL_SOCKET_CONNECT: Any = socket.socket.connect
_ORIGINAL_SOCKET_CONNECT_EX: Any = socket.socket.connect_ex
_ORIGINAL_SOCKET_SENDTO: Any = socket.socket.sendto


def _extract_host(address: Any) -> str:
    if isinstance(address, (list, tuple)) and address:
        return str(address[0]).strip().lower()
    if isinstance(address, bytes):
        return address.decode("utf-8", errors="ignore").strip().lower()
    if isinstance(address, str):
        return address.strip().lower()
    return ""


def _allowed(address: Any) -> bool:
    if not _ALLOWLIST:
        return False
    host = _extract_host(address)
    if not host:
        return False
    for allowed_host in _ALLOWLIST:
        if host == allowed_host or host.endswith(f".{allowed_host}"):
            return True
    return False


def _blocked(reason: str | None = None) -> None:
    if reason:
        suffix = f" ({reason})"
    else:
        suffix = ""
    raise NetworkBlockedError(
        "Trajectly replay mode blocks network access. "
        "Use recorded fixtures, configure contracts.network.allowlist, or disable replay mode."
        f"{suffix}"
    )


def _guard_create_connection(address: Any, *args: Any, **kwargs: Any) -> Any:
    if _allowed(address):
        return _ORIGINAL_CREATE_CONNECTION(address, *args, **kwargs)
    _blocked(f"host={_extract_host(address) or 'unknown'}")


def _guard_socket_connect(sock: Any, address: Any, *args: Any, **kwargs: Any) -> Any:
    if _allowed(address):
        return _ORIGINAL_SOCKET_CONNECT(sock, address, *args, **kwargs)
    _blocked(f"host={_extract_host(address) or 'unknown'}")


def _guard_socket_connect_ex(sock: Any, address: Any, *args: Any, **kwargs: Any) -> Any:
    if _allowed(address):
        return _ORIGINAL_SOCKET_CONNECT_EX(sock, address, *args, **kwargs)
    _blocked(f"host={_extract_host(address) or 'unknown'}")


def _guard_socket_sendto(sock: Any, data: Any, address: Any, *args: Any, **kwargs: Any) -> Any:
    if _allowed(address):
        return _ORIGINAL_SOCKET_SENDTO(sock, data, address, *args, **kwargs)
    _blocked(f"host={_extract_host(address) or 'unknown'}")


def activate() -> None:
    global _PATCHED
    global _ALLOWLIST
    global _ORIGINAL_CREATE_CONNECTION
    global _ORIGINAL_SOCKET_CONNECT
    global _ORIGINAL_SOCKET_CONNECT_EX
    global _ORIGINAL_SOCKET_SENDTO
    if _PATCHED:
        return
    allowlist = os.getenv("TRAJECTLY_NETWORK_ALLOWLIST", "")
    _ALLOWLIST = tuple(host.strip().lower() for host in allowlist.split(",") if host.strip())

    _ORIGINAL_CREATE_CONNECTION = socket.create_connection
    _ORIGINAL_SOCKET_CONNECT = socket.socket.connect
    _ORIGINAL_SOCKET_CONNECT_EX = socket.socket.connect_ex
    _ORIGINAL_SOCKET_SENDTO = socket.socket.sendto

    socket.create_connection = _guard_create_connection
    socket.socket.connect = _guard_socket_connect  # type: ignore[method-assign]
    socket.socket.connect_ex = _guard_socket_connect_ex  # type: ignore[method-assign]
    socket.socket.sendto = _guard_socket_sendto  # type: ignore[method-assign]
    _PATCHED = True
    os.environ["TRAJECTLY_REPLAY_GUARD_ACTIVE"] = "1"
