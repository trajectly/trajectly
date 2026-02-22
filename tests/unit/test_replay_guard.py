from __future__ import annotations

import types

import pytest

from trajectly import replay_guard


class _FakeSocketClass:
    def connect(self, *_args, **_kwargs):
        return None

    def connect_ex(self, *_args, **_kwargs):
        return 0

    def sendto(self, *_args, **_kwargs):
        return 0


def _fake_create_connection(*_args, **_kwargs):
    return None


def test_activate_blocks_network_and_sets_env(monkeypatch: pytest.MonkeyPatch) -> None:
    fake_socket_module = types.SimpleNamespace(
        create_connection=_fake_create_connection,
        socket=_FakeSocketClass,
    )

    monkeypatch.setattr(replay_guard, "socket", fake_socket_module)
    monkeypatch.setattr(replay_guard, "_PATCHED", False)
    monkeypatch.delenv("TRAJECTLY_REPLAY_GUARD_ACTIVE", raising=False)
    monkeypatch.delenv("TRAJECTLY_NETWORK_ALLOWLIST", raising=False)

    replay_guard.activate()

    with pytest.raises(replay_guard.NetworkBlockedError):
        fake_socket_module.create_connection(("localhost", 80))
    with pytest.raises(replay_guard.NetworkBlockedError):
        _FakeSocketClass().connect(("localhost", 80))

    assert replay_guard._PATCHED is True
    assert "TRAJECTLY_REPLAY_GUARD_ACTIVE" in __import__("os").environ


def test_activate_is_idempotent(monkeypatch: pytest.MonkeyPatch) -> None:
    fake_socket_module = types.SimpleNamespace(
        create_connection=_fake_create_connection,
        socket=_FakeSocketClass,
    )
    monkeypatch.setattr(replay_guard, "socket", fake_socket_module)
    monkeypatch.setattr(replay_guard, "_PATCHED", False)
    monkeypatch.delenv("TRAJECTLY_NETWORK_ALLOWLIST", raising=False)

    replay_guard.activate()
    replay_guard.activate()

    assert replay_guard._PATCHED is True


def test_activate_respects_network_allowlist(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = {"create_connection": 0, "connect": 0}

    class _TrackingSocketClass:
        def connect(self, *_args, **_kwargs):
            calls["connect"] += 1
            return None

        def connect_ex(self, *_args, **_kwargs):
            return 0

        def sendto(self, *_args, **_kwargs):
            return 0

    def _tracking_create_connection(*_args, **_kwargs):
        calls["create_connection"] += 1
        return "ok"

    fake_socket_module = types.SimpleNamespace(
        create_connection=_tracking_create_connection,
        socket=_TrackingSocketClass,
    )

    monkeypatch.setattr(replay_guard, "socket", fake_socket_module)
    monkeypatch.setattr(replay_guard, "_PATCHED", False)
    monkeypatch.setenv("TRAJECTLY_NETWORK_ALLOWLIST", "localhost,api.example.com")

    replay_guard.activate()

    assert fake_socket_module.create_connection(("localhost", 443)) == "ok"
    assert _TrackingSocketClass().connect(("api.example.com", 443)) is None
    with pytest.raises(replay_guard.NetworkBlockedError):
        fake_socket_module.create_connection(("blocked.example", 443))
    assert calls["create_connection"] == 1
    assert calls["connect"] == 1
