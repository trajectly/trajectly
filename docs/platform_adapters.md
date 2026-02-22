# Platform Adapter Support

Trajectly uses adapter instrumentation (not runtime interception) for deterministic behavior.

## Current Adapter Helpers

Provided under `trajectly.sdk`:

- `openai_chat_completion(...)`
- `anthropic_messages_create(...)`
- `langchain_invoke(...)`
- `invoke_tool_call(...)`
- `invoke_llm_call(...)`

## Why This Approach

- Deterministic and explicit event emission.
- Stable replay behavior across local and CI runs.
- Avoids brittle monkeypatching of provider/framework internals.

## Integration Patterns

### OpenAI-style

Use clients exposing `client.chat.completions.create(...)`:

```python
from trajectly.sdk import openai_chat_completion

result = openai_chat_completion(
    client,
    model="gpt-4o-mini",
    messages=[{"role": "user", "content": "hello"}],
)
```

### Anthropic-style

Use clients exposing `client.messages.create(...)`:

```python
from trajectly.sdk import anthropic_messages_create

result = anthropic_messages_create(
    client,
    model="claude-3-5-haiku",
    messages=[{"role": "user", "content": "hello"}],
)
```

### LangChain-style

Use runnables exposing `.invoke(...)`:

```python
from trajectly.sdk import langchain_invoke

result = langchain_invoke(
    runnable,
    {"question": "what is trajectly"},
    model="langchain-fake-model",
    provider="langchain",
)
```

## Validation Expectations

- Each adapter flow must support record -> replay with no live network.
- Replay strict mode must fail on unexpected calls.
- Adapter examples must be covered in `trajectly-examples` CI.

## Roadmap

- Add dedicated wrappers and examples for LlamaIndex, CrewAI, AutoGen, and DSPy.
- Add adapter compatibility matrix with pinned framework version ranges.
