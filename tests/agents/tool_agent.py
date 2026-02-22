from __future__ import annotations

from trajectly.sdk import agent_step, tool


@tool("multiply")
def multiply(left: int, right: int) -> int:
    return left * right


@tool("format_result")
def format_result(value: int) -> dict[str, int]:
    return {"value": value}


def main() -> None:
    agent_step("start")
    value = multiply(4, 5)
    payload = format_result(value)
    agent_step("complete", payload)


if __name__ == "__main__":
    main()
