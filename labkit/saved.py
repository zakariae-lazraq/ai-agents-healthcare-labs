"""Saved answers: what the reference agent answered when the course was tested live.

Shown only when the participant's own run could not reach the model (free-quota limit or a busy service), so the
lab can continue. Saved answers are clearly labelled and never counted in the participant's score.
Files: data/labNN/saved_runs.json, {"recorded": "YYYY-MM-DD", "model": …, "results": {item_id: {...}}}.
"""

from __future__ import annotations

import html as _html
import json

from labkit import DATA_DIR


def load(lab: str) -> dict:
    p = DATA_DIR / lab / "saved_runs.json"
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}


def not_run(rows, id_key: str) -> list[str]:
    """Items of a result list (or {id: result} dict) that have no status/verdict because the model was unreachable."""
    if isinstance(rows, dict):
        rows = [{id_key: k, **v} for k, v in rows.items()]
    return [r[id_key] for r in rows or [] if not (r.get("status") or r.get("verdict"))]


def html(lab: str, ids: list[str]) -> str:
    saved = load(lab)
    res = saved.get("results", {})
    td = "padding:4px 10px;text-align:left;vertical-align:top;font-size:13px"
    rows = ""
    for i in ids:
        r = res.get(i)
        if not r:
            continue
        rows += (f"<tr style='border-top:1px solid #C9D2DC'><td style='{td}'><b>{_html.escape(i)}</b></td>"
                 f"<td style='{td}'>{_html.escape(str(r.get('status') or r.get('verdict') or '-'))}</td>"
                 f"<td style='{td};white-space:pre-wrap'>{_html.escape(str(r.get('text', ''))[:900])}</td></tr>")
    if not rows:
        return "<div style='font-family:Inter,Segoe UI,Roboto,sans-serif'>Every item ran, no saved answer needed.</div>"
    return ("<div style='font-family:Inter,Segoe UI,Roboto,sans-serif;font-size:13px;color:#B7791F;margin:4px 0'>"
            f"Saved answers of the reference agent (recorded {saved.get('recorded', '?')}, {saved.get('model', '?')}). "
            "For reading only, not your agent, not in your score. Re-run your cell later to get your own.</div>"
            "<table style='border-collapse:collapse;font-family:Inter,Segoe UI,Roboto,sans-serif'>"
            f"<tr><th style='{td}'>Item</th><th style='{td}'>Status</th><th style='{td}'>Answer</th></tr>{rows}</table>")
