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
    assert res.text == "" and "isn't built yet" in res.message


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
    assert "Setup hasn't passed yet" in res.message and "▶ Setup" in res.message


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
    assert "Fix the ❌ lines" not in html and "optional" in html.lower()


def test_key_source_label_env(monkeypatch):
    monkeypatch.setenv("GOOGLE_API_KEY", "k")
    monkeypatch.setattr(setup, "_make_client", lambda k: type("C", (), {"models": type("M", (), {"generate_content": lambda self, model, contents: None})()})())
    r = {x.name: x for x in setup.check_environment(ping_pubmed=False)}["API key found"]
    assert "Secrets" not in r.detail
