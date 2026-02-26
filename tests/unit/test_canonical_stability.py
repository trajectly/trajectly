"""Canonical serialization stability: sorted keys, consistent output across invocations."""
from __future__ import annotations

from trajectly.core.canonical import canonical_dumps, sha256_of_data


class TestCanonicalStability:
    def test_key_order_is_sorted(self) -> None:
        payload = {"z": 1, "a": 2, "m": 3}
        output = canonical_dumps(payload)
        assert output.index('"a"') < output.index('"m"') < output.index('"z"')

    def test_nested_key_order_is_sorted(self) -> None:
        payload = {"outer": {"z_inner": 1, "a_inner": 2}}
        output = canonical_dumps(payload)
        assert output.index('"a_inner"') < output.index('"z_inner"')

    def test_identical_output_for_equivalent_dicts(self) -> None:
        d1 = {"b": [1, {"y": 2, "x": 1}], "a": "hello"}
        d2 = {"a": "hello", "b": [1, {"x": 1, "y": 2}]}
        assert canonical_dumps(d1) == canonical_dumps(d2)

    def test_hash_stability_across_calls(self) -> None:
        payload = {"event": "tool_called", "tool": "search", "args": {"q": "test"}}
        hashes = [sha256_of_data(payload) for _ in range(20)]
        assert len(set(hashes)) == 1

    def test_no_whitespace_variance(self) -> None:
        payload = {"a": 1, "b": 2}
        r1 = canonical_dumps(payload)
        r2 = canonical_dumps(payload)
        assert r1 == r2
        assert " " not in r1

    def test_list_order_preserved(self) -> None:
        payload = {"items": [3, 1, 2]}
        output = canonical_dumps(payload)
        assert '"items":[3,1,2]' in output

    def test_unicode_handling(self) -> None:
        payload = {"name": "trajectly \u2014 test"}
        output = canonical_dumps(payload)
        assert "\u2014" in output or "\\u2014" in output
        h1 = sha256_of_data(payload)
        h2 = sha256_of_data(payload)
        assert h1 == h2
