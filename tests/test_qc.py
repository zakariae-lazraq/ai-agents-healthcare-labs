"""Lab 2 QC tools: on the shipped data they must find exactly the planted issues (the answer key)."""
import json
import pathlib

import pytest

from labkit import qc

DATA = pathlib.Path(__file__).resolve().parents[1] / "data" / "lab02"


@pytest.fixture(scope="module")
def tools():
    return qc.make_qc_tools(qc.load(DATA))


@pytest.fixture(scope="module")
def key():
    return json.loads((DATA / "answer_key.json").read_text(encoding="utf-8"))


def test_ten_batches_with_the_outline_layout():
    d = qc.load(DATA)
    assert sorted(d.batches["batch_id"].unique()) == [f"B{i:02d}" for i in range(1, 11)]
    b01 = d.batches[d.batches.batch_id == "B01"]
    assert (b01.sample_type == "calibrator").sum() == 6
    assert (b01.sample_type == "qc").sum() == 6 and (b01.sample_type == "patient").sum() == 40
    for col in ("batch_id", "sample_id", "sample_type", "expected_conc", "measured_conc", "analyte_area",
                "IS_area", "quantifier_ion", "qualifier_ion", "retention_time"):
        assert col in d.batches.columns
    assert d.history.groupby("level").run_id.nunique().min() == 20


def test_reference_status_matches_answer_key_for_every_batch(key):
    d = qc.load(DATA)
    for batch_id, expected in key.items():
        status, hold = qc.reference_status(d, batch_id, include_retention=False)
        assert status == expected["status"], (batch_id, status)
        assert sorted(hold) == sorted(expected["samples_on_hold"]), batch_id


def test_planted_issues_found_by_the_right_tool(tools):
    cal = tools["check_calibration"]("B02")
    assert cal["status"] == "fail" and cal["r2"] >= 0.995 and cal["failed_calibrators"] == ["CAL3"]
    assert "10-x" in {v["rule"] for v in tools["apply_westgard"]("B03")["violations"]}
    assert len(tools["check_internal_standard"]("B04")["flagged_samples"]) == 5
    assert len(tools["check_ion_ratio"]("B05")["flagged_samples"]) == 2
    rules = {v["rule"] for v in tools["apply_westgard"]("B06")["violations"]}
    assert rules == {"R-4s"}


def test_clean_batch_has_no_flag(tools):
    assert tools["check_calibration"]("B01")["status"] == "pass"
    assert tools["check_internal_standard"]("B01")["flagged_samples"] == []
    assert tools["check_ion_ratio"]("B01")["flagged_samples"] == []
    assert tools["apply_westgard"]("B01")["violations"] == []


def test_retention_time_issue_only_visible_with_the_challenge_check(key):
    d = qc.load(DATA)
    assert qc.reference_status(d, "B10", include_retention=False)[0] == "PASS"
    status, hold = qc.reference_status(d, "B10", include_retention=True)
    assert status == "HOLD" and len(hold) == 3


def test_unknown_batch_is_a_clear_error_not_a_crash(tools):
    r = tools["check_calibration"]("B99")
    assert r["status"] == "error" and "B01" in r["message"]


def test_tools_have_docstrings_for_the_model(tools):
    for f in tools.values():
        assert f.__doc__ and len(f.__doc__) > 30


@pytest.mark.parametrize("text,status,samples", [
    ("Summary...\nSTATUS: HOLD\nSAMPLES ON HOLD: B04-S11, B04-S12", "HOLD", ["B04-S11", "B04-S12"]),
    ("**STATUS: ESCALATE**\nSAMPLES ON HOLD: none", "ESCALATE", []),
    ("Status - pass", "PASS", []),
    ("I could not decide.", "", []),
])
def test_parse_status(text, status, samples):
    assert qc.parse_status(text) == (status, samples)
