"""Shared status parsing: last status line wins, markdown tolerated, sample lists and ranges expanded."""
import pytest

from labkit.status import parse_samples, parse_status

QC = ("PASS", "HOLD", "ESCALATE")


@pytest.mark.parametrize("text,expected", [
    ("Westgard status: accept. Calibration status: pass\nSTATUS: HOLD\nSAMPLES ON HOLD: B04-S11", "HOLD"),
    ("Proposed status - HOLD pending review\nSTATUS: ESCALATE", "ESCALATE"),
    ("**Status**: HOLD\n**Samples on hold**: B04-S11, B04-S12", "HOLD"),
    ("Report...\n**STATUS: ESCALATE**", "ESCALATE"),
    ("STATUS - pass", "PASS"),
    ("I could not decide.", ""),
])
def test_last_status_line_wins(text, expected):
    assert parse_status(text, QC) == expected


def test_verdict_with_markdown():
    assert parse_status("Evidence...\n**VERDICT**: HOLD", ("RELEASE", "HOLD", "ESCALATE"), word="verdict") == "HOLD"


def test_samples_ranges_and_bullets():
    assert parse_samples("SAMPLES ON HOLD: B04-S11 to B04-S15", r"B\d{2}-S\d{2}") == [
        "B04-S11", "B04-S12", "B04-S13", "B04-S14", "B04-S15"]
    text = "SAMPLES ON HOLD:\n- B05-S07\n- B05-S29\n\nThe deviation note was drafted."
    assert parse_samples(text, r"B\d{2}-S\d{2}") == ["B05-S07", "B05-S29"]
    assert parse_samples("SAMPLES ON HOLD: none", r"B\d{2}-S\d{2}") == []


def test_status_in_any_model_text_of_the_run():
    from types import SimpleNamespace as NS
    from labkit.status import all_model_text

    def ev(text):
        return NS(content=NS(role="model", parts=[NS(text=text, thought=False, function_call=None)]))

    events = [ev("Report.\nSTATUS: HOLD\nSAMPLES ON HOLD: B04-S11"), ev("The deviation note has been drafted.")]
    assert parse_status(all_model_text(events), QC) == "HOLD"
