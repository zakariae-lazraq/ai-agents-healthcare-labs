import pytest

import labkit
from labkit import ui


def test_check_all_ok():
    assert ui.check([(True, "Name filled", "Give the agent a name")]) is True


def test_check_reports_fix():
    html = ui.check_html([(True, "Name filled", ""), (False, "Tool added", "Add get_course_day to tools=[...]")])
    assert "❌" in html and "Add get_course_day to tools=[...]" in html
    assert "Fix the ❌ lines" in html
    assert ui.check([(False, "x", "y")]) is False


def test_has_blank_detects_placeholder():
    assert ui.has_blank("Northbridge helper", "___") is not None
    assert ui.has_blank("Use the tool ___ when asked") is not None
    assert ui.has_blank("   ") is not None
    assert ui.has_blank(...) is not None
    assert ui.has_blank("Northbridge helper", "Use the tool.") is None


def test_require_setup_before_and_after():
    labkit._state["setup_ok"] = False
    with pytest.raises(RuntimeError, match="Run the Setup cell"):
        ui.require_setup()
    labkit._state["setup_ok"] = True
    ui.require_setup()


def test_copy_box_escapes():
    html = ui.copy_box("<b>hi</b>").data
    assert "&lt;b&gt;hi&lt;/b&gt;" in html and "Copy" in html


def test_done_card_mentions_screenshot():
    html = ui.done_card("Lab 0", ["Key works"]).data
    assert "Lab 0 complete ✅" in html and "screenshot" in html and "Key works" in html


def test_run_refuses_blank_instruction():
    from google.adk.agents import Agent
    from labkit import agents
    labkit._state["setup_ok"] = True
    a = Agent(name="helper", model=agents.make_model(), instruction="Use ___ for schedule questions.")
    with pytest.raises(ValueError, match="___"):
        agents.run(a, "hi", show=False)


def test_run_requires_setup():
    from google.adk.agents import Agent
    from labkit import agents
    labkit._state["setup_ok"] = False
    a = Agent(name="helper", model=agents.make_model(), instruction="ok")
    with pytest.raises(RuntimeError, match="Setup cell"):
        agents.run(a, "hi", show=False)
