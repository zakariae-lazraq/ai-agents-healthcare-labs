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
    i_call, i_res, i_final = html.index("TOOL CALL"), html.index("TOOL RESULT"), html.index("ANSWER")
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



def test_answer_markdown_is_rendered():
    events = [_ev(types.Part(text="The longest is **Lab 8**.\n* Lab 6\n* Lab 7 <b>"))]
    html = trace_html(events)
    assert "<b>Lab 8</b>" in html and "**" not in html
    assert "<li>Lab 6</li>" in html
    assert "&lt;b&gt;" in html  # model text is still escaped
