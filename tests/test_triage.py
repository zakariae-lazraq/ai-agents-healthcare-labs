"""Lab 4 triage: shipped data and model, routing rule, threshold sweep, tools, quality check."""
import pathlib

import numpy as np
import pytest

from labkit import triage

DATA = pathlib.Path(__file__).resolve().parents[1] / "data" / "lab04"


@pytest.fixture(scope="module")
def data():
    return triage.load(DATA)


def test_shipped_data_and_model(data):
    assert data.images.shape == (200, 28, 28, 3) and len(data.ids) == 200
    assert data.probs.shape == (200, 9) and np.allclose(data.probs.sum(1), 1, atol=1e-4)
    assert data.card["accuracy_test"] >= 0.80
    acc = float((data.probs.argmax(1) == data.labels).mean())
    assert acc >= 0.75


def test_routing_rule():
    assert triage.reference_route(0.95, 0.03) == "auto"
    assert triage.reference_route(0.70, 0.20) == "review"
    assert triage.reference_route(0.85, 0.70) == "review"


def test_higher_threshold_sends_more_to_humans_and_is_more_accurate(data):
    rows = triage.sweep(data, [0.60, 0.80, 0.95])
    assert rows[0]["to_humans_pct"] <= rows[1]["to_humans_pct"] <= rows[2]["to_humans_pct"]
    assert rows[0]["auto_accuracy_pct"] <= rows[2]["auto_accuracy_pct"]
    assert 5 <= rows[1]["to_humans_pct"] <= 60


def test_tools_route_and_queue(data):
    q = []
    t = triage.make_triage_tools(data, lambda p1, p2: triage.reference_route(p1, p2), q)
    r = t["triage_images"](["IMG001", "IMG002", "BAD"])
    assert len(r["results"]) == 2 and r["unknown_ids"] == ["BAD"]
    t["add_to_review_queue"]("IMG002", "close call")
    t["add_to_review_queue"]("IMG002", "again")
    assert q == [{"image_id": "IMG002", "reason": "close call"}]
    assert "IMG002" in triage.queue_html(data, q)


def test_quality_check_catches_blank_and_blur_not_real_tiles(data):
    assert triage.quality_problem(data.extra["blank"]).startswith("blank")
    assert "blur" in triage.quality_problem(data.extra["blurred"])
    ok = sum(triage.quality_problem(img) == "" for img in data.images)
    assert ok >= 190


def test_model_is_confident_on_out_of_scope_images(data):
    """The teaching point: a blank tile still gets 9 probabilities summing to 1, often with high confidence."""
    p = data.predict(np.stack([data.extra["blank"], data.extra["colour_shifted"]]))
    assert np.allclose(p.sum(1), 1, atol=1e-4)


def test_second_opinion_sends_the_image_and_handles_errors(data):
    from types import SimpleNamespace as NS
    seen = {}

    def gen(model, contents, config=None):
        seen["n_parts"] = len(contents)
        return NS(text="Most likely lymphocytes. I am not certain.")

    r = triage.second_opinion(data, "IMG001", "m", client=NS(models=NS(generate_content=gen)))
    assert r["text"].startswith("Most likely") and seen["n_parts"] == 2

    def boom(model, contents, config=None):
        raise RuntimeError("429 RESOURCE_EXHAUSTED quota")

    r = triage.second_opinion(data, "IMG001", "m", client=NS(models=NS(generate_content=boom)))
    assert r["text"] == "" and "quota" in r["message"].lower()
