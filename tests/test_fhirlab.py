"""Lab 5 FHIR tools: planted issues found by the right check, report drafting and validation, answer key."""
import json
import pathlib

import pytest

from labkit import fhirlab

DATA = pathlib.Path(__file__).resolve().parents[1] / "data" / "lab05"


@pytest.fixture(scope="module")
def lab():
    return fhirlab.load(DATA)


@pytest.fixture()
def tools(lab):
    return fhirlab.make_fhir_tools(lab)


@pytest.fixture(scope="module")
def key():
    return json.loads((DATA / "answer_key.json").read_text(encoding="utf-8"))


def test_twenty_patients_with_resources(lab):
    assert len(lab.patients) == 20
    for pid in lab.patients:
        assert lab.observations(pid) and lab.requests(pid)
    assert all(m.startswith("NB-") and len(m) == 9 for m in lab.mrns.values())


def test_reference_status_matches_answer_key(lab, key):
    for pid, k in key.items():
        assert fhirlab.reference_status(lab, pid)[0] == k["status"], pid


def test_planted_issues_by_check(tools):
    coding = [p for p in ("pat-03", "pat-07", "pat-11") if tools["check_coding"](p)["problems"]]
    assert coding == ["pat-03", "pat-07", "pat-11"]
    assert "mmol/L" in tools["check_units"]("pat-05")["problems"][0]["issue"]
    assert tools["check_units"]("pat-14")["problems"]
    assert "missing" in tools["check_units"]("pat-16")["problems"][0]["issue"]
    assert tools["check_critical"]("pat-09")["critical"][0]["value"] == 6.8
    assert tools["check_duplicates"]("pat-18")["duplicates"]
    for check in ("check_coding", "check_units", "check_duplicates"):
        assert not tools[check]("pat-01").get("problems") and not tools[check]("pat-01").get("duplicates")
    assert not tools["check_critical"]("pat-01")["critical"]


def test_draft_report_is_valid_fhir_and_keeps_values(lab, tools):
    r = tools["draft_diagnostic_report"]("pat-01", "All results within reference. For review.")
    assert r["report"]["status"] == "preliminary"
    assert fhirlab.validate_report(lab, r["report"]) == []
    bad = dict(r["report"], status="final")
    assert any("preliminary" in p for p in fhirlab.validate_report(lab, bad))
    bad2 = dict(r["report"], result=[{"reference": "Observation/does-not-exist"}])
    assert any("does not exist" in p for p in fhirlab.validate_report(lab, bad2))


def test_notifications_are_recorded(lab, tools):
    lab.notifications.clear()
    tools["notify_human"]("pat-09", "Critical potassium 6.8 mmol/L", "urgent")
    assert lab.notifications[0]["patient_id"] == "pat-09" and lab.notifications[0]["urgency"] == "urgent"


def test_unknown_patient_is_a_clear_error(tools):
    r = tools["get_observations"]("pat-99")
    assert r["status"] == "error" and "pat-01" in r["message"]


def test_lookup_loinc(tools):
    assert tools["lookup_loinc"]("2823-3")["unit"] == "mmol/L"
    assert tools["lookup_loinc"]("0000-0")["status"] == "unknown"


def test_delta_check_challenge(lab):
    assert fhirlab.delta_problems(lab, "pat-12") and not fhirlab.delta_problems(lab, "pat-01")


@pytest.mark.parametrize("text,status", [("x\nSTATUS: HOLD", "HOLD"), ("**STATUS: ESCALATE**", "ESCALATE"),
                                         ("status - pass", "PASS"), ("", "")])
def test_parse_status(text, status):
    assert fhirlab.parse_status(text) == status


def test_run_patients_and_scoreboard(lab, key, monkeypatch):
    import labkit
    from labkit import agents
    labkit._state["setup_ok"] = True

    async def fake(agent, message, plugins=None):
        pid = message.split()[-1].rstrip(".")
        return agents.RunResult(f"Done.\nSTATUS: {key[pid]['status']}", [], ["check_units"])

    monkeypatch.setattr(agents, "arun", fake)
    lab.notifications.clear()
    lab.notifications.append({"patient_id": "pat-09", "mrn": "x", "message": "K 6.8", "urgency": "urgent"})
    rows = fhirlab.run_patients("agent", lab.patients, show_progress=False)
    html, right, notify_ok = fhirlab.scoreboard_html(rows, key, lab.notifications)
    assert right == 20 and notify_ok is True and "pat-09" in html
    lab.notifications.append({"patient_id": "pat-01", "mrn": "y", "message": "?", "urgency": "urgent"})
    assert fhirlab.scoreboard_html(rows, key, lab.notifications)[2] is False


def test_hl7_guide_lists_segments(lab):
    html = fhirlab.hl7_guide_html((DATA / "oru_example.hl7").read_text(encoding="utf-8"))
    for seg in ("MSH", "PID", "OBR", "OBX"):
        assert seg in html
    assert "6.8" in html and "HH" in html
