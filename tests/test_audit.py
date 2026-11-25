"""Audit log written automatically by an ADK after_tool_callback."""
from types import SimpleNamespace as NS

from labkit.audit import AuditLog


def test_callback_records_tool_calls_without_changing_the_result():
    log = AuditLog()
    resp = {"batch_id": "B04", "flagged_samples": [{"sample_id": "B04-S11"}], "status": "flags"}
    out = log.callback(tool=NS(name="check_internal_standard"), args={"batch_id": "B04"},
                       tool_context=NS(agent_name="qc_reviewer"), tool_response=resp)
    assert out is None
    e = log.entries[0]
    assert e["tool"] == "check_internal_standard" and e["batch_id"] == "B04" and e["agent"] == "qc_reviewer"
    assert "1 flagged" in e["summary"]


def test_decision_and_rebuild_for_one_batch():
    log = AuditLog()
    log.callback(tool=NS(name="apply_westgard"), args={"batch_id": "B06"}, tool_context=NS(),
                 tool_response={"violations": [{"rule": "R-4s", "level": "QC-M"}], "status": "reject"})
    log.callback(tool=NS(name="check_ion_ratio"), args={"batch_id": "B05"}, tool_context=NS(),
                 tool_response={"flagged_samples": [], "status": "pass"})
    log.decision("B06", "ESCALATE", [], "STATUS: ESCALATE")
    rows = log.for_batch("B06")
    assert [r["tool"] for r in rows] == ["apply_westgard", "DECISION (agent proposal)"]
    assert "R-4s" in rows[0]["summary"] and "human approval pending" in rows[1]["summary"]
    html = log.html("B06")
    assert "apply_westgard" in html and "check_ion_ratio" not in html
