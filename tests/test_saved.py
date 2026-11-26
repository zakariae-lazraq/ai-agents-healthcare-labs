"""A9: saved answers are shown only for items that did not run, labelled, and never scored."""
from labkit import saved


def test_not_run_lists_and_dicts():
    rows = [{"batch_id": "B01", "status": "PASS"}, {"batch_id": "B02", "status": "", "note": "quota"}]
    assert saved.not_run(rows, "batch_id") == ["B02"]
    assert saved.not_run({"C01": {"verdict": "HOLD"}, "C02": {"verdict": ""}}, "case_id") == ["C02"]


def test_html_labels_saved_answers(monkeypatch):
    monkeypatch.setattr(saved, "load", lambda lab: {"recorded": "2026-11-26", "model": "m",
                                                     "results": {"B02": {"status": "ESCALATE", "text": "CAL3 +17 %"}}})
    h = saved.html("lab02", ["B02"])
    assert "not in your score" in h and "ESCALATE" in h and "2026-11-26" in h
    assert "no saved answer needed" in saved.html("lab02", ["B99"])


def test_second_opinion_waits_once_on_per_minute_limit(monkeypatch):
    import time
    from types import SimpleNamespace as NS
    from labkit import DATA_DIR, triage
    data = triage.load(DATA_DIR / "lab04")
    calls = []

    class Models:
        def generate_content(self, **kw):
            calls.append(1)
            if len(calls) == 1:
                raise Exception("429 RESOURCE_EXHAUSTED. Please retry in 3s.")
            return NS(text="tumor epithelium")
    monkeypatch.setattr(time, "sleep", lambda s: None)
    r = triage.second_opinion(data, data.ids[0], "m", client=NS(models=Models()))
    assert r["text"] == "tumor epithelium" and len(calls) == 2
