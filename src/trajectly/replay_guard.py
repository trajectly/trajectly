from __future__ import annotations

import importlib
import os
import shlex
import socket
import subprocess
import urllib.parse
import urllib.request
from typing import Any


class NetworkBlockedError(RuntimeError):
    pass


_PATCHED = False
_ALLOWLIST: tuple[str, ...] = ()
_SUBPROCESS_ALLOWLIST: tuple[str, ...] = ()
_SUBPROCESS_DENYLIST = ("curl", "wget", "http", "https", "nc", "ncat", "telnet")

_ORIGINAL_CREATE_CONNECTION: Any = socket.create_connection
_ORIGINAL_GETADDRINFO: Any = socket.getaddrinfo
_ORIGINAL_SOCKET_CONNECT: Any = socket.socket.connect
_ORIGINAL_SOCKET_CONNECT_EX: Any = socket.socket.connect_ex
_ORIGINAL_SOCKET_SENDTO: Any = socket.socket.sendto
_ORIGINAL_URLOPEN: Any = urllib.request.urlopen
_ORIGINAL_SUBPROCESS_RUN: Any = subprocess.run
_ORIGINAL_SUBPROCESS_POPEN: Any = subprocess.Popen

_BASE_URLOPEN: Any = urllib.request.urlopen
_BASE_SUBPROCESS_RUN: Any = subprocess.run
_BASE_SUBPROCESS_POPEN: Any = subprocess.Popen

_REQUESTS_SESSION_REQUEST: Any = None
_HTTPX_CLIENT_REQUEST: Any = None
_HTTPX_ASYNC_CLIENT_REQUEST: Any = None
_WEBSOCKET_CREATE_CONNECTION: Any = None


def _extract_host(address: Any) -> str:
    if isinstance(address, (list, tuple)) and address:
        return str(address[0]).strip().lower()
    if isinstance(address, bytes):
        return address.decode("utf-8", errors="ignore").strip().lower()
    if isinstance(address, str):
        return address.strip().lower()
    return ""


def _host_from_url(raw_url: Any) -> str:
    if hasattr(raw_url, "full_url"):
        parsed = urllib.parse.urlparse(str(raw_url.full_url))
    else:
        parsed = urllib.parse.urlparse(str(raw_url))
    return (parsed.hostname or "").strip().lower()


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
    suffix = f" ({reason})" if reason else ""
    raise NetworkBlockedError(
        "Trajectly replay mode blocks network access. "
        "Use recorded fixtures, configure contracts.network.allowlist, or disable replay mode."
        f"{suffix}"
    )


def _guard_create_connection(address: Any, *args: Any, **kwargs: Any) -> Any:
    if _allowed(address):
        return _ORIGINAL_CREATE_CONNECTION(address, *args, **kwargs)
    _blocked(f"host={_extract_host(address) or 'unknown'}")


def _guard_getaddrinfo(host: Any, *args: Any, **kwargs: Any) -> Any:
    if _allowed(host):
        return _ORIGINAL_GETADDRINFO(host, *args, **kwargs)
    _blocked(f"dns={_extract_host(host) or 'unknown'}")


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


def _guard_urlopen(url: Any, *args: Any, **kwargs: Any) -> Any:
    host = _host_from_url(url)
    if _allowed(host):
        return _ORIGINAL_URLOPEN(url, *args, **kwargs)
    _blocked(f"url={host or 'unknown'}")


def _guard_requests_request(self: Any, method: str, url: str, *args: Any, **kwargs: Any) -> Any:
    host = _host_from_url(url)
    if _allowed(host):
        if _REQUESTS_SESSION_REQUEST is None:
            _blocked("requests-not-patched")
        return _REQUESTS_SESSION_REQUEST(self, method, url, *args, **kwargs)
    _blocked(f"requests={host or 'unknown'}")


def _guard_httpx_request(self: Any, method: str, url: Any, *args: Any, **kwargs: Any) -> Any:
    host = _host_from_url(url)
    if _allowed(host):
        if _HTTPX_CLIENT_REQUEST is None:
            _blocked("httpx-client-not-patched")
        return _HTTPX_CLIENT_REQUEST(self, method, url, *args, **kwargs)
    _blocked(f"httpx={host or 'unknown'}")


async def _guard_httpx_async_request(self: Any, method: str, url: Any, *args: Any, **kwargs: Any) -> Any:
    host = _host_from_url(url)
    if _allowed(host):
        if _HTTPX_ASYNC_CLIENT_REQUEST is None:
            _blocked("httpx-async-not-patched")
        return await _HTTPX_ASYNC_CLIENT_REQUEST(self, method, url, *args, **kwargs)
    _blocked(f"httpx_async={host or 'unknown'}")


def _guard_websocket_create_connection(url: Any, *args: Any, **kwargs: Any) -> Any:
    host = _host_from_url(url)
    if _allowed(host):
        if _WEBSOCKET_CREATE_CONNECTION is None:
            _blocked("websocket-not-patched")
        return _WEBSOCKET_CREATE_CONNECTION(url, *args, **kwargs)
    _blocked(f"websocket={host or 'unknown'}")


