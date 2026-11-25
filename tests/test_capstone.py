"""Lab 8 capstone helpers: canvas checks (outline success criteria), exports, test cases, scoring."""
import labkit
from labkit import capstone

GOOD = {
    "problem_and_users": "Morning review of LC-MS/MS batches by the QC supervisor.",
    "goal": "Halve review time without missing any QC failure.",
    "inputs_and_data": "Batch CSV exports, QC history, SOP-01.",
    "tools": "check_calibration, check_ion_ratio, apply_westgard, draft_deviation.",
    "agent_steps": "Run all checks, apply status rules, draft a deviation note.",
    "human_checkpoints": "Supervisor approves every HOLD and ESCALATE before release.",
    "guardian_checks": "Counts recomputed from the data; no PHI in the note.",
    "risks": "Missed drift; over-trust; data export errors.",
    "compliance_controls": "ISO 15189 validation, audit trail, CAP checklist, GDPR access control.",
    "success_metrics": "Detection 100 % of planted QC failures on 50 batches; false alarms below 5 %.",
    "pilot_plan": "Shadow mode for 4 weeks, then supervised use on one analyser.",
}


def test_good_canvas_passes_every_criterion():
    assert all(ok for ok, _, _ in capstone.check_canvas(GOOD))


def test_missing_human_checkpoint_and_metric_fail():
    bad = dict(GOOD, human_checkpoints="", success_metrics="faster reviews")
    failed = [what for ok, what, _ in capstone.check_canvas(bad) if not ok]
    assert any("human checkpoint" in f for f in failed) and any("measurable" in f for f in failed)


def test_exports():
    md = capstone.canvas_markdown("Team QC", GOOD)
    assert md.startswith("# Agent design canvas — Team QC") and "## Human checkpoints" in md
    assert "Supervisor approves" in capstone.canvas_html("Team QC", GOOD)


def test_run_test_cases(monkeypatch):
    from labkit import agents
    labkit._state["setup_ok"] = True

    async def fake(agent, message, plugins=None):
        return agents.RunResult("ok\nSTATUS: HOLD" if "bad" in message else "ok\nSTATUS: PASS")

    monkeypatch.setattr(agents, "arun", fake)
    rows = capstone.run_test_cases("agent", [{"input": "good batch", "expected": "PASS"},
                                             {"input": "bad batch", "expected": "HOLD"},
                                             {"input": "bad again", "expected": "PASS"}], show_progress=False)
    assert [r["ok"] for r in rows] == [True, True, False]
    assert "2 / 3" in capstone.results_html(rows)


def test_scores_sorted_best_first():
    html = capstone.scores_html({"A": {"value": 3, "feasibility": 3, "safety": 3, "oversight": 3},
                                 "B": {"value": 5, "feasibility": 4, "safety": 5, "oversight": 5}})
    assert html.index(">B<") < html.index(">A<") and "19</b> / 20" in html
