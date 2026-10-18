"""Token accounting for a turn.

Providers report what each request cost; this module normalises the shapes
(LiteLLM's OpenAI-style `usage`, Anthropic's cache fields, the Claude agent
runtime's `ResultMessage.usage`), keeps a running total on the Run, streams a
`usage` event so clients can show it live, and leaves a one-line notice in
the chat when the turn ends. Nothing here changes what is sent to the model.
"""
from __future__ import annotations

import logging
from typing import Any, Optional

log = logging.getLogger(__name__)

FIELDS = ("input", "output", "cache_read", "cache_write")


def normalise(usage: Any) -> dict[str, int]:
    """{input, output, cache_read, cache_write} from any provider's usage object.

    `input` is the total prompt size including the cached part, so the cached
    share is cache_read / input.
    """
    get = (lambda k: getattr(usage, k, None)) if not isinstance(usage, dict) else usage.get
    details = get("prompt_tokens_details")
    cached_openai = 0
    if details is not None:
        cached_openai = (details.get("cached_tokens") if isinstance(details, dict)
                         else getattr(details, "cached_tokens", None)) or 0
    cache_read = get("cache_read_input_tokens") or cached_openai or 0
    cache_write = get("cache_creation_input_tokens") or 0
    prompt = get("prompt_tokens")
    if prompt is None:
        # Anthropic reports uncached input separately from the cache fields.
        prompt = (get("input_tokens") or 0) + cache_read + cache_write
    return {"input": int(prompt or 0), "output": int(get("completion_tokens") or get("output_tokens") or 0),
            "cache_read": int(cache_read), "cache_write": int(cache_write)}


def record(run, usage: Any, *, model: str, cost: Optional[float] = None, steps: int = 1) -> dict:
    """Add one request's (or one runtime turn's) usage to the Run and stream it."""
    step = normalise(usage)
    totals = run.usage
    for key in FIELDS:
        totals[key] += step[key]
    totals["steps"] += steps
    if cost is not None:
        totals["cost_usd"] = round((totals.get("cost_usd") or 0.0) + float(cost), 6)
    totals["model"] = model
    run.emit("usage", {"step": step, "total": dict(totals)})
    return step


def summary(totals: dict) -> str:
    """'Tokens this turn: 412k in (388k cached), 9k out, 37 steps, ~$0.84'."""
    def k(n: int) -> str:
        return f"{n / 1000:.0f}k" if n >= 10_000 else f"{n / 1000:.1f}k" if n >= 1000 else str(n)
    cached = f" ({k(totals['cache_read'])} cached)" if totals.get("cache_read") else ""
    text = f"Tokens this turn: {k(totals['input'])} in{cached}, {k(totals['output'])} out, {totals['steps']} step(s)"
    if totals.get("cost_usd"):
        text += f", ~${totals['cost_usd']:.2f}"
    return text


def new_totals() -> dict:
    return {"input": 0, "output": 0, "cache_read": 0, "cache_write": 0, "steps": 0, "cost_usd": None, "model": "",
            # Where the context comes from, in characters (about 4 per token), and
            # the prompt size of each model request in order.
            "makeup": {"system_prompt": 0, "history": 0, "tool_calls": 0, "tool_results": 0, "narration": 0},
            "per_step_input": []}


def add_makeup(run, part: str, text) -> None:
    """Count characters that enter the conversation, by origin."""
    if text:
        run.usage["makeup"][part] += len(text if isinstance(text, str) else str(text))


def step_input(run, usage: Any) -> None:
    """Record one model request's prompt size, for the growth curve only
    (totals come from `record`)."""
    run.usage["per_step_input"].append(normalise(usage)["input"])


def makeup_summary(totals: dict) -> str:
    m = totals.get("makeup") or {}
    tok = lambda chars: f"{chars / 4000:.0f}k" if chars >= 4000 else f"{chars / 4:.0f}"  # noqa: E731
    parts = [f"system prompt {tok(m.get('system_prompt', 0))}", f"earlier turns {tok(m.get('history', 0))}",
             f"agent's tool calls {tok(m.get('tool_calls', 0))}",
             f"tool results {tok(m.get('tool_results', 0))}", f"narration {tok(m.get('narration', 0))}"]
    text = "Context added this turn (approx. tokens): " + ", ".join(parts)
    steps = totals.get("per_step_input") or []
    if steps:
        k = lambda n: f"{n / 1000:.0f}k"  # noqa: E731
        mid = steps[len(steps) // 2]
        text += f". Prompt per step: first {k(steps[0])}, middle {k(mid)}, last {k(steps[-1])} ({len(steps)} requests)"
    return text
