"""Lab 3: a risk model as an agent tool — input checks, prediction, explanation, and a guardrail in code.

The guardrail is an ADK before_tool_callback: it runs before predict_risk / explain_prediction and, if the input is
invalid, returns a result itself — the tool never runs, whatever the model decided. A prompt can be argued with;
code cannot.
"""

from __future__ import annotations

import json
import math
import re
from pathlib import Path

TRAINING = {"age": (30, 79), "systolic_bp": (90, 200), "cholesterol": (120, 400), "max_heart_rate": (70, 205)}
IMPOSSIBLE = {"age": (0, 120), "systolic_bp": (50, 300), "cholesterol": (50, 1000), "max_heart_rate": (30, 250)}
UNITS = {"age": "years", "systolic_bp": "mmHg", "cholesterol": "mg/dL", "max_heart_rate": "bpm"}
MMOL_TO_MGDL = 38.67
GUARDED = ("predict_risk", "explain_prediction")
FIELDS = ("age", "sex", "systolic_bp", "cholesterol", "max_heart_rate", "smoker", "diabetes")
RUN_LOG: list[dict] = []   # every time predict_risk really ran (evidence for the guardrail test)
NOTE = "Risk estimate for research and education — not a diagnosis and not a treatment decision."


def load_model(folder) -> dict:
    return json.loads((Path(folder) / "model.json").read_text(encoding="utf-8"))


def _row(features: dict) -> dict:
    sex = str(features.get("sex", "")).strip().lower()
    return {"age": float(features["age"]), "male": 1.0 if sex in ("male", "m", "man") else 0.0,
            "systolic_bp": float(features["systolic_bp"]), "cholesterol": float(features["cholesterol"]),
            "max_heart_rate": float(features["max_heart_rate"]), "smoker": 1.0 if features.get("smoker") else 0.0,
            "diabetes": 1.0 if features.get("diabetes") else 0.0}


def check_ranges(features: dict) -> dict:
    """Impossible values, likely unit errors and out-of-training-range values. status 'ok' or 'hold'."""
    problems = []
    sex = str(features.get("sex", "")).strip().lower()
    if sex not in ("male", "female", "m", "f", "man", "woman"):
        problems.append({"field": "sex", "value": features.get("sex"), "issue": "must be male or female"})
    for field, (lo, hi) in IMPOSSIBLE.items():
        try:
            v = float(features[field])
        except (KeyError, TypeError, ValueError):
            problems.append({"field": field, "value": features.get(field), "issue": "missing or not a number"})
            continue
        if field == "cholesterol" and 1.5 <= v <= 15:
            problems.append({"field": field, "value": v, "issue": (
                f"looks like mmol/L, not mg/dL (≈ {round(v * MMOL_TO_MGDL)} mg/dL): confirm the unit")})
        elif not lo <= v <= hi:
            problems.append({"field": field, "value": v,
                             "issue": f"impossible value for {field} ({UNITS[field]}): outside {lo}–{hi}"})
        else:
            tlo, thi = TRAINING[field]
            if not tlo <= v <= thi:
                problems.append({"field": field, "value": v, "issue": (
                    f"outside the training range {tlo}–{thi} {UNITS[field]}: the model would extrapolate")})
    return {"status": "hold" if problems else "ok", "problems": problems}


def log_odds(model: dict, features: dict) -> float:
    r = _row(features)
    return model["intercept"] + sum(model["coef"][f] * (r[f] - model["mean"][f]) / model["sd"][f]
                                    for f in model["features"])


def explain(model: dict, features: dict) -> dict:
    r = _row(features)
    contrib = [{"factor": f, "value": r[f], "log_odds_contribution": round(
        model["coef"][f] * (r[f] - model["mean"][f]) / model["sd"][f], 6)} for f in model["features"]]
    for c in contrib:
        c["direction"] = "raises risk" if c["log_odds_contribution"] > 0 else "lowers risk"
    top = sorted(contrib, key=lambda c: -abs(c["log_odds_contribution"]))[:3]
    return {"baseline_log_odds": model["intercept"], "top_factors": top, "all_factors": contrib,
            "how_to_read": "each factor's contribution compared with an average profile of the training data"}


