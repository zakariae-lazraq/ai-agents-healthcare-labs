"""Model factory and a one-line way to run an ADK agent from a notebook cell."""

from __future__ import annotations

import asyncio
import concurrent.futures
from dataclasses import dataclass, field

from google.adk.models.google_llm import Gemini
from google.adk.runners import InMemoryRunner
from google.genai import types

from labkit import DEFAULT_MODEL
from labkit.setup import get_api_key
from labkit.trace import trace_cards

RETRY = types.HttpRetryOptions(attempts=5, initial_delay=2, exp_base=4,
                               http_status_codes=[429, 500, 503, 504])
QUOTA_MESSAGE = "⏳ Free quota reached — wait one minute and run this cell again."


def make_model(name: str = DEFAULT_MODEL) -> Gemini:
    """The Gemini model used by every agent in the course, with automatic retries."""
    return Gemini(model=name, retry_options=RETRY)


@dataclass
class RunResult:
    text: str
    events: list = field(default_factory=list)
    tool_calls: list[str] = field(default_factory=list)
    message: str = ""


def summarize(events) -> tuple[str, list[str]]:
    """Final answer text (last model text) and the names of tools called, in order."""
    text, calls = "", []
    for ev in events:
        content = getattr(ev, "content", None)
        for part in (getattr(content, "parts", None) or []):
            if getattr(part, "function_call", None):
                calls.append(part.function_call.name)
            elif getattr(part, "text", None) and not getattr(part, "thought", False) \
                    and getattr(content, "role", "model") == "model":
                text = part.text.strip()
    return text, calls


def _run_coro(coro):
    """Run a coroutine whether or not an event loop is already running (Colab/Jupyter)."""
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(coro)
    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
        return pool.submit(asyncio.run, coro).result()


def run(agent, message: str, *, plugins: list | None = None, show: bool = True) -> RunResult:
    """Send one message to an agent, show what it did as trace cards, return the result."""
    get_api_key()
    runner = InMemoryRunner(agent=agent, app_name="lab", plugins=plugins)
    try:
        events = _run_coro(runner.run_debug(message, quiet=True))
    except Exception as exc:
        msg = str(exc).lower()
        if "429" in msg or "resource_exhausted" in msg or "quota" in msg:
            if show:
                from IPython.display import HTML, display
                display(HTML(f"<b style='font-family:sans-serif'>{QUOTA_MESSAGE}</b>"))
            return RunResult("", [], [], QUOTA_MESSAGE)
        raise
    text, calls = summarize(events)
    if show:
        from IPython.display import display
        display(trace_cards(events))
    return RunResult(text, list(events), calls)
