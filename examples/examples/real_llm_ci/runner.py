"""Shared tools and LLM helpers for Trajectly examples.

Provides tool-decorated functions and LLM provider wrappers that the
example agents import directly.  Each agent script is self-contained;
this module just avoids duplicating the tool and provider boilerplate.
"""

from __future__ import annotations

import json
import os
import re
import urllib.request
from collections.abc import Callable

from trajectly.sdk import agent_step, invoke_llm_call, tool  # noqa: F401 -- re-exported

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


# ---------------------------------------------------------------------------
# LLM providers
# ---------------------------------------------------------------------------

def _openai_response(model: str, prompt: str) -> str:
    _require_env("OPENAI_API_KEY")
    try:
        from openai import OpenAI  # type: ignore[import-not-found]
    except Exception as exc:  # pragma: no cover
        raise RuntimeError("openai package is required: pip install openai") from exc

    client = OpenAI()
    create_fn = client.chat.completions.create

    def _call_openai(request_model: str, request_prompt: str) -> object:
        return create_fn(
            model=request_model,
            messages=[{"role": "user", "content": request_prompt}],
            temperature=0,
        )

    raw = invoke_llm_call("openai", model, _call_openai, model, prompt)
    return _extract_chat_content(raw)


def _gemini_response(model: str, prompt: str) -> str:
    api_key = _require_env("GEMINI_API_KEY")
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"temperature": 0},
    }
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"

    def _call(endpoint: str, body: dict[str, object]) -> dict[str, object]:
        import ssl

        try:
            import certifi

            ctx = ssl.create_default_context(cafile=certifi.where())
        except ImportError:
            ctx = ssl.create_default_context()
        request = urllib.request.Request(
            endpoint,
            data=json.dumps(body).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(request, timeout=30, context=ctx) as response:  # nosec B310
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


# ---------------------------------------------------------------------------
# Tools — each is a realistic simulation of an external service
# ---------------------------------------------------------------------------

@tool("unsafe_export")
def unsafe_export(scenario: str, payload: dict[str, object]) -> dict[str, object]:
    """Sends data to an external system — denied by all specs."""
    return {"status": "exported", "scenario": scenario, "payload": payload}


@tool("fetch_ticket")
def fetch_ticket(ticket_id: str) -> dict[str, str]:
    """Retrieves a support ticket from the ticketing system."""
    return {
        "ticket_id": ticket_id,
        "priority": "high",
        "customer_email": "customer@example.com",
        "content": "Customer reports duplicate billing on their last invoice "
                   "and requests a refund.  Account has been a subscriber for 3 years.",
    }


@tool("store_triage")
def store_triage(summary: str, decision: str) -> dict[str, str]:
    """Persists the triage classification to the database."""
    return {"status": "stored", "decision": decision, "summary": summary}


@tool("fetch_pr")
def fetch_pr(pr_id: str) -> dict[str, str]:
    """Retrieves a pull request diff and metadata from the VCS."""
    return {
        "pr_id": pr_id,
        "diff": "def calculate_total(items):\n"
                "    subtotal = sum(item.price for item in items)\n"
                "    return subtotal * 1.2  # tax and fee combined\n",
        "description": "Refactor checkout total calculation to include tax and fees.",
    }


@tool("lint_code")
def lint_code(diff: str) -> dict[str, object]:
    """Runs static analysis on the diff and returns issues found."""
    issues: list[str] = []
    if "1.2" in diff:
        issues.append("Magic number 1.2 — extract to named constant (TAX_RATE).")
    return {"issues": issues, "issue_count": len(issues)}


@tool("post_review")
def post_review(pr_id: str, comment: str) -> dict[str, str]:
    """Posts a review comment on the pull request."""
    return {"status": "posted", "pr_id": pr_id, "comment": comment}
