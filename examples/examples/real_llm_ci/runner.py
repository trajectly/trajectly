"""Real-provider TRT scenarios for validation (OpenAI/Gemini/LangGraph/LlamaIndex).

Each scenario supports:
- baseline: compliant behavior (expected TRT PASS)
- regression: forbidden tool path (expected TRT FAIL)
"""

from __future__ import annotations

import json
import os
import re
import urllib.request
from collections.abc import Callable
from dataclasses import dataclass
from typing import TypedDict

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


def _langgraph_response(model: str, prompt: str) -> str:
    _require_env("OPENAI_API_KEY")
    try:
        from langchain_openai import ChatOpenAI  # type: ignore[import-not-found]
        from langgraph.graph import END, START, StateGraph  # type: ignore[import-not-found]
    except Exception as exc:  # pragma: no cover - depends on optional dependency
        raise RuntimeError(
            "langgraph and langchain-openai packages are required for REAL_PROVIDER=langgraph",
        ) from exc

    class GraphState(TypedDict):
        prompt: str
        response: str

    llm = ChatOpenAI(model=model, temperature=0)

    def _call_model(state: GraphState) -> GraphState:
        message = llm.invoke(state["prompt"])
        content = getattr(message, "content", "")
        if isinstance(content, list):
            text = " ".join(str(part) for part in content)
        else:
            text = str(content)
        return {"prompt": state["prompt"], "response": text}

    graph = StateGraph(GraphState)
    graph.add_node("call_model", _call_model)
    graph.add_edge(START, "call_model")
    graph.add_edge("call_model", END)
    app = graph.compile()

    raw = invoke_llm_call("langgraph", model, app.invoke, {"prompt": prompt, "response": ""})
    if not isinstance(raw, dict):
        return str(raw)
    return str(raw.get("response", ""))


def _llamaindex_response(model: str, prompt: str) -> str:
    _require_env("OPENAI_API_KEY")
    try:
        from llama_index.llms.openai import OpenAI as LlamaOpenAI  # type: ignore[import-not-found]
    except Exception as exc:  # pragma: no cover - depends on optional dependency
        raise RuntimeError("llama-index-llms-openai package is required for REAL_PROVIDER=llamaindex") from exc

    llm = LlamaOpenAI(model=model, temperature=0)
    raw = invoke_llm_call("llamaindex", model, llm.complete, prompt)
    text = getattr(raw, "text", raw)
    return str(text)


def _provider_handler(provider: str) -> PromptResponder:
    handlers: dict[str, PromptResponder] = {
        "openai": _openai_response,
        "gemini": _gemini_response,
        "langgraph": _langgraph_response,
        "llamaindex": _llamaindex_response,
    }
    if provider not in handlers:
        raise RuntimeError(
            f"Unsupported REAL_PROVIDER={provider}. Expected one of: {', '.join(sorted(handlers))}",
        )
    return handlers[provider]


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


@tool("search_web")
def search_web(query: str) -> list[str]:
    if not query:
        return []
    return [
        "https://docs.example.com/vector-db-a",
        "https://docs.example.com/vector-db-b",
    ]


@tool("extract_content")
def extract_content(url: str) -> dict[str, str]:
    if "vector-db-a" in url:
        return {
            "url": url,
            "title": "Vector DB A",
            "content": "Vector DB A offers strong metadata filters and low-latency retrieval.",
        }
    return {
        "url": url,
        "title": "Vector DB B",
        "content": "Vector DB B offers integrated reranking and lower operational overhead.",
    }


@tool("summarize")
def summarize(text: str) -> str:
    compact = " ".join(text.strip().split())
    return compact[:180]


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


@tool("search_flights")
def search_flights(origin: str, destination: str) -> list[dict[str, object]]:
    return [{"flight_id": "FL-100", "origin": origin, "destination": destination, "price": 199.0}]


@tool("search_hotels")
def search_hotels(city: str) -> list[dict[str, object]]:
    return [{"hotel_id": "HT-200", "city": city, "nightly": 129.0}]


@tool("book_itinerary")
def book_itinerary(flight_id: str, hotel_id: str) -> dict[str, str]:
    return {"status": "booked", "flight_id": flight_id, "hotel_id": hotel_id}


@tool("ingest_doc")
def ingest_doc(doc_id: str, content: str) -> dict[str, object]:
    return {"status": "indexed", "doc_id": doc_id, "content_length": len(content)}


@tool("query_index")
def query_index(query: str) -> list[str]:
    base = [
        "TRT computes a witness index for earliest violation.",
        "TRT includes deterministic repro command in report artifacts.",
        "TRT distinguishes contract and refinement failures.",
    ]
    if "citation" in query.lower():
        base.append("Citations map answers to retrieved chunks.")
    return base


@tool("rerank")
def rerank(candidates: list[str]) -> list[str]:
    return sorted(candidates, key=len)


@tool("format_answer")
def format_answer(answer: str, citations: list[str]) -> dict[str, object]:
    return {"answer": answer, "citations": citations}


@tool("cite_sources")
def cite_sources(chunks: list[str]) -> list[str]:
    return [f"source-{index + 1}" for index, _chunk in enumerate(chunks[:3])]


@tool("classify")
def classify(text: str) -> str:
    if "refund" in text.lower():
        return "refund"
    if "billing" in text.lower():
        return "billing"
    return "general"


@tool("route")
def route(label: str) -> str:
    mapping = {"refund": "finance", "billing": "support", "general": "assistant"}
    return mapping.get(label, "assistant")


@tool("execute_action")
def execute_action(route_name: str, payload: dict[str, str]) -> dict[str, str]:
    return {"status": "executed", "route": route_name, "note": payload.get("note", "")}


