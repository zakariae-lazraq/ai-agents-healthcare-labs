"""Model factory and a one-line way to run an ADK agent from a notebook cell."""

from __future__ import annotations

import asyncio
import threading
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

# Short retries: if Gemini stays busy, switching to a backup model is faster than waiting.
RETRY = types.HttpRetryOptions(attempts=3, initial_delay=1, exp_base=3,
                               http_status_codes=[500, 503, 504])   # 429 is handled by arun (waits for the per-minute window)
# Tried in order when the agent's model is busy (503 high demand) or out of free quota (429).
# Flash-Lite first: the free tier allows only ~20 requests per day for Flash models (seen 2026-11-25).
BACKUP_MODELS = ["gemini-flash-lite-latest"]   # not Flash: its free tier allows only ~20 requests per day
QUOTA_MESSAGE = "Free quota reached: wait one minute and run this cell again."
# Course rule (outline 3.1): temperature 0 for reproducible answers. Pass as generate_content_config=DETERMINISTIC.
DETERMINISTIC = types.GenerateContentConfig(temperature=0)
BUSY_MESSAGE = "Gemini is very busy right now (a Google-side spike, not your fault). Wait 30 seconds and run this cell again."
NOT_BUILT = "Your agent is not built yet: fix the red lines in the CHECK cell above, run it, then this cell."


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
    message: str = ""   # set when the run stopped (setup, blanks, quota…): what the participant must do
    note: str = ""      # informational, e.g. a backup model answered


def summarize(events) -> tuple[str, list[str]]:
    """Final answer text (last model text) and the names of tools called, in order."""
    text, calls = "", []
    for ev in events:
        content = getattr(ev, "content", None)
        buf = []
        for part in (getattr(content, "parts", None) or []):
            if getattr(part, "function_call", None):
                calls.append(part.function_call.name)
            elif getattr(part, "text", None) and not getattr(part, "thought", False) \
                    and getattr(content, "role", "model") == "model":
                buf.append(part.text)   # Gemini may split one answer across parts: join them
        if "".join(buf).strip():
            text = "".join(buf).strip()
    return text, calls


_LOOP: asyncio.AbstractEventLoop | None = None


def _background_loop() -> asyncio.AbstractEventLoop:
    """One event loop, alive for the whole session, in a daemon thread.

    ADK/genai cache their HTTP clients per event loop; reusing one loop keeps them valid
    (a new loop per run left clients to be cleaned up in a closed loop → noisy errors).
    It also works the same inside Colab/Jupyter (which already run a loop) and in scripts.
    """
    global _LOOP
    if _LOOP is None or _LOOP.is_closed():
        _LOOP = asyncio.new_event_loop()
        threading.Thread(target=_LOOP.run_forever, name="labkit-loop", daemon=True).start()
    return _LOOP


def _run_coro(coro):
    """Run a coroutine on the session's background loop and wait for its result."""
    return asyncio.run_coroutine_threadsafe(coro, _background_loop()).result()


def _precheck(agent) -> str:
    """'' if the agent can run, else the participant-facing reason."""
    if not _state.get("setup_ok"):
        return SETUP_NOT_PASSED
    if agent is None:
        return NOT_BUILT
    instruction = getattr(agent, "instruction", "")
    return has_blank(getattr(agent, "name", ""), instruction if isinstance(instruction, str) else "x") or ""


async def arun(agent, message: str, plugins: list | None = None) -> RunResult:
    """Async core of run(): no display. Tries the agent's model, then the backup models if Gemini is busy."""
    problem = _precheck(agent)
    if problem:
        return RunResult("", [], [], problem)
    get_api_key()
    primary = getattr(getattr(agent, "model", None), "model", None)
    candidates = [None] + [m for m in BACKUP_MODELS if m != primary]   # None = the agent as built
    last_kind = ""
    for backup in candidates:
        current = agent if backup is None else agent.model_copy(update={"model": make_model(backup)})
        events = None
        for _attempt in range(3):   # per-minute quota: wait the delay Google gives, then retry the same model
            runner = InMemoryRunner(agent=current, app_name="lab", plugins=plugins)
            try:
                events = await runner.run_debug(message, quiet=True)
                break
            except Exception as exc:
                kind = _error_kind(exc)
                if kind not in ("busy", "quota"):
                    raise
                last_kind = kind
                delay = _retry_delay(exc)
                if kind == "quota" and delay is not None and delay <= MAX_QUOTA_WAIT and _attempt < 2:
                    await _sleep(delay + 1)
                    continue
                break
        if events is None:
            continue
        text, calls = summarize(events)
        note = f"The model {primary} was busy, so this answer comes from the backup model {backup}." if backup else ""
        return RunResult(text, list(events), calls, note=note)
    return RunResult("", [], [], QUOTA_MESSAGE if last_kind == "quota" else BUSY_MESSAGE)


def run(agent, message: str, *, plugins: list | None = None, show: bool = True) -> RunResult:
    """Send one message to an agent, show what it did as trace cards, return the result.

    Participant mistakes (setup not passed, agent not built, blanks left, quota) never raise:
    they show one red line and return a RunResult whose .message explains what to do.
    """
    from IPython.display import HTML, display

    problem = _precheck(agent)
    if problem:
        if show:
            display(error_line(problem))
        return RunResult("", [], [], problem)
    handle = display(HTML("<i style='font-family:sans-serif;color:#5F6B7A'>Asking Gemini…</i>"), display_id=True) if show else None
    try:
        with _quiet_adk_logs():
            result = _run_coro(arun(agent, message, plugins))
    except Exception as exc:   # unexpected model/tool error: one clear line instead of a traceback
        result = RunResult("", [], [], f"Gemini returned an error: {str(exc)[:200]}. Run the cell again; "
                                       "if it repeats, tell the trainer.")
    finally:
        if handle:
            handle.update(HTML(""))
    if show:
        if result.message:
            display(error_line(result.message))
        else:
            if result.note:
                display(HTML(f"<div style='font-family:sans-serif;font-size:13px;color:#5F6B7A'>Note: {result.note}</div>"))
            display(trace_cards(result.events))
    return result


MAX_QUOTA_WAIT = 65   # seconds: per-minute limits reset within a minute; per-day limits do not


async def _sleep(seconds: float) -> None:
    await asyncio.sleep(seconds)


def _retry_delay(exc: Exception) -> float | None:
    """Seconds Google asks us to wait ('retry in 21.4s' / retryDelay '21s'); None if not given."""
    import re
    m = re.search(r"retry in ([\d.]+)\s*s", str(exc), re.I) or re.search(r"retryDelay['\"]?\s*[:=]\s*['\"]?([\d.]+)s",
                                                                          str(exc))
    return float(m.group(1)) if m else None


def _error_kind(exc: Exception) -> str:
    msg = str(exc).lower()
    if "429" in msg or "resource_exhausted" in msg or "quota" in msg:
        return "quota"
    if any(s in msg for s in ("503", "unavailable", "high demand", "overloaded",
                              "500", "internal", "504", "deadline_exceeded",
                              "timeout", "timed out", "disconnected", "connection", "remoteprotocol")):
        return "busy"   # transient Google-side errors: try the backup model
    return "other"
