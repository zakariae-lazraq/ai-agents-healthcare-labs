"""A4: a run that failed on quota/busy is 'not run', never 'wrong'; re-runs redo only the failed cases."""
import json
import pathlib

import labkit
from labkit import agents, fhirlab, guardian, qc, risk

DATA = pathlib.Path(__file__).resolve().parents[1] / "data"
BUSY = "Gemini is very busy right now"


def test_qc_scoreboard_excludes_not_run():
    key = json.loads((DATA / "lab02" / "answer_key.json").read_text(encoding="utf-8"))
    rows = [{"batch_id": "B02", "status": "ESCALATE", "samples": [], "tools": [], "text": "", "note": ""},
            {"batch_id": "B03", "status": "", "samples": [], "tools": [], "text": "", "note": BUSY}]
    html, right = qc.scoreboard_html(rows, key)
    assert right == 1 and "not run" in html and "1 / 1" in html and "1 not run" in html


def test_risk_scoreboard_excludes_not_run():
    profiles = json.loads((DATA / "lab03" / "profiles.json").read_text(encoding="utf-8"))
    rows = [{"id": "P1", "status": "ESTIMATE", "tools": [], "text": "", "note": ""},
            {"id": "T1", "status": "", "tools": [], "text": "", "note": BUSY}]
    html, right = risk.scoreboard_html(rows, profiles)
    assert right == 1 and "not run" in html and "1 / 1" in html


def test_fhir_scoreboard_excludes_not_run():
    key = json.loads((DATA / "lab05" / "answer_key.json").read_text(encoding="utf-8"))
    rows = [{"patient_id": "pat-01", "status": "PASS", "tools": [], "text": "", "note": ""},
            {"patient_id": "pat-02", "status": "", "tools": [], "text": "", "note": BUSY}]
    html, right, _ = fhirlab.scoreboard_html(rows, key, [])
    assert right == 1 and "not run" in html


def test_guardian_evaluate_excludes_not_run():
    g = guardian.load(DATA / "lab06")
    verdicts = {c["id"]: c["expected"] for c in g.cases}
    verdicts[g.cases[0]["id"]] = ""          # not run
    e = guardian.evaluate(g.cases, verdicts)
    assert e["not_run"] == [g.cases[0]["id"]] and e["n"] == 29 and e["exact"] == 29


def test_rerun_redoes_only_failed(monkeypatch):
    labkit._state["setup_ok"] = True
    asked = []

    async def fake(agent, message, plugins=None):
        asked.append(message)
        return agents.RunResult("STATUS: PASS")

    monkeypatch.setattr(agents, "arun", fake)
    from labkit.audit import AuditLog
    previous = [{"batch_id": "B01", "status": "PASS", "samples": [], "tools": [], "text": "x", "note": ""},
                {"batch_id": "B02", "status": "", "samples": [], "tools": [], "text": "", "note": BUSY}]
    out = qc.run_batches("agent", ["B01", "B02"], AuditLog(), show_progress=False, previous=previous)
    assert asked == ["Review batch B02."] and [o["batch_id"] for o in out] == ["B01", "B02"]
