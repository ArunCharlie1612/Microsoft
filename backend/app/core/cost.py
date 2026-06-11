"""Per-run token + cost metering.

Accumulates GPT-4o token usage for the in-flight run via a context variable holding
the run id, so usage recorded inside child tasks (e.g. ``asyncio.gather`` fan-out)
still attributes to the correct run. Cost is an estimate using configurable per-1K
token rates for the GPT-4o family.
"""

from __future__ import annotations

from contextvars import ContextVar

# Default GPT-4o pricing (USD per 1K tokens). Adjust to your contract.
_INPUT_PER_1K = 0.005
_OUTPUT_PER_1K = 0.015

_current_run: ContextVar[str | None] = ContextVar("breachsim_current_run", default=None)
_usage: dict[str, dict[str, int]] = {}


def begin_run(run_id: str) -> None:
    _current_run.set(run_id)
    _usage.setdefault(run_id, {"prompt": 0, "completion": 0, "total": 0})


def record_usage(prompt_tokens: int, completion_tokens: int) -> None:
    run_id = _current_run.get()
    if run_id is None:
        return
    bucket = _usage.setdefault(run_id, {"prompt": 0, "completion": 0, "total": 0})
    bucket["prompt"] += prompt_tokens
    bucket["completion"] += completion_tokens
    bucket["total"] += prompt_tokens + completion_tokens


def estimate_cost_usd(prompt_tokens: int, completion_tokens: int) -> float:
    return round(
        (prompt_tokens / 1000.0) * _INPUT_PER_1K
        + (completion_tokens / 1000.0) * _OUTPUT_PER_1K,
        4,
    )


def usage_for(run_id: str) -> dict[str, int | float]:
    bucket = _usage.get(run_id, {"prompt": 0, "completion": 0, "total": 0})
    return {
        "promptTokens": bucket["prompt"],
        "completionTokens": bucket["completion"],
        "totalTokens": bucket["total"],
        "estimatedCostUsd": estimate_cost_usd(bucket["prompt"], bucket["completion"]),
    }


def clear(run_id: str) -> None:
    _usage.pop(run_id, None)
