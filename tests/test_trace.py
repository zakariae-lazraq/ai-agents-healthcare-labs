from google.adk.events import Event
from google.genai import types

from labkit.trace import trace_cards, trace_html


def _ev(part, role="model"):
    return Event(author="agent", content=types.Content(role=role, parts=[part]))


def sample_events(result_text="Day 2: compliance"):
    return [
        _ev(types.Part(function_call=types.FunctionCall(name="get_course_day", args={"day": 2}))),
        _ev(types.Part(function_response=types.FunctionResponse(name="get_course_day",
                                                                response={"result": result_text})), role="user"),
        _ev(types.Part(text="On day 2 we cover compliance.")),
    ]


def test_trace_cards_order():
    html = trace_html(sample_events())
    i_call, i_res, i_final = html.index("🔧"), html.index("📄"), html.index("✅")
    assert i_call < i_res < i_final
    assert "get_course_day" in html
    assert "On day 2 we cover compliance." in html


def test_trace_escapes_html():
    html = trace_html(sample_events(result_text="<script>alert(1)</script>"))
    assert "<script>" not in html
    assert "&lt;script&gt;" in html


def test_trace_cards_returns_display_object():
    from IPython.display import HTML
    assert isinstance(trace_cards(sample_events()), HTML)
