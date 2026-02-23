"""Tests for canonical normalizer edge cases: NaN, Infinity, -Infinity, bytes,
nested volatile key stripping, float precision, sha256_subset."""

from __future__ import annotations

from trajectly.normalize.canonical import CanonicalNormalizer, canonical_dumps, sha256_of_data, sha256_of_subset


def test_nan_normalized_to_string() -> None:
    normalizer = CanonicalNormalizer()
    result = normalizer.normalize(float("nan"), strip_volatile=False)
    assert result == "NaN"


def test_positive_infinity_normalized_to_string() -> None:
    normalizer = CanonicalNormalizer()
    result = normalizer.normalize(float("inf"), strip_volatile=False)
    assert result == "Infinity"


def test_negative_infinity_normalized_to_string() -> None:
    normalizer = CanonicalNormalizer()
    result = normalizer.normalize(float("-inf"), strip_volatile=False)
    assert result == "-Infinity"


def test_nan_in_nested_dict() -> None:
    normalizer = CanonicalNormalizer()
    data = {"a": {"b": float("nan")}}
    result = normalizer.normalize(data, strip_volatile=False)
    assert result == {"a": {"b": "NaN"}}


def test_infinity_in_list() -> None:
    normalizer = CanonicalNormalizer()
    data = [1.0, float("inf"), float("-inf")]
    result = normalizer.normalize(data, strip_volatile=False)
    assert result == [1.0, "Infinity", "-Infinity"]


def test_bytes_decoded_to_utf8() -> None:
    normalizer = CanonicalNormalizer()
    result = normalizer.normalize(b"hello world", strip_volatile=False)
    assert result == "hello world"


def test_bytes_with_invalid_utf8_replaced() -> None:
    normalizer = CanonicalNormalizer()
    result = normalizer.normalize(b"\xff\xfe", strip_volatile=False)
    assert isinstance(result, str)
    assert "\ufffd" in result


def test_bytes_in_nested_structure() -> None:
    normalizer = CanonicalNormalizer()
    data = {"key": [b"data"]}
    result = normalizer.normalize(data, strip_volatile=False)
    assert result == {"key": ["data"]}


def test_bytes_stripped_volatile() -> None:
    normalizer = CanonicalNormalizer()
    data = {"content": b"payload", "timestamp": b"volatile"}
    result = normalizer.strip_volatile(data)
    assert result == {"content": "payload"}


def test_nested_volatile_keys_stripped() -> None:
    normalizer = CanonicalNormalizer()
    data = {
        "outer": {
            "timestamp": "should-be-stripped",
            "run_id": "also-stripped",
            "value": 42,
            "nested": {
                "request_id": "stripped",
                "data": "kept",
            },
        },
        "event_id": "top-level-stripped",
    }
    result = normalizer.strip_volatile(data)
    assert "timestamp" not in result["outer"]
    assert "run_id" not in result["outer"]
    assert result["outer"]["value"] == 42
    assert "request_id" not in result["outer"]["nested"]
    assert result["outer"]["nested"]["data"] == "kept"
    assert "event_id" not in result


def test_volatile_keys_in_list_of_dicts() -> None:
    normalizer = CanonicalNormalizer()
    data = [
        {"name": "a", "timestamp": "ts1"},
        {"name": "b", "created_at": "ca1"},
    ]
    result = normalizer.strip_volatile(data)
    assert result == [{"name": "a"}, {"name": "b"}]


def test_float_precision() -> None:
    normalizer = CanonicalNormalizer(float_precision=3)
    result = normalizer.normalize(3.14159265, strip_volatile=False)
    assert result == 3.142


def test_canonical_dumps_deterministic_with_special_values() -> None:
    data = {"nan": float("nan"), "inf": float("inf"), "neg_inf": float("-inf"), "bytes": b"ok"}
    s1 = canonical_dumps(data)
    s2 = canonical_dumps(data)
    assert s1 == s2


def test_sha256_deterministic_with_nan() -> None:
    data = {"value": float("nan")}
    h1 = sha256_of_data(data)
    h2 = sha256_of_data(data)
    assert h1 == h2
    assert len(h1) == 64


def test_sha256_of_subset_ignores_keys() -> None:
    data = {"a": 1, "b": 2, "c": 3}
    h1 = sha256_of_subset(data, ignored_keys={"b"})
    h2 = sha256_of_subset({"a": 1, "c": 3})
    assert h1 == h2


def test_sha256_of_subset_no_ignored() -> None:
    data = {"a": 1}
    h1 = sha256_of_subset(data)
    h2 = sha256_of_data(data)
    assert h1 == h2


def test_none_and_bool_preserved() -> None:
    normalizer = CanonicalNormalizer()
    assert normalizer.normalize(None, strip_volatile=False) is None
    assert normalizer.normalize(True, strip_volatile=False) is True
    assert normalizer.normalize(False, strip_volatile=False) is False


def test_int_preserved() -> None:
    normalizer = CanonicalNormalizer()
    assert normalizer.normalize(42, strip_volatile=False) == 42


def test_non_json_type_becomes_string() -> None:
    normalizer = CanonicalNormalizer()
    result = normalizer.normalize(set(), strip_volatile=False)
    assert isinstance(result, str)


def test_dict_keys_sorted_in_output() -> None:
    normalizer = CanonicalNormalizer()
    data = {"z": 1, "a": 2, "m": 3}
    s = normalizer.canonical_dumps(data, strip_volatile=False)
    assert s.index('"a"') < s.index('"m"') < s.index('"z"')