def make_risk_tools(model: dict) -> dict:
    auc = model["metrics"]["auc_validation"]

    def check_input_ranges(age: int, sex: str, systolic_bp: float, cholesterol: float, max_heart_rate: float,
                           smoker: bool, diabetes: bool) -> dict:
        """Check a profile before any prediction: impossible values, likely unit errors (cholesterol must be in
        mg/dL) and values outside the model's training range. Returns status 'ok' or 'hold' with the problems."""
        return check_ranges(locals())

    def predict_risk(age: int, sex: str, systolic_bp: float, cholesterol: float, max_heart_rate: float,
                     smoker: bool, diabetes: bool) -> dict:
        """Estimate the 10-year cardiovascular event risk (probability 0–1) for a profile. Units: years, mmHg,
        mg/dL, bpm; sex 'male' or 'female'. Call check_input_ranges first."""
        RUN_LOG.append({k: v for k, v in locals().items() if k in FIELDS})
        p = 1 / (1 + math.exp(-log_odds(model, locals())))
        return {"risk_10y": round(p, 3), "risk_percent": f"{p * 100:.0f} %", "model_auc_validation": auc,
                "note": NOTE, "model_limits": model["limits"]}

    def explain_prediction(age: int, sex: str, systolic_bp: float, cholesterol: float, max_heart_rate: float,
                           smoker: bool, diabetes: bool) -> dict:
        """Explain a risk estimate: the 3 factors that raise or lower this profile's risk most, compared with an
        average profile of the training data."""
        return explain(model, locals())

    return {f.__name__: f for f in (check_input_ranges, predict_risk, explain_prediction)}


def ran_on_invalid_input() -> bool:
    """True if predict_risk really ran on an input that fails the range check (since RUN_LOG was cleared)."""
    return any(check_ranges(r)["status"] != "ok" for r in RUN_LOG)


def reference_guardrail(tool, args, tool_context):
    """Reference before_tool_callback: block prediction tools on invalid input (returns the tool's result itself)."""
    if getattr(tool, "name", "") in GUARDED:
        check = check_ranges(args)
        if check["status"] != "ok":
            return {"blocked_by_guardrail": True, "status": "HOLD",
                    "reason": "input failed the range check — no prediction made", "problems": check["problems"]}
    return None


_STATUS = re.compile(r"status\s*[:\-–]?\s*\**\s*(estimate|hold|refuse)\b", re.I)


def parse_status(text: str) -> str:
    m = _STATUS.search(text or "")
    return m.group(1).upper() if m else ""


def run_profiles(agent, profiles: list[dict], show_progress: bool = True, concurrency: int = 2) -> list[dict]:
    from labkit.batch import run_many

    res = run_many(agent, [p["message"] for p in profiles], show_progress=show_progress, concurrency=concurrency)
    return [{"id": p["id"], "status": parse_status(r.text), "tools": list(r.tool_calls), "text": r.text,
             "note": r.message or r.note} for p, r in zip(profiles, res)]


