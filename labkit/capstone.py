"""Lab 8 capstone: the agent design canvas (check, one-page view, Markdown export), test cases, peer scoring."""

from __future__ import annotations

import html as _html
import re

CANVAS_FIELDS = [
    ("problem_and_users", "Problem and users"), ("goal", "Goal"), ("inputs_and_data", "Inputs and data"),
    ("tools", "Tools"), ("agent_steps", "Agent steps"), ("human_checkpoints", "Human checkpoints"),
    ("guardian_checks", "Guardian checks"), ("risks", "Risks"), ("compliance_controls", "Compliance controls"),
    ("success_metrics", "Success metrics"), ("pilot_plan", "Pilot plan")]
COMPLIANCE_WORDS = ("hipaa", "gdpr", "clia", "cap", "iso 15189", "ivdr", "fda", "21 cfr", "audit", "validation",
                    "gxp", "glp", "data protection", "access control")
GRID = [("value", "Value for the laboratory"), ("feasibility", "Feasibility"),
        ("safety", "Safety and compliance"), ("oversight", "Clarity of human oversight")]


def check_canvas(canvas: dict) -> list[tuple[bool, str, str]]:
    """The outline's success criteria, as CHECK items (ok, what, how to fix)."""
    filled = [k for k, _ in CANVAS_FIELDS if len(str(canvas.get(k, "")).strip()) >= 10]
    comp = str(canvas.get("compliance_controls", "")).lower()
    metrics = str(canvas.get("success_metrics", ""))
    return [
        (len(filled) == len(CANVAS_FIELDS), f"All 11 boxes filled ({len(filled)}/11)",
         "Write at least one short sentence in every box."),
        (len(str(canvas.get("human_checkpoints", "")).strip()) >= 10, "At least one human checkpoint",
         "Say where a person approves, reviews or decides (e.g. 'supervisor approves every HOLD')."),
        (len(str(canvas.get("guardian_checks", "")).strip()) >= 10, "At least one guardian check",
         "Name a check on the agent's output (numbers recomputed, references verified, PHI detected…)."),
        (any(w in comp for w in COMPLIANCE_WORDS), "Compliance controls named",
         "Name the frameworks or controls (e.g. ISO 15189, CAP, CLIA, GDPR/HIPAA, IVDR, audit trail, validation)."),
        (bool(re.search(r"\d", metrics)), "Success metrics are measurable (contain a number)",
         "Give a target, e.g. 'detection ≥ 95 % on 50 test cases, false alarms ≤ 5 %'."),
    ]


def canvas_html(team: str, canvas: dict) -> str:
    cells = "".join(
        f"<div style='border:1px solid #C9D2DC;border-radius:6px;padding:8px 10px;background:#FFFFFF'>"
        f"<div style='font-size:11px;font-weight:700;letter-spacing:.05em;color:#2A7F7F;text-transform:uppercase'>"
        f"{label}</div><div style='font-size:13px;margin-top:4px;white-space:pre-wrap'>"
        f"{_html.escape(str(canvas.get(k, '')).strip()) or '<i style=color:#B3261E>empty</i>'}</div></div>"
        for k, label in CANVAS_FIELDS)
    return (f"<div style='font-family:Inter,Segoe UI,Roboto,sans-serif;max-width:980px'><div style='font-size:19px;"
            f"font-weight:700;color:#1F3A5F;margin-bottom:8px'>Agent design canvas — {_html.escape(team)}</div>"
            f"<div style='display:grid;grid-template-columns:repeat(3,1fr);gap:8px'>{cells}</div></div>")


def canvas_markdown(team: str, canvas: dict) -> str:
    lines = [f"# Agent design canvas — {team}", ""]
    for k, label in CANVAS_FIELDS:
        lines += [f"## {label}", str(canvas.get(k, "")).strip() or "_(empty)_", ""]
    return "\n".join(lines)


def run_test_cases(agent, cases: list[dict], show_progress: bool = True) -> list[dict]:
    """cases: [{'input': …, 'expected': 'PASS'|'HOLD'|…}]. The agent must end with 'STATUS: …'."""
    from labkit.batch import run_many

    res = run_many(agent, [c["input"] for c in cases], show_progress=show_progress, concurrency=2)
    out = []
    for c, r in zip(cases, res):
        from labkit.status import all_model_text, parse_status

        allowed = tuple(sorted({x["expected"].upper() for x in cases}))
        got = parse_status(all_model_text(r.events) or r.text, allowed)
        out.append({"input": c["input"], "expected": c["expected"].upper(), "agent": got or "—",
                    "ok": got == c["expected"].upper(), "note": r.message or r.note})
    return out


def results_html(rows: list[dict]) -> str:
    td = "padding:4px 10px;text-align:left;vertical-align:top;font-size:13px"
    body = "".join(f"<tr style='border-top:1px solid #C9D2DC'><td style='{td}'>{_html.escape(r['input'][:160])}</td>"
                   f"<td style='{td}'>{r['expected']}</td><td style='{td}'>{_html.escape(r['agent'])}</td>"
                   f"<td style='{td};color:{'#1E7A3C' if r['ok'] else '#B3261E'}'><b>{'right' if r['ok'] else 'wrong'}"
                   f"</b></td></tr>" for r in rows)
    n = sum(r["ok"] for r in rows)
    return ("<table style='border-collapse:collapse;font-family:Inter,Segoe UI,Roboto,sans-serif'>"
            f"<tr><th style='{td}'>Test input</th><th style='{td}'>Expected</th><th style='{td}'>Agent</th>"
            f"<th style='{td}'>Result</th></tr>{body}<tr style='border-top:2px solid #1F3A5F'><td style='{td}' "
            f"colspan='4'><b>{n} / {len(rows)}</b> test cases right</td></tr></table>")


def scores_html(scores: dict[str, dict[str, int]]) -> str:
    """scores: team → {value, feasibility, safety, oversight} (1–5). Shows totals, best first."""
    td = "padding:4px 12px;text-align:left;font-size:13px"
    rows = sorted(scores.items(), key=lambda kv: -sum(kv[1].values()))
    body = "".join(f"<tr style='border-top:1px solid #C9D2DC'><td style='{td}'><b>{_html.escape(t)}</b></td>"
                   + "".join(f"<td style='{td}'>{s.get(k, '')}</td>" for k, _ in GRID)
                   + f"<td style='{td}'><b>{sum(s.values())}</b> / 20</td></tr>" for t, s in rows)
    head = "".join(f"<th style='{td}'>{label}</th>" for _, label in GRID)
    return ("<table style='border-collapse:collapse;font-family:Inter,Segoe UI,Roboto,sans-serif'>"
            f"<tr><th style='{td}'>Team</th>{head}<th style='{td}'>Total</th></tr>{body}</table>")
