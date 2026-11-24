import pytest

import labkit
from labkit import agents


def test_make_model_defaults():
    m = agents.make_model()
    assert m.model == "gemini-3.5-flash-lite"
    assert m.retry_options.attempts == 3
    assert 429 in m.retry_options.http_status_codes


def test_final_text_and_tool_calls_from_events():
    from tests.test_trace import sample_events
    text, calls = agents.summarize(sample_events())
    assert text == "On day 2 we cover compliance."
    assert calls == ["get_course_day"]


def test_run_shows_quota_message_instead_of_crashing(monkeypatch, capsys):
    labkit._state["setup_ok"] = True

    async def boom(self, *a, **k):
        raise Exception("429 RESOURCE_EXHAUSTED quota")

    monkeypatch.setattr("google.adk.runners.InMemoryRunner.run_debug", boom)
    from google.adk.agents import Agent
    a = Agent(name="t", model=agents.make_model(), instruction="hi")
    res = agents.run(a, "hello", show=False)
    assert res.text == ""
    assert "Free quota reached" in res.message


def get_course_day(day: int) -> dict:
    """Return the programme of the given course day (1 or 2)."""
    return {"day": day, "modules": ["Compliance, safety and ethics", "Capstone"] if day == 2 else ["Intro"]}


@pytest.mark.live
def test_run_live_tool_call(live_key):
    labkit._state["setup_ok"] = True
    from google.adk.agents import Agent
    a = Agent(name="course_helper", model=agents.make_model(),
              instruction="Use get_course_day for any question about the course programme.",
              tools=[get_course_day])
    res = agents.run(a, "What happens on day 2?", show=False)
    assert "get_course_day" in res.tool_calls
    assert res.text.strip()



def test_summarize_joins_split_text_parts():
    from google.adk.events import Event
    from google.genai import types
    ev = Event(author="a", content=types.Content(role="model", parts=[types.Part(text="Hello "), types.Part(text="world")]))
    assert agents.summarize([ev])[0] == "Hello world"


def test_deterministic_config_is_temperature_zero():
    assert agents.DETERMINISTIC.temperature == 0