@tool("notify")
def notify(channel: str, message: str) -> dict[str, str]:
    return {"status": "sent", "channel": channel, "message": message}


@tool("check_history")
def check_history(customer_id: str) -> dict[str, object]:
    return {"customer_id": customer_id, "open_tickets": 2, "last_intent": "billing"}


@tool("classify_intent")
def classify_intent(message: str) -> str:
    if "escalate" in message.lower() or "manager" in message.lower():
        return "escalation"
    if "charge" in message.lower():
        return "billing"
    return "general"


@tool("escalate")
def escalate(customer_id: str, reason: str) -> dict[str, str]:
    return {"status": "escalated", "customer_id": customer_id, "reason": reason}


@tool("resolve")
def resolve(customer_id: str, resolution: str) -> dict[str, str]:
    return {"status": "resolved", "customer_id": customer_id, "resolution": resolution}


@tool("log_outcome")
def log_outcome(customer_id: str, outcome: str) -> dict[str, str]:
    return {"status": "logged", "customer_id": customer_id, "outcome": outcome}


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


def _web_search_agent(mode: str, responder: PromptResponder, model: str) -> dict[str, object]:
    urls = search_web("best vector database for support copilots")
    sources = [extract_content(url) for url in urls]
    combined = "\n".join(source["content"] for source in sources)
    response = responder(model, f"Synthesize one recommendation from these notes:\n{combined}")
    concise = summarize(response)
    if mode == "regression":
        output = unsafe_export("web_search_agent", {"sources": sources, "summary": concise})
    else:
        output = {"status": "ok", "summary": concise}
    return {"sources_count": len(sources), "output": output}


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


def _travel_planner(mode: str, responder: PromptResponder, model: str) -> dict[str, object]:
    flights = search_flights("SFO", "LAX")
    hotels = search_hotels("Los Angeles")
    response = responder(
        model,
        f"Pick best combo from flights={_stable_json(flights)} hotels={_stable_json(hotels)}",
    )
    if mode == "regression":
        output = unsafe_export("travel_planner", {"flights": flights, "hotels": hotels, "response": response})
    else:
        flight_id = str(flights[0]["flight_id"])
        hotel_id = str(hotels[0]["hotel_id"])
        output = book_itinerary(flight_id, hotel_id)
    return {"output": output}


def _rag_pipeline(mode: str, responder: PromptResponder, model: str) -> dict[str, object]:
    chunks = query_index("How does TRT witness indexing work?")
    ranked = rerank(chunks)
    response = responder(model, "Use these chunks to explain TRT value:\n" + "\n".join(ranked))
    if mode == "regression":
        output = unsafe_export("rag_pipeline", {"chunks": ranked, "response": response})
    else:
        output = format_answer(response, ranked[:2])
    return {"output": output}


def _document_qa(mode: str, responder: PromptResponder, model: str) -> dict[str, object]:
    indexed = ingest_doc("doc-42", "TRT contracts constrain tool and data behavior.")
    chunks = query_index("Provide citation-ready explanation for TRT contracts")
    citations = cite_sources(chunks)
    response = responder(model, "Answer with references:\n" + "\n".join(chunks))
    concise = summarize(response)
    if mode == "regression":
        output = unsafe_export("document_qa", {"indexed": indexed, "citations": citations, "summary": concise})
    else:
        output = format_answer(concise, citations)
    return {"output": output}


def _multi_step_workflow(mode: str, responder: PromptResponder, model: str) -> dict[str, object]:
    label = classify("Customer asks for refund after failed charge")
    route_name = route(label)
    response = responder(model, f"Generate action note for route={route_name} label={label}")
    action = execute_action(route_name, {"note": response})
    if mode == "regression":
        output = unsafe_export("multi_step_workflow", {"label": label, "route": route_name, "action": action})
    else:
        output = notify("ops", f"{route_name}:{action['status']}")
    return {"output": output}


def _support_escalation(mode: str, responder: PromptResponder, model: str) -> dict[str, object]:
    history = check_history("cust-77")
    intent = classify_intent("Please escalate this duplicate charge issue to a manager.")
    response = responder(model, f"Given history={_stable_json(history)} and intent={intent}, propose final action.")
    if mode == "regression":
        output = unsafe_export("support_escalation", {"history": history, "intent": intent, "response": response})
    else:
        escalated = escalate("cust-77", response)
        output = log_outcome("cust-77", escalated["status"])
    return {"output": output}


@dataclass(frozen=True)
class ScenarioConfig:
    key: str
    provider: str
    default_model: str
    run: Callable[[str, PromptResponder, str], dict[str, object]]


SCENARIOS: dict[str, ScenarioConfig] = {
    "ticket_classifier": ScenarioConfig("ticket_classifier", "openai", "gpt-4o-mini", _ticket_classifier),
    "web_search_agent": ScenarioConfig("web_search_agent", "openai", "gpt-4o-mini", _web_search_agent),
    "code_review_bot": ScenarioConfig("code_review_bot", "gemini", "gemini-2.5-flash", _code_review_bot),
    "travel_planner": ScenarioConfig("travel_planner", "gemini", "gemini-2.5-flash", _travel_planner),
    "rag_pipeline": ScenarioConfig("rag_pipeline", "llamaindex", "gpt-4o-mini", _rag_pipeline),
    "document_qa": ScenarioConfig("document_qa", "llamaindex", "gpt-4o-mini", _document_qa),
    "multi_step_workflow": ScenarioConfig("multi_step_workflow", "langgraph", "gpt-4o-mini", _multi_step_workflow),
    "support_escalation": ScenarioConfig("support_escalation", "langgraph", "gpt-4o-mini", _support_escalation),
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
