"""Lab 6 guardian: every planted problem is found by the right check, no safe case is flagged by any check."""
import pathlib

import pytest

from labkit import guardian

DATA = pathlib.Path(__file__).resolve().parents[1] / "data" / "lab06"


@pytest.fixture(scope="module")
def g():
    return guardian.load(DATA)


def by_label(g, label):
    return [c for c in g.cases if c["label"] == label]


def test_thirty_cases_fifteen_safe(g):
    assert len(g.cases) == 30 and len(by_label(g, "SAFE")) == 15
    assert {c["label"] for c in g.cases} == {"SAFE", "INVENTED_LIMIT", "FAKE_REFERENCE", "WRONG_COUNT", "INJECTION",
                                             "PHI", "UNSAFE_ADVICE"}


def test_no_check_fires_on_a_safe_case(g):
    for c in by_label(g, "SAFE"):
        assert not guardian.grounding_problems(c), (c["id"], guardian.grounding_problems(c))
        assert not guardian.number_problems(g, c), (c["id"], guardian.number_problems(g, c))
        assert not guardian.reference_problems(g, c), (c["id"], guardian.reference_problems(g, c))
        assert not guardian.phi_problems(c) and not guardian.injection_problems(c), c["id"]


def test_each_problem_type_is_caught_by_its_check(g):
    for c in by_label(g, "INVENTED_LIMIT"):
        assert guardian.grounding_problems(c), c["id"]
    for c in by_label(g, "FAKE_REFERENCE"):
        assert guardian.reference_problems(g, c), c["id"]
    for c in by_label(g, "WRONG_COUNT"):
        assert guardian.number_problems(g, c), c["id"]
    for c in by_label(g, "INJECTION"):
        assert guardian.injection_problems(c), c["id"]
    for c in by_label(g, "PHI"):
        assert guardian.phi_problems(c), c["id"]


def test_code_only_guardian_misses_the_severity_of_unsafe_advice(g):
    verdicts = {c["id"]: guardian.reference_guardian(g, c)[0] for c in g.cases}
    e = guardian.evaluate(g.cases, verdicts)
    assert e["detection_rate"] == 1.0 and e["false_alarm_rate"] == 0.0
    unsafe = by_label(g, "UNSAFE_ADVICE")[0]["id"]
    assert e["missed_high_severity"] == [unsafe]


def test_tools_and_alerts(g):
    t = guardian.make_guardian_tools(g)
    cid = by_label(g, "PHI")[0]["id"]
    assert t["detect_phi"](cid)["phi_found"]
    g.alerts.clear()
    t["alert_human"](cid, "high", "MRN in the answer")
    assert g.alerts == [{"case_id": cid, "severity": "high", "reason": "MRN in the answer"}]
    assert t["check_grounding"]("C99")["status"] == "error"


def test_hunt_scoring(g):
    problems = [c["id"] for c in g.cases if c["label"] != "SAFE"]
    s = guardian.score_hunt(g.cases, problems[:10] + [by_label(g, "SAFE")[0]["id"]])
    assert s["detection_rate"] == round(10 / 15, 2) and s["false_alarm_rate"] == round(1 / 15, 2)
    assert sum(v[1] for v in s["by_type"].values()) == 15


@pytest.mark.parametrize("text,v", [("...\nVERDICT: HOLD", "HOLD"), ("**Verdict: ESCALATE**", "ESCALATE"),
                                    ("verdict - release", "RELEASE"), ("none", "")])
def test_parse_verdict(text, v):
    assert guardian.parse_verdict(text) == v
