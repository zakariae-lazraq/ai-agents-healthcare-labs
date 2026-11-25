"""Tests for the final-review findings (Lab 0 foundation)."""
import logging

import labkit
from labkit import agents, setup, ui


class _Models:
    def __init__(self, exc):
        self.exc = exc

    def generate_content(self, model, contents):
        raise self.exc


class _Client:
    def __init__(self, exc):
        self.models = _Models(exc)


def _works(monkeypatch, exc):
    monkeypatch.setenv("GOOGLE_API_KEY", "k")
    monkeypatch.setattr(setup, "_make_client", lambda k: _Client(exc))
    return {r.name: r for r in setup.check_environment(ping_pubmed=False)}["API key works"]


# Important 1 — ADK tracebacks must not bury the friendly quota message
def test_run_quota_does_not_emit_adk_error_logs(monkeypatch, caplog):
    labkit._state["setup_ok"] = True

    async def boom(self, *a, **k):
        logging.getLogger("google_adk.google.adk.workflow._node_runner").exception("Node execution failed")
        raise Exception("429 RESOURCE_EXHAUSTED")

    monkeypatch.setattr("google.adk.runners.InMemoryRunner.run_debug", boom)
    from google.adk.agents import Agent
    a = Agent(name="t", model=agents.make_model(), instruction="hi")
    with caplog.at_level(logging.DEBUG):
        res = agents.run(a, "hello", show=False)
    assert "Free quota reached" in res.message
    assert not [r for r in caplog.records if r.name.startswith("google_adk") and r.levelno >= logging.ERROR]
    assert logging.getLogger("google_adk").level != logging.CRITICAL  # restored afterwards


# Important 2 — agent not built (None) → friendly message, no exception
def test_run_with_no_agent_gives_message():
    labkit._state["setup_ok"] = True
    res = agents.run(None, "hello", show=False)
    assert res.text == "" and "is not built yet" in res.message


def test_run_with_blank_gives_message_not_exception():
    from google.adk.agents import Agent
    labkit._state["setup_ok"] = True
    a = Agent(name="helper", model=agents.make_model(), instruction="Use ___ please")
    res = agents.run(a, "hello", show=False)
    assert "___" in res.message


# Important 3 — setup guard wording
def test_setup_not_passed_message():
    labkit._state["setup_ok"] = False
    res = agents.run(None, "hello", show=False)
    assert "Setup has not passed yet" in res.message and "Setup cell" in res.message


# Important 6 — real-world model errors get the right fix
def test_model_not_found_fix(monkeypatch):
    r = _works(monkeypatch, Exception("404 NOT_FOUND. models/gemini-x is not found for API version v1beta"))
    assert "trainer" in r.fix and "Wait" not in r.fix


def test_location_not_supported_fix(monkeypatch):
    r = _works(monkeypatch, Exception("400 FAILED_PRECONDITION. User location is not supported for the API use."))
    assert "trainer" in r.fix and "Create a new key" not in r.fix


def test_zero_free_quota_fix(monkeypatch):
    r = _works(monkeypatch, Exception("429 RESOURCE_EXHAUSTED. Quota exceeded ... limit: 0, model: gemini-x"))
    assert "trainer" in r.fix and "Wait one minute" not in r.fix


# Re-graded minors that confuse participants
def test_optional_check_footer():
    html = ui.check_html([(False, "Canvas", "Tell the trainer")], optional=True)
    assert "Fix the red lines" not in html and "optional" in html.lower()


def test_key_source_label_env(monkeypatch):
    monkeypatch.setenv("GOOGLE_API_KEY", "k")
    monkeypatch.setattr(setup, "_make_client", lambda k: type("C", (), {"models": type("M", (), {"generate_content": lambda self, model, contents: None})()})())
    r = {x.name: x for x in setup.check_environment(ping_pubmed=False)}["API key found"]
    assert "Secrets" not in r.detail


# Live-run finding — a temporary genai client is closed (garbage-collected) before the request runs
def test_ping_keeps_client_alive(monkeypatch):
    class Models:
        closed = False

        def generate_content(self, model, contents):
            if self.closed:
                raise RuntimeError("Cannot send a request, as the client has been closed.")
            return None

    class ClosingClient:
        def __init__(self):
            self.models = Models()

        def __del__(self):
            self.models.closed = True

    monkeypatch.setenv("GOOGLE_API_KEY", "k")
    monkeypatch.setattr(setup, "_make_client", lambda k: ClosingClient())
    r = {x.name: x for x in setup.check_environment(ping_pubmed=False)}["API key works"]
    assert r.ok, r.detail


