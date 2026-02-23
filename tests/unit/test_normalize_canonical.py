from __future__ import annotations

from trajectly.normalize.canonical import CanonicalNormalizer


def test_canonical_normalizer_is_deterministic_for_repeated_runs() -> None:
    normalizer = CanonicalNormalizer()
    payload = {
        "kind": "TOOL_CALL",
        "payload": {
            "tool_name": "search",
            "args": {"q": "laptop", "timestamp": "volatile"},
            "request_id": "abc",
        },
    }

    first = normalizer.canonical_dumps(payload)
    for _ in range(100):
        assert normalizer.canonical_dumps(payload) == first


def test_canonical_normalizer_strips_volatile_fields_for_hashing() -> None:
    normalizer = CanonicalNormalizer()
    first = {"kind": "TOOL_CALL", "payload": {"tool_name": "search", "request_id": "one"}}
    second = {"kind": "TOOL_CALL", "payload": {"tool_name": "search", "request_id": "two"}}

    assert normalizer.sha256(first, strip_volatile=True) == normalizer.sha256(second, strip_volatile=True)
