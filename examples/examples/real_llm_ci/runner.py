"""Real-provider TRT scenarios for validation (OpenAI / Gemini).

Scenarios:
- ticket_classifier (OpenAI): simple 2-tool agent
- code_review_bot (Gemini): medium 3-tool agent
"""

from __future__ import annotations

import json
import os
import re
import urllib.request
from collections.abc import Callable
from dataclasses import dataclass

from trajectly.sdk import agent_step, invoke_llm_call, tool

PromptResponder = Callable[[str, str], str]


def _stable_json(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"))


def _extract_chat_content(raw: object) -> str:
    if isinstance(raw, str):
        match = re.search(r"content='((?:\\\\'|[^'])*)'", raw)
        if match:
            return match.group(1).replace("\\n", "\n").replace("\\'", "'")
        return raw

    if isinstance(raw, dict):
        response = raw.get("response")
        if isinstance(response, str):
            return _extract_chat_content(response)
        choices = raw.get("choices")
        if isinstance(choices, list) and choices:
            first = choices[0]
            if isinstance(first, dict):
                message = first.get("message")
                if isinstance(message, dict):
                    content = message.get("content")
                    if isinstance(content, str):
                        return content

    choices = getattr(raw, "choices", None)
    if choices:
        first = choices[0]
        message = getattr(first, "message", None)
        content = getattr(message, "content", None)
        if isinstance(content, str):
            return content
    return str(raw)


def _require_env(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise RuntimeError(f"Missing required environment variable: {name}")
    return value


def _openai_response(model: str, prompt: str) -> str:
    _require_env("OPENAI_API_KEY")
    try:
        from openai import OpenAI  # type: ignore[import-not-found]
    except Exception as exc:  # pragma: no cover - depends on optional dependency
        raise RuntimeError("openai package is required for REAL_PROVIDER=openai") from exc

    client = OpenAI()
    create_fn = client.chat.completions.create

    def _call_openai(request_model: str, request_prompt: str) -> object:
        return create_fn(
            model=request_model,
            messages=[{"role": "user", "content": request_prompt}],
            temperature=0,
        )

    raw = invoke_llm_call(
        "openai",
        model,
        _call_openai,
        model,
        prompt,
    )
    return _extract_chat_content(raw)


def _gemini_response(model: str, prompt: str) -> str:
    api_key = _require_env("GEMINI_API_KEY")
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"temperature": 0},
    }
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"

    def _call(endpoint: str, body: dict[str, object]) -> dict[str, object]:
        request = urllib.request.Request(
            endpoint,
            data=json.dumps(body).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(request, timeout=30) as response:  # nosec B310
            return json.loads(response.read().decode("utf-8"))

    raw = invoke_llm_call("gemini", model, _call, url, payload)
    if not isinstance(raw, dict):
        raise RuntimeError("Gemini returned invalid payload")
    candidates = raw.get("candidates", [])
    if not isinstance(candidates, list) or not candidates:
        raise RuntimeError("Gemini returned no candidates")
    first = candidates[0] if isinstance(candidates[0], dict) else {}
    content = first.get("content", {}) if isinstance(first, dict) else {}
    parts = content.get("parts", []) if isinstance(content, dict) else []
    if not isinstance(parts, list) or not parts:
        raise RuntimeError("Gemini returned no text parts")
    first_part = parts[0] if isinstance(parts[0], dict) else {}
    return str(first_part.get("text", ""))


def _provider_handler(provider: str) -> PromptResponder:
    handlers: dict[str, PromptResponder] = {
        "openai": _openai_response,
        "gemini": _gemini_response,
    }
    if provider not in handlers:
        raise RuntimeError(
            f"Unsupported REAL_PROVIDER={provider}. Expected one of: {', '.join(sorted(handlers))}",
        )
    return handlers[provider]


# ---------------------------------------------------------------------------
# Tools
# ---------------------------------------------------------------------------

@tool("unsafe_export")
def unsafe_export(scenario: str, payload: dict[str, object]) -> dict[str, object]:
    return {"status": "exported", "scenario": scenario, "payload": payload}


@tool("fetch_ticket")
def fetch_ticket(ticket_id: str) -> dict[str, str]:
    return {
        "ticket_id": ticket_id,
        "priority": "high",
        "customer_email": "customer@example.com",
        "content": "Customer reports duplicate billing and asks for a concise action plan.",
    }


@tool("store_triage")
def store_triage(summary: str, decision: str) -> dict[str, str]:
    return {"status": "stored", "decision": decision, "summary": summary}


@tool("fetch_pr")
def fetch_pr(pr_id: str) -> dict[str, str]:
    return {
        "pr_id": pr_id,
        "diff": "def pay(amount): return amount*1.2 # tax and fee mixed",
        "description": "Refactor payments calculation and response formatting.",
    }


@tool("lint_code")
def lint_code(diff: str) -> dict[str, object]:
    issues: list[str] = []
    if "1.2" in diff:
        issues.append("Magic number detected in billing path.")
    return {"issues": issues, "issue_count": len(issues)}


@tool("post_review")
def post_review(pr_id: str, comment: str) -> dict[str, str]:
    return {"status": "posted", "pr_id": pr_id, "comment": comment}


# ---------------------------------------------------------------------------
# Scenarios
# ---------------------------------------------------------------------------

def _ticket_classifier(mode: str, responder: PromptResponder, model: str) -> dict[str, object]:
    ticket = fetch_ticket("ticket-1729")
    prompt = (
        "Classify this support ticket into one of [refund, billing, account]. "
        "Then provide one short response line.\n\n"
        f"Ticket: {ticket['content']}"
    )
    response = responder(model, prompt)
    if mode == "regression":
        output = unsafe_export("ticket_classifier", {"ticket": ticket, "response": response})
    else:
        output = store_triage(response, "billing")
    return {"ticket_id": ticket["ticket_id"], "output": output}


def _code_review_bot(mode: str, responder: PromptResponder, model: str) -> dict[str, object]:
    pr = fetch_pr("PR-2026")
    lint = lint_code(pr["diff"])
    response = responder(
        model,
        f"Review this diff and lint summary. diff={pr['diff']} lint={_stable_json(lint)}",
    )
    if mode == "regression":
        output = unsafe_export("code_review_bot", {"pr": pr, "lint": lint, "response": response})
    else:
        output = post_review(pr["pr_id"], response)
    return {"pr_id": pr["pr_id"], "output": output}


# ---------------------------------------------------------------------------
# Registry & entrypoint
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class ScenarioConfig:
    key: str
    provider: str
    default_model: str
    run: Callable[[str, PromptResponder, str], dict[str, object]]


SCENARIOS: dict[str, ScenarioConfig] = {
    "ticket_classifier": ScenarioConfig("ticket_classifier", "openai", "gpt-4o-mini", _ticket_classifier),
    "code_review_bot": ScenarioConfig("code_review_bot", "gemini", "gemini-2.5-flash", _code_review_bot),
}


def run_example(scenario: str, provider: str, mode: str, model: str) -> None:
    if mode not in {"baseline", "regression"}:
        raise RuntimeError("REAL_MODE must be 'baseline' or 'regression'")
    config = SCENARIOS.get(scenario)
    if config is None:
        raise RuntimeError(f"Unsupported REAL_SCENARIO={scenario}. Expected one of: {', '.join(sorted(SCENARIOS))}")
    responder = _provider_handler(provider)

    agent_step(
        "start",
        {"scenario": scenario, "provider": provider, "mode": mode, "model": model},
    )
    output = config.run(mode, responder, model)
    agent_step(
        "done",
        {"scenario": scenario, "provider": provider, "mode": mode, "model": model, "output": output},
    )


def main() -> None:
    scenario = os.getenv("REAL_SCENARIO", "ticket_classifier").strip().lower()
    config = SCENARIOS.get(scenario)
    if config is None:
        raise RuntimeError(f"Unsupported REAL_SCENARIO={scenario}. Expected one of: {', '.join(sorted(SCENARIOS))}")
    provider = os.getenv("REAL_PROVIDER", config.provider).strip().lower()
    mode = os.getenv("REAL_MODE", "baseline").strip().lower()
    model = os.getenv("REAL_MODEL", config.default_model).strip()
    run_example(scenario=scenario, provider=provider, mode=mode, model=model)


if __name__ == "__main__":
    main()
