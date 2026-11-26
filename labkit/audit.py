"""Audit log written automatically: an ADK after_tool_callback records every tool call and its result.

The agent cannot forget to log, and cannot change what was logged: the code does it, not the model.
Used from Lab 2 onwards: `Agent(..., after_tool_callback=LOG.callback)`.
"""

from __future__ import annotations

import datetime
import html as _html


def _summary(resp) -> str:
    if not isinstance(resp, dict):
        return str(resp)[:120]
    if resp.get("status") == "error":
        return "ERROR: " + str(resp.get("message", ""))[:100]
    parts = []
    if "r2" in resp:
        parts.append(f"r² {resp['r2']}")
    if resp.get("failed_calibrators"):
        parts.append("failed: " + ", ".join(resp["failed_calibrators"]))
    if "flagged_samples" in resp:
        ids = [f.get("sample_id", "?") for f in resp["flagged_samples"]]
        parts.append(f"{len(ids)} flagged" + (": " + ", ".join(ids) if ids else ""))
    if "violations" in resp:
        rules = [f"{v.get('rule')} ({v.get('level')})" for v in resp["violations"]]
        parts.append(", ".join(rules) if rules else "no violation")
    if "results" in resp and "auto" in resp and "review" in resp:
        parts.append(f"{len(resp['results'])} images: {resp['auto']} auto, {resp['review']} to review")
    if resp.get("status") == "queued":
        parts.append(f"{resp.get('image_id')} queued for review")
        return "; ".join(parts)
    if resp.get("requires_human_approval"):
        parts.append("deviation note drafted for supervisor approval")
    if "status" in resp:
        parts.append(f"status {resp['status']}")
    return "; ".join(parts) or str(resp)[:120]


_KEYS = ("batch_id", "patient_id", "case_id", "sample_id", "image_id", "profile_id")


class AuditLog:
    def __init__(self):
        self.entries: list[dict] = []
        self._n = 0

    def clear(self) -> None:
        self.entries.clear()

    def callback(self, tool, args, tool_context, tool_response):
        """ADK after_tool_callback: record, return None (the tool result is passed on unchanged)."""
        args = dict(args or {})
        try:
            run = getattr(tool_context, "invocation_id", None)
        except Exception:
            run = None
        self._n += 1
        self.entries.append({
            "time": datetime.datetime.now().isoformat(timespec="seconds"),
            "agent": getattr(tool_context, "agent_name", "agent"),
            "tool": getattr(tool, "name", str(tool)),
            "batch_id": next((str(args[k]) for k in _KEYS if args.get(k)), ""),
            "run": run,   # ADK invocation id; None outside a real run (then never collapsed)
            "args": args,
            "summary": _summary(tool_response),
        })
        return None

    def latest(self) -> list[dict]:
        """For each item (batch, patient, case …) keep only the entries of its most recent run: a re-run after a
        quota error does not show the failed attempt twice. Entries without an item id are all kept."""
        last = {}
        for e in self.entries:
            if e["batch_id"] and e.get("run"):
                last[e["batch_id"]] = e["run"]
        return [e for e in self.entries if not e["batch_id"] or not e.get("run") or
                e["tool"].startswith("DECISION") or last.get(e["batch_id"]) == e["run"]]

    def decision(self, batch_id: str, status: str, samples: list[str], report: str) -> None:
        """Record the agent's proposed status. The decision itself stays with a human."""
        self.entries.append({
            "time": datetime.datetime.now().isoformat(timespec="seconds"), "agent": "qc_reviewer",
            "tool": "DECISION (agent proposal)", "batch_id": batch_id, "args": {},
            "summary": f"{status or 'no status'}; on hold: {', '.join(samples) or 'none'}; human approval pending",
        })

    def for_batch(self, batch_id: str) -> list[dict]:
        return [e for e in self.latest() if e["batch_id"] == batch_id]

    def html(self, batch_id: str | None = None) -> str:
        rows = self.for_batch(batch_id) if batch_id else self.latest()
        td = "padding:3px 10px;text-align:left;vertical-align:top"
        body = "".join(
            f"<tr style='border-top:1px solid #C9D2DC'><td style='{td};color:#5F6B7A'>{_html.escape(e['time'][11:])}</td>"
            f"<td style='{td}'>{_html.escape(e['batch_id'])}</td><td style='{td}'><b>{_html.escape(e['tool'])}</b></td>"
            f"<td style='{td}'>{_html.escape(e['summary'])}</td></tr>" for e in rows)
        return ("<table style='border-collapse:collapse;font-family:Inter,Segoe UI,Roboto,sans-serif;font-size:13px'>"
                f"<tr><th style='{td}'>Time</th><th style='{td}'>Item</th><th style='{td}'>Tool / event</th>"
                f"<th style='{td}'>Result recorded</th></tr>{body}</table>")
