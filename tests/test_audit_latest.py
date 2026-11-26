"""Audit log: a re-run of an item replaces its earlier attempt in the displayed log (A10)."""
from types import SimpleNamespace as NS

from labkit.audit import AuditLog


def test_rerun_shows_only_latest_attempt_per_item():
    log = AuditLog()
    t = NS(name="check_units")
    log.callback(t, {"patient_id": "pat-01"}, NS(invocation_id="run1"), {"problems": []})
    log.callback(t, {"patient_id": "pat-02"}, NS(invocation_id="run2"), {"problems": []})
    log.callback(t, {"patient_id": "pat-01"}, NS(invocation_id="run3"), {"problems": []})
    shown = log.latest()
    assert [e["batch_id"] for e in shown] == ["pat-02", "pat-01"] and shown[1]["run"] == "run3"
    assert len(log.entries) == 3          # nothing is deleted: the full record stays in LOG.entries
    assert "pat-01" in log.html() and len(log.for_batch("pat-01")) == 1
