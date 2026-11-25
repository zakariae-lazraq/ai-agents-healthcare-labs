import pytest

import labkit
from labkit import ui


def test_check_all_ok():
    assert ui.check([(True, "Name filled", "Give the agent a name")]) is True


def test_check_reports_fix():
    html = ui.check_html([(True, "Name filled", ""), (False, "Tool added", "Add get_course_day to tools=[...]")])
    assert "FIX" in html and "Add get_course_day to tools=[...]" in html
    assert "Fix the red lines" in html
    assert ui.check([(False, "x", "y")]) is False


def test_has_blank_detects_placeholder():
    assert ui.has_blank("Northbridge helper", "___") is not None
    assert ui.has_blank("Use the tool ___ when asked") is not None
    assert ui.has_blank("   ") is not None
    assert ui.has_blank(...) is not None
    assert ui.has_blank("Northbridge helper", "Use the tool.") is None


def test_require_setup_before_and_after():
    labkit._state["setup_ok"] = False
    with pytest.raises(RuntimeError, match="Setup has not passed yet"):
        ui.require_setup()
    labkit._state["setup_ok"] = True
    ui.require_setup()


def test_copy_box_escapes():
    html = ui.copy_box("<b>hi</b>").data
    assert "&lt;b&gt;hi&lt;/b&gt;" in html and "Copy" in html


def test_done_card_mentions_screenshot():
    html = ui.done_card("Lab 0", ["Key works"]).data
    assert "Lab 0 complete" in html and "screenshot" in html and "Key works" in html


def test_run_refuses_blank_instruction():
    from google.adk.agents import Agent
    from labkit import agents
    labkit._state["setup_ok"] = True
    a = Agent(name="helper", model=agents.make_model(), instruction="Use ___ for schedule questions.")
    assert "___" in agents.run(a, "hi", show=False).message


def test_run_requires_setup():
    from google.adk.agents import Agent
    from labkit import agents
    labkit._state["setup_ok"] = False
    a = Agent(name="helper", model=agents.make_model(), instruction="ok")
    assert "Setup has not passed yet" in agents.run(a, "hi", show=False).message


def test_labkit_outputs_have_no_emoji():
    import re
    from labkit import agents, setup
    from labkit.trace import trace_html
    from tests.test_trace import sample_events
    emoji = re.compile("[\U0001F300-\U0001FAFF\u2600-\u27BF\u23F3]")
    texts = [ui.check_html([(True, "a", ""), (False, "b", "c")]), ui.check_html([(False, "b", "c")], optional=True),
             ui.done_card("Lab 0", ["x"]).data, ui.error_line("x").data, trace_html(sample_events()),
             setup.checks_html([setup.CheckResult("k", False, "d", setup.FIX_KEY_MISSING)]),
             agents.QUOTA_MESSAGE, agents.NOT_BUILT, ui.SETUP_NOT_PASSED]
    for t in texts:
        assert not emoji.search(t), t[:120]



def test_status_card_title_and_items():
    html = ui.done_card("Lab 0 — status", ["a"], complete=False).data
    assert "Lab 0 — status" in html and "not complete" in html.lower()
    html2 = ui.done_card("Lab 0 — status", ["a"], complete=True).data
    assert "complete" in html2.lower() and "not complete" not in html2.lower()


def test_ready_reports_blank_and_wrong_tools():
    def tool():
        pass
    assert ui.ready("name", "rules", [tool]) is True
    assert ui.ready("___", "rules", [tool]) is False
    assert ui.ready("name", "rules", ["___"]) is False
    assert ui.ready("name", "rules", ["get_test_info"]) is False  # quoted name instead of the function


def test_ready_names_the_labs_own_tool(monkeypatch):
    from labkit import ui
    shown = []
    monkeypatch.setattr(ui, "error_line", lambda m: shown.append(m) or m)
    import IPython.display
    monkeypatch.setattr(IPython.display, "display", lambda *a, **k: None)
    assert ui.ready("a", "rules", ["search_sop"], example="search_sop") is False
    assert "TOOLS = [search_sop]" in shown[0]