# Live-run finding — each run used a new event loop, so ADK/genai clients cached per loop were
# cleaned up in a closed loop ("Event loop is closed" noise). One persistent loop fixes it.
def test_runs_share_one_persistent_loop():
    import asyncio

    async def which_loop():
        return asyncio.get_running_loop()

    first = agents._run_coro(which_loop())
    second = agents._run_coro(which_loop())
    assert first is second and not first.is_closed()


def test_run_coro_works_inside_running_loop():
    import asyncio

    async def outer():
        async def inner():
            return 42
        return agents._run_coro(inner())

    assert asyncio.run(outer()) == 42


# Live finding — Google 503 "high demand": switch to a backup model instead of waiting minutes
def test_run_falls_back_when_model_busy(monkeypatch):
    labkit._state["setup_ok"] = True
    used = []

    async def fake_run_debug(self, message, **k):
        model = self.agent.model.model if hasattr(self, "agent") else self._agent.model.model
        used.append(model)
        if model == agents.DEFAULT_MODEL:
            raise Exception("503 UNAVAILABLE. This model is currently experiencing high demand.")
        from google.adk.events import Event
        from google.genai import types
        return [Event(author="a", content=types.Content(role="model", parts=[types.Part(text="ok from backup")]))]

    monkeypatch.setattr("google.adk.runners.InMemoryRunner.run_debug", fake_run_debug)
    from google.adk.agents import Agent
    a = Agent(name="t", model=agents.make_model(), instruction="hi")
    res = agents.run(a, "hello", show=False)
    assert res.text == "ok from backup"
    assert used[0] == agents.DEFAULT_MODEL and used[1] in agents.BACKUP_MODELS
    assert "backup" in res.note.lower()


def test_busy_model_setup_message(monkeypatch):
    r = _works(monkeypatch, Exception("503 UNAVAILABLE. This model is currently experiencing high demand."))
    assert "busy" in r.fix.lower() and "trainer" not in r.fix.lower()


def test_transient_server_errors_count_as_busy():
    for text in ("500 INTERNAL. An internal error has occurred.", "504 DEADLINE_EXCEEDED", "503 UNAVAILABLE"):
        assert agents._error_kind(Exception(text)) == "busy"
    assert agents._error_kind(Exception("400 INVALID_ARGUMENT bad request")) == "other"


def test_setup_ping_client_has_retries(monkeypatch):
    seen = {}
    import google.genai as genai_mod

    class FakeClient:
        def __init__(self, api_key=None, http_options=None):
            seen["http_options"] = http_options

    monkeypatch.setattr(genai_mod, "Client", FakeClient)
    setup._make_client("k")
    assert seen["http_options"] is not None and seen["http_options"].retry_options is not None


def test_network_hiccups_count_as_busy():
    for text in ("ReadTimeout: timed out", "Server disconnected without sending a response.",
                 "RemoteProtocolError: peer closed connection", "ConnectError: connection reset"):
        assert agents._error_kind(Exception(text)) == "busy", text


# ---- live-run findings (2026-11-25): per-minute quota must not block participants
def test_setup_treats_rate_limited_key_as_working(monkeypatch):
    from labkit import setup

    class FakeModels:
        def generate_content(self, **kw):
            raise RuntimeError("429 RESOURCE_EXHAUSTED. Quota exceeded for metric generate_content_free_tier_requests "
                               "GenerateRequestsPerMinutePerProjectPerModel-FreeTier. Please retry in 21.4s.")

    monkeypatch.setattr(setup, "get_api_key", lambda: "k")
    monkeypatch.setattr(setup, "_make_client", lambda key: type("C", (), {"models": FakeModels()})())
    res = {r.name: r for r in setup.check_environment(ping_pubmed=False)}
    assert res["API key works"].ok is True and "wait" in res["API key works"].detail.lower()


def test_arun_waits_and_retries_on_per_minute_quota(monkeypatch):
    import asyncio
    from types import SimpleNamespace
    from labkit import agents
    labkit._state["setup_ok"] = True
    calls, waits = [], []

    class FakeRunner:
        def __init__(self, agent, app_name, plugins=None):
            self.agent = agent

        async def run_debug(self, message, quiet=True):
            calls.append(1)
            if len(calls) == 1:
                raise RuntimeError("429 RESOURCE_EXHAUSTED. PerMinute quota. Please retry in 12.5s.")
            return []

    async def fake_sleep(s):
        waits.append(s)

    monkeypatch.setattr(agents, "InMemoryRunner", FakeRunner)
    monkeypatch.setattr(agents, "_sleep", fake_sleep)
    monkeypatch.setattr(agents, "get_api_key", lambda: "k")
    agent = SimpleNamespace(name="a", instruction="x", model=SimpleNamespace(model="m"))
    r = asyncio.run(agents.arun(agent, "q"))
    assert r.message == "" and len(calls) == 2 and 12 <= waits[0] <= 15 and r.note == ""
