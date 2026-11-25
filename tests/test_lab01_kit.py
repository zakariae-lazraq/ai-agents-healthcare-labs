"""labkit pieces used by Lab 1: SOP loading and search, scoring against the answer key, batch runs."""
import json
import pathlib

import pytest

import labkit
from labkit import scoring, sop

DATA = pathlib.Path(__file__).resolve().parents[1] / "data" / "lab01"


@pytest.fixture(scope="module")
def sections():
    return sop.load_sops(DATA / "sops")


@pytest.fixture(scope="module")
def questions():
    return {q["id"]: q for q in json.loads((DATA / "questions.json").read_text(encoding="utf-8"))}


def test_load_sops(sections):
    assert len(sections) == 18
    s = [x for x in sections if x.sop == "SOP-01" and x.number == "5"][0]
    assert s.title == "Ion ratio" and "20 %" in s.text


@pytest.mark.parametrize("query,sop_id,num", [
    ("ion ratio tolerance vitamin D", "SOP-01", "5"),
    ("haemolysed sample potassium accepted", "SOP-02", "3"),
    ("phone critical potassium inpatient minutes", "SOP-03", "3"),
    ("calibration curve r2", "SOP-01", "3"),
    ("stability vitamin D 2-8", "SOP-02", "5"),
])
def test_search_finds_the_right_section(sections, query, sop_id, num):
    search = sop.make_search_tool(sections)
    top = search(query)["results"]
    assert (top[0]["sop"], top[0]["section"]) == (sop_id, num)
    assert len(top) <= 3 and "text" in top[0]


def test_search_tool_has_a_docstring(sections):
    assert "SOP" in sop.make_search_tool(sections).__doc__


def test_scoreboard_counts(questions):
    qs = list(questions.values())[:2]
    a = [scoring.Grade("correct", ""), scoring.Grade("fabricated", "")]
    b = [scoring.Grade("correct", ""), scoring.Grade("correct", "")]
    counts = scoring.count(a)
    assert counts["correct"] == 1 and counts["fabricated"] == 1
    html = scoring.scoreboard_html(qs, {"Naive": a, "Grounded": b},
                                   {"Grounded": ["", "saved answer (Gemini was not available)"]})
    assert "Naive" in html and "Grounded" in html and "1 / 2" in html and "2 / 2" in html
    assert "Expected (SOP)" in html and qs[0]["expected"].split()[0] in html
    assert "SAVED ANSWER" in html and "1 saved answer(s) included" in html


def test_compare_you_vs_machine(questions):
    qs = list(questions.values())
    grades = [scoring.Grade("fabricated", "r")] * len(qs)
    html = scoring.compare_html(qs, {"Q05": "Fabricated (invented fact or number)", "Q06": "Correct"}, grades)
    assert html.count(">same<") == 1 and "who is right" in html and "14 days" in html


def test_run_many_uses_run(monkeypatch):
    from labkit import agents, batch
    calls = []
    async def fake(agent, q, plugins=None):
        calls.append(q)
        return agents.RunResult(q.upper())
    monkeypatch.setattr(agents, "arun", fake)
    res = batch.run_many("agent", ["a", "b"], show_progress=False)
    assert [r.text for r in res] == ["A", "B"] and calls == ["a", "b"]


def test_run_many_parallel_keeps_order_and_uses_saved_fallback(monkeypatch):
    import asyncio
    from labkit import agents, batch
    labkit._state["setup_ok"] = True

    async def fake_arun(agent, message, plugins=None):
        await asyncio.sleep(0.05 if message == "a" else 0.0)
        if message == "c":
            return agents.RunResult("", [], [], "Gemini is very busy right now")
        return agents.RunResult(message.upper(), [], ["search_sop"])

    monkeypatch.setattr(agents, "arun", fake_arun)
    saved = {"c": "saved answer for c"}
    res = batch.run_many("agent", ["a", "b", "c"], show_progress=False, saved=saved, concurrency=3)
    assert [r.text for r in res] == ["A", "B", "saved answer for c"]
    assert "saved" in res[2].note.lower() and res[0].note == ""


def test_side_by_side_folds_long_answers():
    from labkit.agents import RunResult
    from labkit.batch import side_by_side
    long = "Intro sentence. " + "Detail about ion ratios. " * 60
    html = side_by_side([{"id": "Q01", "question": "q?"}],
                        {"Naive": [RunResult(long)], "Grounded": [RunResult("Short (SOP-01 §5).")]})
    assert html.count("<details") == 1 and "Show full answer" in html
    assert "Short (SOP-01 §5)." in html