def _extract_command_name(command: Any) -> str:
    if isinstance(command, str):
        tokens = shlex.split(command)
        if not tokens:
            return ""
        return tokens[0].strip().lower()
    if isinstance(command, (list, tuple)) and command:
        return str(command[0]).strip().lower()
    return ""


def _is_blocked_subprocess(command: Any) -> bool:
    name = _extract_command_name(command)
    if not name:
        return False
    if name in _SUBPROCESS_ALLOWLIST:
        return False
    return name in _SUBPROCESS_DENYLIST


def _guard_subprocess_run(*args: Any, **kwargs: Any) -> Any:
    command = args[0] if args else kwargs.get("args")
    if _is_blocked_subprocess(command):
        _blocked(f"subprocess={_extract_command_name(command)}")
    return _ORIGINAL_SUBPROCESS_RUN(*args, **kwargs)


def _guard_subprocess_popen(*args: Any, **kwargs: Any) -> Any:
    command = args[0] if args else kwargs.get("args")
    if _is_blocked_subprocess(command):
        _blocked(f"subprocess={_extract_command_name(command)}")
    return _ORIGINAL_SUBPROCESS_POPEN(*args, **kwargs)


def activate() -> None:
    global _PATCHED
    global _ALLOWLIST
    global _SUBPROCESS_ALLOWLIST
    global _ORIGINAL_CREATE_CONNECTION
    global _ORIGINAL_GETADDRINFO
    global _ORIGINAL_SOCKET_CONNECT
    global _ORIGINAL_SOCKET_CONNECT_EX
    global _ORIGINAL_SOCKET_SENDTO
    global _ORIGINAL_URLOPEN
    global _ORIGINAL_SUBPROCESS_RUN
    global _ORIGINAL_SUBPROCESS_POPEN
    global _REQUESTS_SESSION_REQUEST
    global _HTTPX_CLIENT_REQUEST
    global _HTTPX_ASYNC_CLIENT_REQUEST
    global _WEBSOCKET_CREATE_CONNECTION
    if _PATCHED:
        return

    allowlist = os.getenv("TRAJECTLY_NETWORK_ALLOWLIST", "")
    _ALLOWLIST = tuple(host.strip().lower() for host in allowlist.split(",") if host.strip())
    subprocess_allowlist = os.getenv("TRAJECTLY_SUBPROCESS_ALLOWLIST", "")
    _SUBPROCESS_ALLOWLIST = tuple(
        name.strip().lower()
        for name in subprocess_allowlist.split(",")
        if name.strip()
    )

    _ORIGINAL_CREATE_CONNECTION = socket.create_connection
    _ORIGINAL_GETADDRINFO = socket.getaddrinfo
    _ORIGINAL_SOCKET_CONNECT = socket.socket.connect
    _ORIGINAL_SOCKET_CONNECT_EX = socket.socket.connect_ex
    _ORIGINAL_SOCKET_SENDTO = socket.socket.sendto
    _ORIGINAL_URLOPEN = _BASE_URLOPEN
    _ORIGINAL_SUBPROCESS_RUN = _BASE_SUBPROCESS_RUN
    _ORIGINAL_SUBPROCESS_POPEN = _BASE_SUBPROCESS_POPEN

    socket.create_connection = _guard_create_connection
    socket.getaddrinfo = _guard_getaddrinfo
    socket.socket.connect = _guard_socket_connect  # type: ignore[method-assign,assignment]
    socket.socket.connect_ex = _guard_socket_connect_ex  # type: ignore[method-assign,assignment]
    socket.socket.sendto = _guard_socket_sendto  # type: ignore[method-assign,assignment]
    urllib.request.urlopen = _guard_urlopen
    subprocess_module: Any = subprocess
    subprocess_module.run = _guard_subprocess_run
    subprocess_module.Popen = _guard_subprocess_popen

    try:
        requests_module: Any = importlib.import_module("requests")
        current_request = requests_module.sessions.Session.request
        if current_request is not _guard_requests_request:
            _REQUESTS_SESSION_REQUEST = current_request
        requests_module.sessions.Session.request = _guard_requests_request
    except Exception:
        _REQUESTS_SESSION_REQUEST = None

    try:
        httpx_module: Any = importlib.import_module("httpx")
        current_client_request = httpx_module.Client.request
        current_async_request = httpx_module.AsyncClient.request
        if current_client_request is not _guard_httpx_request:
            _HTTPX_CLIENT_REQUEST = current_client_request
        if current_async_request is not _guard_httpx_async_request:
            _HTTPX_ASYNC_CLIENT_REQUEST = current_async_request
        httpx_module.Client.request = _guard_httpx_request
        httpx_module.AsyncClient.request = _guard_httpx_async_request
    except Exception:
        _HTTPX_CLIENT_REQUEST = None
        _HTTPX_ASYNC_CLIENT_REQUEST = None

    try:
        websocket_module: Any = importlib.import_module("websocket")
        current_create_connection = websocket_module.create_connection
        if current_create_connection is not _guard_websocket_create_connection:
            _WEBSOCKET_CREATE_CONNECTION = current_create_connection
        websocket_module.create_connection = _guard_websocket_create_connection
    except Exception:
        _WEBSOCKET_CREATE_CONNECTION = None

    _PATCHED = True
    os.environ["TRAJECTLY_REPLAY_GUARD_ACTIVE"] = "1"
