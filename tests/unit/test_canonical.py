from __future__ import annotations

from trajectly.canonical import canonical_dumps, sha256_of_data, sha256_of_subset


def test_canonical_serialization_is_stable() -> None:
    left = {"b": 2, "a": [3, {"z": 0, "y": 1}]}
    right = {"a": [3, {"y": 1, "z": 0}], "b": 2}
    assert canonical_dumps(left) == canonical_dumps(right)
    assert sha256_of_data(left) == sha256_of_data(right)


def test_sha256_of_subset_ignores_requested_keys() -> None:
    payload = {"event_type": "tool_called", "payload": {"x": 1}, "rel_ms": 42}
    hash_a = sha256_of_subset(payload, ignored_keys={"rel_ms"})
    payload["rel_ms"] = 84
    hash_b = sha256_of_subset(payload, ignored_keys={"rel_ms"})
    assert hash_a == hash_b
