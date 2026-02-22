from __future__ import annotations

from trajectly.redaction import REDACTION_TOKEN, apply_redactions


def test_apply_redactions_nested_structures() -> None:
    payload = {
        "token": "secret_12345",
        "nested": ["safe", {"value": "api_key=abc123"}],
        "number": 5,
    }

    redacted = apply_redactions(payload, [r"secret_[0-9]+", r"api_key=[a-z0-9]+"])

    assert redacted["token"] == REDACTION_TOKEN
    assert redacted["nested"][0] == "safe"
    assert redacted["nested"][1]["value"] == REDACTION_TOKEN
    assert redacted["number"] == 5


def test_apply_redactions_no_patterns_returns_original_object() -> None:
    payload = {"value": "unchanged"}
    assert apply_redactions(payload, []) is payload
