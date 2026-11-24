"""Model factory and a one-line way to run an ADK agent from a notebook cell."""

from __future__ import annotations

import asyncio
import concurrent.futures
import contextlib
import logging
from dataclasses import dataclass, field

from google.adk.models.google_llm import Gemini
from google.adk.runners import InMemoryRunner
from google.genai import types

from labkit import DEFAULT_MODEL
from labkit.setup import get_api_key
from labkit.trace import trace_cards
from labkit import _state
from labkit.ui import SETUP_NOT_PASSED, error_line, has_blank

RETRY = types.HttpRetryOptions(attempts=5, initial_delay=2, exp_base=4,
                               http_status_codes=[429, 500, 503, 504])
QUOTA_MESSAGE = "⏳ Free quota reached — wait one minute and run this cell again."
NOT_BUILT = "Your agent isn't built yet — fix the ❌ lines in the CHECK cell above, run it, then this cell."


@contextlib.contextmanager
def _quiet_adk_logs():
    """ADK logs a full traceback on model errors; hide it so participants see our one-line message."""
    log = logging.getLogger("google_adk")
    old = log.level
    log.setLevel(logging.CRITICAL)
    try:
        yield
    finally:
        log.setLevel(old)


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
    """Send one message to an agent, show what it did as trace cards, return the result.

    Participant mistakes (setup not passed, agent not built, blanks left, quota) never raise:
    they show one red line and return a RunResult whose .message explains what to do.
    """
    from IPython.display import HTML, display

    def stop(note: str) -> RunResult:
        if show:
            display(error_line(note))
        return RunResult("", [], [], note)

    if not _state.get("setup_ok"):
        return stop(SETUP_NOT_PASSED)
    if agent is None:
        return stop(NOT_BUILT)
    instruction = getattr(agent, "instruction", "")
    blank = has_blank(getattr(agent, "name", ""), instruction if isinstance(instruction, str) else "x")
    if blank:
        return stop(blank)
    get_api_key()
    runner = InMemoryRunner(agent=agent, app_name="lab", plugins=plugins)
    handle = display(HTML("<i style='font-family:sans-serif'>⏳ Asking Gemini…</i>"), display_id=True) if show else None
    try:
        with _quiet_adk_logs():
            events = _run_coro(runner.run_debug(message, quiet=True))
    except Exception as exc:
        msg = str(exc).lower()
        if handle:
            handle.update(HTML(""))
        if "429" in msg or "resource_exhausted" in msg or "quota" in msg:
            return stop(QUOTA_MESSAGE)
        raise
    if handle:
        handle.update(HTML(""))
    text, calls = summarize(events)
    if show:
        display(trace_cards(events))
    return RunResult(text, list(events), calls)