def scoreboard_html(rows: list[dict], profiles: list[dict]) -> tuple[str, int]:
    import html as _h

    key = {p["id"]: p for p in profiles}
    td = "padding:4px 10px;text-align:left;vertical-align:top"
    body, right = "", 0
    for r in rows:
        k = key[r["id"]]
        ok = r["status"] == k["expected"]
        right += ok
        checked = "check_input_ranges" in r["tools"]
        body += (f"<tr style='border-top:1px solid #C9D2DC'><td style='{td}'><b>{r['id']}</b></td>"
                 f"<td style='{td}'>{k['expected']}<br><span style='color:#5F6B7A;font-size:12px'>"
                 f"{_h.escape(k['why'])}</span></td><td style='{td}'>{_h.escape(r['status'] or '—')}"
                 + (f"<br><span style='color:#B7791F;font-size:12px'>{_h.escape(r['note'])}</span>" if r["note"] else "")
                 + f"</td><td style='{td};font-size:12px'>{'yes' if checked else 'no'}</td>"
                 f"<td style='{td};color:{'#1E7A3C' if ok else '#B3261E'}'><b>{'right' if ok else 'wrong'}</b></td></tr>")
    html = ("<table style='border-collapse:collapse;font-family:Inter,Segoe UI,Roboto,sans-serif;font-size:13px'>"
            f"<tr><th style='{td}'>Case</th><th style='{td}'>Expected</th><th style='{td}'>Agent</th>"
            f"<th style='{td}'>Checked input first?</th><th style='{td}'>Result</th></tr>{body}"
            f"<tr style='border-top:2px solid #1F3A5F'><td style='{td}' colspan='5'><b>{right} / {len(rows)}</b> "
            "cases right</td></tr></table>")
    return html, right


def explanation_chart(model: dict, features: dict, title: str = ""):
    """Horizontal bars: each factor's contribution to the log-odds (right = raises risk)."""
    import matplotlib.pyplot as plt

    e = explain(model, features)
    items = sorted(e["all_factors"], key=lambda c: c["log_odds_contribution"])
    fig, ax = plt.subplots(figsize=(7, 3), dpi=110)
    ax.barh([c["factor"] for c in items], [c["log_odds_contribution"] for c in items],
            color=["#B3261E" if c["log_odds_contribution"] > 0 else "#2A7F7F" for c in items])
    ax.axvline(0, color="#1F3A5F", lw=1)
    ax.set_xlabel("contribution to log-odds (right = raises risk)")
    p = 1 / (1 + math.exp(-log_odds(model, features)))
    ax.set_title(title or f"10-year risk estimate {p * 100:.0f} % — not a diagnosis", loc="left", fontsize=11)
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    fig.tight_layout()
    return fig


def calibration_chart(model: dict):
    """Predicted versus observed event rate in 5 risk groups of the validation set (on the diagonal = calibrated)."""
    import matplotlib.pyplot as plt

    cal = model["calibration"]
    fig, ax = plt.subplots(figsize=(4.2, 3.6), dpi=110)
    ax.plot([0, 1], [0, 1], color="#C9D2DC", lw=1, ls="--", label="perfect calibration")
    ax.plot([b["predicted"] for b in cal], [b["observed"] for b in cal], marker="o", color="#2A7F7F", label="model")
    ax.set_xlabel("predicted risk (mean per group)")
    ax.set_ylabel("observed event rate")
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.set_title("Calibration on validation data", loc="left", fontsize=11)
    ax.legend(frameon=False, fontsize=8)
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    fig.tight_layout()
    return fig


def truth_chart(model: dict):
    """Teaching only: the direction the model learned for each factor versus the true effect used to make the data."""
    import matplotlib.pyplot as plt

    feats = model["features"]
    learned = [model["coef"][f] for f in feats]
    truth = [model["teaching_truth"][f] * model["sd"][f] for f in feats]   # true effect per 1 SD, comparable scale
    fig, ax = plt.subplots(figsize=(7, 3), dpi=110)
    y = range(len(feats))
    ax.barh([i + 0.2 for i in y], truth, height=0.38, color="#C9D2DC", label="true effect (synthetic data)")
    ax.barh([i - 0.2 for i in y], learned, height=0.38, color="#1F3A5F", label="learned by the model")
    ax.set_yticks(list(y), feats)
    ax.axvline(0, color="#5F6B7A", lw=1)
    ax.set_xlabel("effect on log-odds per 1 SD (right = raises risk)")
    ax.legend(frameon=False, fontsize=8, loc="lower right")
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    fig.tight_layout()
    return fig
