"""Lab 2: quality-control tools for LC-MS/MS batches (25-OH vitamin D), and the status rules.

The tools do all the arithmetic; the agent only calls them and decides. Rules are those of SOP-01:
calibration r² ≥ 0.995 and back-calculated accuracy ±15 % (±20 % at the lowest level); internal standard area
50–150 % of the mean IS area of calibrators and QCs; ion ratio ±20 % of the calibrator mean; Westgard rules
1-3s, 2-2s, R-4s, 4-1s, 10-x against the established QC targets.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

import pandas as pd

LEVELS = ("QC-L", "QC-M", "QC-H")
RT_TOLERANCE = 0.10   # minutes, challenge check


@dataclass
class QCData:
    batches: pd.DataFrame
    history: pd.DataFrame
    targets: pd.DataFrame

    def batch(self, batch_id: str) -> pd.DataFrame:
        return self.batches[self.batches.batch_id == batch_id]

    @property
    def batch_ids(self) -> list[str]:
        return sorted(self.batches.batch_id.unique())


def load(folder) -> QCData:
    folder = Path(folder)
    return QCData(pd.read_csv(folder / "batches.csv"), pd.read_csv(folder / "qc_history.csv"),
                  pd.read_csv(folder / "qc_targets.csv"))


def _unknown(data: QCData, batch_id: str) -> dict | None:
    if batch_id not in data.batch_ids:
        return {"status": "error", "message": f"Unknown batch '{batch_id}'. Valid batches: {', '.join(data.batch_ids)}."}
    return None


# ---------------------------------------------------------------- individual checks (pure functions)
def calibration(data: QCData, batch_id: str) -> dict:
    cal = data.batch(batch_id).query("sample_type == 'calibrator'")
    x = cal.expected_conc.to_numpy(float)
    y = (cal.analyte_area / cal.IS_area).to_numpy(float)
    w = 1 / x                                   # linear, 1/x weighted (usual for LC-MS/MS calibration)
    xm, ym = (w * x).sum() / w.sum(), (w * y).sum() / w.sum()
    slope = (w * (x - xm) * (y - ym)).sum() / (w * (x - xm) ** 2).sum()
    intercept = ym - slope * xm
    pred = slope * x + intercept
    r2 = 1 - (w * (y - pred) ** 2).sum() / (w * (y - ym) ** 2).sum()
    rows, failed = [], []
    for sid, conc, resp in zip(cal.sample_id, x, y):
        back = (resp - intercept) / slope
        acc = (back - conc) / conc * 100
        limit = 20 if conc == x.min() else 15
        ok = abs(acc) <= limit
        rows.append({"sample_id": sid, "nominal_ng_ml": conc, "back_calculated_ng_ml": round(back, 2),
                     "accuracy_pct": round(acc, 1), "limit_pct": limit, "pass": bool(ok)})
        if not ok:
            failed.append(sid)
    passed = r2 >= 0.995 and not failed
    return {"batch_id": batch_id, "r2": round(float(r2), 4), "r2_limit": 0.995, "calibrators": rows,
            "failed_calibrators": failed, "status": "pass" if passed else "fail",
            "rule": "SOP-01 §3: linear 1/x weighted fit; r² ≥ 0.995; accuracy ±15 % (±20 % at the lowest calibrator)"}


def internal_standard(data: QCData, batch_id: str) -> dict:
    b = data.batch(batch_id)
    ref = b[b.sample_type.isin(["calibrator", "qc"])].IS_area.mean()
    pct = b.IS_area / ref * 100
    flagged = [{"sample_id": s, "sample_type": t, "is_area_pct": round(float(p), 1)}
               for s, t, p in zip(b.sample_id, b.sample_type, pct) if p < 50 or p > 150]
    return {"batch_id": batch_id, "mean_is_area_calibrators_qcs": round(float(ref)), "flagged_samples": flagged,
            "status": "flags" if flagged else "pass",
            "rule": "SOP-01 §4: IS area 50–150 % of the mean of calibrators and QCs"}


def ion_ratio(data: QCData, batch_id: str) -> dict:
    b = data.batch(batch_id)
    ratio = b.qualifier_ion / b.quantifier_ion
    ref = ratio[b.sample_type == "calibrator"].mean()
    dev = (ratio - ref) / ref * 100
    flagged = [{"sample_id": s, "sample_type": t, "ion_ratio": round(float(r), 3), "deviation_pct": round(float(d), 1)}
               for s, t, r, d in zip(b.sample_id, b.sample_type, ratio, dev) if abs(d) > 20]
    return {"batch_id": batch_id, "calibrator_mean_ratio": round(float(ref), 3), "flagged_samples": flagged,
            "status": "flags" if flagged else "pass",
            "rule": "SOP-01 §5: ion ratio within ±20 % of the calibrator mean"}


def retention_time(data: QCData, batch_id: str) -> dict:
    b = data.batch(batch_id)
    ref = b[b.sample_type == "calibrator"].retention_time.mean()
    flagged = [{"sample_id": s, "sample_type": t, "retention_time_min": float(rt), "shift_min": round(float(rt - ref), 3)}
               for s, t, rt in zip(b.sample_id, b.sample_type, b.retention_time) if abs(rt - ref) > RT_TOLERANCE]
    return {"batch_id": batch_id, "calibrator_mean_rt_min": round(float(ref), 3), "flagged_samples": flagged,
            "status": "flags" if flagged else "pass",
            "rule": f"retention time within ±{RT_TOLERANCE} min of the calibrator mean"}


def z_table(data: QCData) -> pd.DataFrame:
    """All QC results (history then batches, in run order) as z-scores against the established targets."""
    t = data.targets.set_index("level")
    hist = data.history.rename(columns={"run_id": "run"})[["run", "level", "measured_conc"]]
    qcs = data.batches.query("sample_type == 'qc'").copy()
    qcs["level"] = qcs.sample_id.str.rsplit("-", n=1).str[0]
    qcs = qcs.rename(columns={"batch_id": "run"})[["run", "level", "measured_conc"]]
    z = pd.concat([hist, qcs], ignore_index=True)
    z["z"] = (z.measured_conc - z.level.map(t["mean"])) / z.level.map(t["sd"])
    return z


def westgard(data: QCData, batch_id: str) -> dict:
    z = z_table(data)
    runs = list(dict.fromkeys(z.run))
    upto = runs[: runs.index(batch_id) + 1]
    cur = z[z.run == batch_id]
    v = []
    for lvl in LEVELS:
        zs = cur[cur.level == lvl].z.tolist()
        if any(abs(x) > 3 for x in zs):
            v.append({"rule": "1-3s", "level": lvl,
                      "detail": f"a result beyond 3 SD ({', '.join(f'{x:+.1f}' for x in zs)} SD)"})
        if len(zs) == 2 and (min(zs) > 2 or max(zs) < -2):
            v.append({"rule": "2-2s", "level": lvl, "detail": "both replicates beyond 2 SD on the same side"})
        if len(zs) == 2 and max(zs) > 2 and min(zs) < -2:
            v.append({"rule": "R-4s", "level": lvl, "detail": f"replicates at {max(zs):+.1f} SD and {min(zs):+.1f} SD"})
        means = z[(z.level == lvl) & z.run.isin(upto)].groupby("run", sort=False).z.mean().reindex(upto).tolist()
        if len(means) >= 4 and (all(m > 1 for m in means[-4:]) or all(m < -1 for m in means[-4:])):
            v.append({"rule": "4-1s", "level": lvl, "detail": "4 consecutive runs beyond 1 SD on the same side"})
        if len(means) >= 10 and (all(m > 0 for m in means[-10:]) or all(m < 0 for m in means[-10:])):
            v.append({"rule": "10-x", "level": lvl, "detail": "10 consecutive runs on the same side of the mean (drift)"})
    for side in (1, -1):   # 2-2s across levels in the same run
        lv = sorted({r.level for r in cur.itertuples() if side * r.z > 2})
        if len(lv) >= 2:
            v.append({"rule": "2-2s", "level": " + ".join(lv), "detail": "two QC levels beyond 2 SD on the same side"})
    qc_now = {lvl: [round(float(x), 2) for x in cur[cur.level == lvl].z] for lvl in LEVELS}
    return {"batch_id": batch_id, "qc_z_scores": qc_now, "violations": v,
            "status": "reject" if v else "accept",
            "rule": "Westgard 1-3s, 2-2s, R-4s, 4-1s, 10-x against established QC targets (SOP-01 §6)"}


def reference_status(data: QCData, batch_id: str, include_retention: bool = False) -> tuple[str, list[str]]:
    """The status rules applied in code (the answer the agent should reach)."""
    if calibration(data, batch_id)["status"] == "fail" or westgard(data, batch_id)["violations"]:
        return "ESCALATE", []
    checks = [internal_standard(data, batch_id), ion_ratio(data, batch_id)]
    if include_retention:
        checks.append(retention_time(data, batch_id))
    flagged = [f for c in checks for f in c["flagged_samples"]]
    if any(f["sample_type"] != "patient" for f in flagged):
        return "ESCALATE", []
    hold = sorted({f["sample_id"] for f in flagged})
    return ("HOLD", hold) if hold else ("PASS", [])


# ---------------------------------------------------------------- tools for the agent
def make_qc_tools(data: QCData) -> dict:
    """The agent's tools, bound to one data set. Each returns a dict; unknown batch ids give a clear error."""

    def check_calibration(batch_id: str) -> dict:
        """Check the calibration curve of an LC-MS/MS batch: r² and the back-calculated accuracy of each of the
        6 calibrators (limits ±15 %, ±20 % at the lowest level). batch_id is like 'B01'."""
        return _unknown(data, batch_id) or calibration(data, batch_id)

    def check_internal_standard(batch_id: str) -> dict:
        """Flag samples whose internal standard (IS) area is below 50 % or above 150 % of the mean IS area of the
        batch calibrators and QCs. batch_id is like 'B01'."""
        return _unknown(data, batch_id) or internal_standard(data, batch_id)

    def check_ion_ratio(batch_id: str) -> dict:
        """Flag samples whose qualifier/quantifier ion ratio differs by more than ±20 % from the calibrator mean
        ratio (possible interference). batch_id is like 'B01'."""
        return _unknown(data, batch_id) or ion_ratio(data, batch_id)

    def apply_westgard(batch_id: str) -> dict:
        """Apply the Westgard rules 1-3s, 2-2s, R-4s, 4-1s and 10-x to the 3 QC levels of a batch, using the
        established QC targets and the previous runs. batch_id is like 'B01'."""
        return _unknown(data, batch_id) or westgard(data, batch_id)

    def draft_deviation(batch_id: str, status: str, findings: str, samples_on_hold: str) -> dict:
        """Draft a deviation note for the laboratory supervisor to review and approve. Nothing is released or
        rejected by this tool. status is PASS, HOLD or ESCALATE; findings lists each flag with the tool that found
        it; samples_on_hold is a comma-separated list of sample ids, or 'none'."""
        err = _unknown(data, batch_id)
        if err:
            return err
        note = (f"DEVIATION NOTE (DRAFT) — batch {batch_id}\nProposed status: {status}\nFindings: {findings}\n"
                f"Samples on hold: {samples_on_hold}\nAction required: supervisor review and approval. "
                "No result has been released or rejected by the agent.")
        return {"batch_id": batch_id, "draft": note, "requires_human_approval": True}

    return {f.__name__: f for f in (check_calibration, check_internal_standard, check_ion_ratio, apply_westgard,
                                    draft_deviation)}


_STATUS = re.compile(r"status\s*[:\-–]?\s*\**\s*(pass|hold|escalate)\b", re.I)
_HOLD = re.compile(r"samples? on hold\s*[:\-–]\s*(.+)", re.I)


def parse_status(text: str) -> tuple[str, list[str]]:
    """Read 'STATUS: …' and 'SAMPLES ON HOLD: …' from the agent's report."""
    m = _STATUS.search(text or "")
    status = m.group(1).upper() if m else ""
    h = _HOLD.search(text or "")
    samples = re.findall(r"B\d{2}-S\d{2}", h.group(1)) if h else []
    return status, samples
