"""Lab 3 risk tools: input checks, prediction, explanation, guardrail, profiles answer key."""
import json
import pathlib
from types import SimpleNamespace as NS

import pytest

from labkit import risk

DATA = pathlib.Path(__file__).resolve().parents[1] / "data" / "lab03"


@pytest.fixture(scope="module")
def model():
    return risk.load_model(DATA)


@pytest.fixture(scope="module")
def tools(model):
    return risk.make_risk_tools(model)


@pytest.fixture(scope="module")
def profiles():
    return json.loads((DATA / "profiles.json").read_text(encoding="utf-8"))


OK = dict(age=55, sex="male", systolic_bp=140, cholesterol=240, max_heart_rate=150, smoker=True, diabetes=False)


def test_model_has_validation_metrics(model):
    assert 0.70 <= model["metrics"]["auc_validation"] <= 0.95
    assert model["metrics"]["n_train"] >= 1000


def test_valid_profile_predicts_a_probability(tools):
    assert tools["check_input_ranges"](**OK)["status"] == "ok"
    p = tools["predict_risk"](**OK)
    assert 0 < p["risk_10y"] < 1 and "not a diagnosis" in p["note"].lower()


def test_impossible_value_is_flagged(tools):
    r = tools["check_input_ranges"](**{**OK, "cholesterol": 5000})
    assert r["status"] == "hold" and r["problems"][0]["field"] == "cholesterol"
    assert "impossible" in r["problems"][0]["issue"]


def test_mmol_l_cholesterol_is_flagged_as_unit_problem(tools):
    r = tools["check_input_ranges"](**{**OK, "cholesterol": 5.4})
    assert r["status"] == "hold" and "mmol/L" in r["problems"][0]["issue"] and "209" in r["problems"][0]["issue"]


def test_out_of_training_range_is_flagged(tools):
    r = tools["check_input_ranges"](**{**OK, "age": 91})
    assert r["status"] == "hold" and "training" in r["problems"][0]["issue"]


def test_explanation_contributions_sum_to_the_log_odds(model, tools):
    e = tools["explain_prediction"](**OK)
    assert len(e["top_factors"]) == 3
    total = sum(c["log_odds_contribution"] for c in e["all_factors"]) + e["baseline_log_odds"]
    assert abs(total - risk.log_odds(model, OK)) < 1e-6


def test_higher_risk_profile_has_higher_probability(tools):
    low = tools["predict_risk"](age=40, sex="female", systolic_bp=115, cholesterol=180, max_heart_rate=175,
                                smoker=False, diabetes=False)["risk_10y"]
    high = tools["predict_risk"](age=68, sex="male", systolic_bp=170, cholesterol=290, max_heart_rate=110,
                                 smoker=True, diabetes=True)["risk_10y"]
    assert high > low * 3


def test_reference_guardrail_blocks_invalid_input_in_code(model):
    blocked = risk.reference_guardrail(tool=NS(name="predict_risk"), args={**OK, "cholesterol": 5000},
                                       tool_context=None)
    assert blocked["blocked_by_guardrail"] is True
    assert risk.reference_guardrail(tool=NS(name="predict_risk"), args=OK, tool_context=None) is None
    assert risk.reference_guardrail(tool=NS(name="check_input_ranges"), args={**OK, "cholesterol": 5000},
                                    tool_context=None) is None


def test_profiles_answer_key(profiles, model):
    assert len([p for p in profiles if p["kind"] == "profile"]) == 5
    assert {p["id"] for p in profiles if p["kind"] == "trap"} == {"T1", "T2", "T3"}
    for p in profiles:
        if p["kind"] == "profile":
            assert risk.check_ranges(p["features"])["status"] == "ok", p["id"]
            assert p["expected"] == "ESTIMATE"


@pytest.mark.parametrize("text,status", [("...\nSTATUS: HOLD", "HOLD"), ("**STATUS: REFUSE**", "REFUSE"),
                                         ("STATUS - estimate", "ESTIMATE"), ("nothing", "")])
def test_parse_status(text, status):
    assert risk.parse_status(text) == status


def test_predict_risk_records_every_real_run(tools):
    risk.RUN_LOG.clear()
    tools["predict_risk"](**{**OK, "cholesterol": 5000})
    tools["check_input_ranges"](**OK)
    assert len(risk.RUN_LOG) == 1 and risk.RUN_LOG[0]["cholesterol"] == 5000
    assert risk.ran_on_invalid_input() is True
    risk.RUN_LOG.clear()
    assert risk.ran_on_invalid_input() is False
