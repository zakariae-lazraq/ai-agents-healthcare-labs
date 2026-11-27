"""Lab 5: an interoperability agent, FHIR Observations, LOINC coding, units, critical values, a draft report.

Checks are per patient (the agent can call them in parallel). Values are never changed: the drafted
DiagnosticReport only references the source Observations, and validate_report() proves it.
"""

from __future__ import annotations

import csv
import json
import re
from pathlib import Path


class FhirLab:
    def __init__(self, folder):
        folder = Path(folder)
        self.resources = json.loads((folder / "resources.json").read_text(encoding="utf-8"))
        self.by_id = {(r["resourceType"], r["id"]): r for r in self.resources}
        with open(folder / "loinc_table.csv", encoding="utf-8") as f:
            self.loinc = {r["code"]: r for r in csv.DictReader(f)}
        with open(folder / "critical_values.csv", encoding="utf-8") as f:
            self.critical = {r["code"]: r for r in csv.DictReader(f)}
        self.previous = json.loads((folder / "previous_results.json").read_text(encoding="utf-8"))
        self.patients = [r["id"] for r in self.resources if r["resourceType"] == "Patient"]
        self.mrns = {r["id"]: r["identifier"][0]["value"] for r in self.resources if r["resourceType"] == "Patient"}
        self.notifications: list[dict] = []
        self.drafts: dict[str, dict] = {}

    def observations(self, pid: str) -> list[dict]:
        return [r for r in self.resources if r["resourceType"] == "Observation"
                and r["subject"]["reference"] == f"Patient/{pid}"]

    def requests(self, pid: str) -> list[dict]:
        return [r for r in self.resources if r["resourceType"] == "ServiceRequest"
                and r["subject"]["reference"] == f"Patient/{pid}"]


def load(folder) -> FhirLab:
    return FhirLab(folder)


def _summary(o: dict) -> dict:
    q = o.get("valueQuantity", {})
    c = o["code"]["coding"][0]
    return {"observation_id": o["id"], "loinc_code": c["code"], "test_name": o["code"].get("text", ""),
            "value": q.get("value"), "unit": q.get("unit"), "request": o["basedOn"][0]["reference"]}


def coding_problems(lab: FhirLab, pid: str) -> list[dict]:
    out = []
    for o in lab.observations(pid):
        s = _summary(o)
        ref = lab.loinc.get(s["loinc_code"])
        if ref is None:
            out.append({**s, "issue": f"LOINC code {s['loinc_code']} not in the laboratory's table"})
        elif ref["short_name"].lower() != s["test_name"].lower():
            out.append({**s, "issue": f"test name '{s['test_name']}' but LOINC {s['loinc_code']} is "
                                      f"'{ref['short_name']}' ({ref['long_name']})"})
    return out


def unit_problems(lab: FhirLab, pid: str) -> list[dict]:
    out = []
    for o in lab.observations(pid):
        s = _summary(o)
        ref = lab.loinc.get(s["loinc_code"])
        if not s["unit"]:
            out.append({**s, "issue": "unit missing, the value cannot be interpreted"})
            continue
        if ref is None or ref["short_name"].lower() != s["test_name"].lower():
            continue   # a coding problem: reported by check_coding, not judged here
        if s["unit"] != ref["unit"]:
            out.append({**s, "issue": f"unit {s['unit']} but LOINC {s['loinc_code']} expects {ref['unit']}"})
        elif not float(ref["plausible_low"]) <= float(s["value"]) <= float(ref["plausible_high"]):
            hint = ""
            if s["loinc_code"] == "2345-7" and float(s["value"]) < 50:
                hint = f": looks like mmol/L (≈ {round(float(s['value']) * 18)} mg/dL)"
            out.append({**s, "issue": f"value {s['value']} {s['unit']} implausible for {ref['short_name']}{hint}"})
    return out


def critical_results(lab: FhirLab, pid: str) -> list[dict]:
    out = []
    for o in lab.observations(pid):
        s = _summary(o)
        c = lab.critical.get(s["loinc_code"])
        ref = lab.loinc.get(s["loinc_code"])
        if not c or s["value"] is None or not s["unit"] or (ref and ref["short_name"].lower() != s["test_name"].lower()):
            continue
        lo = float(c["critical_low"]) if c["critical_low"] else None
        hi = float(c["critical_high"]) if c["critical_high"] else None
        v = float(s["value"])
        if not (ref and float(ref["plausible_low"]) <= v <= float(ref["plausible_high"])):
            if (lo is not None and v < lo) or (hi is not None and v > hi):
                out.append({**s, "critical_range": f"< {lo} or > {hi}" if hi else f"< {lo}", "rule": "SOP-03 §2",
                            "possible": True, "issue": "possible critical value, unit/coding inconsistent: "
                            "confirm with the laboratory before calling it critical"})
            continue
        if (lo is not None and v < lo) or (hi is not None and v > hi):
            out.append({**s, "critical_range": f"< {lo} or > {hi}" if hi else f"< {lo}", "rule": "SOP-03 §2"})
    return out


def duplicates(lab: FhirLab, pid: str) -> list[dict]:
    seen, out = {}, []
    for o in lab.observations(pid):
        s = _summary(o)
        k = (s["loinc_code"], s["test_name"], s["request"])
        if k in seen:
            out.append({"observation_ids": [seen[k], s["observation_id"]], "loinc_code": s["loinc_code"],
                        "request": s["request"], "issue": "two results for the same test and request"})
        else:
            seen[k] = s["observation_id"]
    return out


def delta_problems(lab: FhirLab, pid: str, limit_pct: float = 50) -> list[dict]:
    """Challenge reference: change since the previous result above limit_pct %."""
    out = []
    for o in lab.observations(pid):
        s = _summary(o)
        prev = lab.previous.get(pid, {}).get(s["loinc_code"])
        if prev and s["value"] is not None:
            change = (float(s["value"]) - prev["value"]) / prev["value"] * 100
            if abs(change) > limit_pct:
                out.append({**s, "previous": prev, "change_pct": round(change)})
    return out


def reference_status(lab: FhirLab, pid: str) -> tuple[str, list[str]]:
    if [c for c in critical_results(lab, pid) if not c.get("possible")]:
        return "ESCALATE", ["critical value"]
    found = [("coding", coding_problems(lab, pid)), ("units", unit_problems(lab, pid)),
             ("duplicate", duplicates(lab, pid))]
    reasons = [k for k, v in found if v]
    return ("HOLD", reasons) if reasons else ("PASS", [])


VALID_DRAFT_STATUS = "preliminary"


def validate_report(lab: FhirLab, report: dict) -> list[str]:
    """FHIR structure (fhir.resources) + course rules: preliminary only, references exist."""
    problems = []
    try:
        from fhir.resources.diagnosticreport import DiagnosticReport

        DiagnosticReport.model_validate(report)
    except ImportError:
        problems.append("fhir.resources is not installed (run the setup cell)")
    except Exception as exc:
        problems.append("not valid FHIR: " + str(exc).splitlines()[0][:200])
    if report.get("status") != VALID_DRAFT_STATUS:
        problems.append(f"status must be '{VALID_DRAFT_STATUS}': a draft is never final before human review")
    for ref in report.get("result", []):
        rid = ref.get("reference", "").split("/")[-1]
        if ("Observation", rid) not in lab.by_id:
            problems.append(f"result {ref.get('reference')} does not exist")
    return problems


def integrity_problems(lab: FhirLab) -> list[str]:
    """Real integrity check: every number in a drafted conclusion must be a source value of that patient."""
    out = []
    for pid, d in lab.drafts.items():
        for r in d["result"]:
            if ("Observation", r["reference"].split("/")[-1]) not in lab.by_id:
                out.append(f"{pid}: reference {r['reference']} does not exist")
        src = {round(float(o["valueQuantity"]["value"]), 2) for o in lab.observations(pid)
               if o.get("valueQuantity", {}).get("value") is not None}
        for m in re.findall(r"(?<![\w.-])(\d+(?:\.\d+)?)(?![\w.])", d.get("conclusion", "")):
            v = round(float(m), 2)
            if v not in src and not any(abs(v - x * 18) < 1 or abs(v - x / 18) < .05 for x in src) and v not in (
                    2, 3, 6.2, 2.5, 50):
                out.append(f"{pid}: conclusion mentions {m}, which is not a source value")
    return out


def make_fhir_tools(lab: FhirLab) -> dict:
    def _unknown(pid):
        if pid not in lab.patients:
            return {"status": "error", "message": f"Unknown patient '{pid}'. Valid ids: pat-01 … pat-20."}
        return None

    def get_observations(patient_id: str) -> dict:
        """List a patient's laboratory Observations (FHIR): id, LOINC code, test name, value, unit, request.
        patient_id is like 'pat-01'."""
        return _unknown(patient_id) or {"patient_id": patient_id, "mrn": lab.mrns[patient_id],
                                        "observations": [_summary(o) for o in lab.observations(patient_id)]}

    def lookup_loinc(code: str) -> dict:
        """Look up a LOINC code in the laboratory's LOINC table: name and expected unit."""
        r = lab.loinc.get(code)
        return {"status": "unknown", "code": code} if r is None else {"status": "found", **{
            k: r[k] for k in ("code", "short_name", "long_name", "unit")}}

    def check_coding(patient_id: str) -> dict:
        """Check that every Observation's LOINC code matches its test name. Problems mean HOLD."""
        return _unknown(patient_id) or {"patient_id": patient_id, "problems": coding_problems(lab, patient_id)}

    def check_units(patient_id: str) -> dict:
        """Check every Observation's unit: present, as expected for its LOINC code, and plausible for the test.
        Problems mean HOLD."""
        return _unknown(patient_id) or {"patient_id": patient_id, "problems": unit_problems(lab, patient_id)}

    def check_critical(patient_id: str) -> dict:
        """Check every Observation against the critical value list (SOP-03 §2). A critical value means ESCALATE
        and notify_human."""
        return _unknown(patient_id) or {"patient_id": patient_id, "critical": critical_results(lab, patient_id)}

    def check_duplicates(patient_id: str) -> dict:
        """Find two results for the same test and the same request. Duplicates mean HOLD."""
        return _unknown(patient_id) or {"patient_id": patient_id, "duplicates": duplicates(lab, patient_id)}

    def draft_diagnostic_report(patient_id: str, conclusion: str) -> dict:
        """Draft a FHIR DiagnosticReport (status 'preliminary') that references the patient's Observations and
        carries your short conclusion. Values are referenced, never copied or changed. For human review only."""
        err = _unknown(patient_id)
        if err:
            return err
        req = lab.requests(patient_id)[0]
        report = {"resourceType": "DiagnosticReport", "id": f"dr-{patient_id}", "status": VALID_DRAFT_STATUS,
                  "category": [{"coding": [{"system": "http://terminology.hl7.org/CodeSystem/v2-0074", "code": "LAB"}]}],
                  "code": {"coding": [{"system": "http://loinc.org", "code": "11502-2",
                           "display": "Laboratory report"}], "text": "Laboratory report"}, "subject": {"reference": f"Patient/{patient_id}"},
                  "basedOn": [{"reference": f"ServiceRequest/{req['id']}"}], "issued": "2026-11-23T11:00:00+01:00",
                  "result": [{"reference": f"Observation/{o['id']}"} for o in lab.observations(patient_id)],
                  "conclusion": conclusion}
        lab.drafts[patient_id] = report
        return {"patient_id": patient_id, "report": report, "requires_human_review": True}

    def notify_human(patient_id: str, message: str, urgency: str) -> dict:
        """Call ONLY for a confirmed critical value. Notify the responsible person (for a critical value: the clinician, by telephone, with read-back, per
        SOP-03). urgency is 'urgent' or 'routine'. The notification is recorded."""
        err = _unknown(patient_id)
        if err:
            return err
        lab.notifications.append({"patient_id": patient_id, "mrn": lab.mrns[patient_id], "message": message,
                                  "urgency": urgency})
        return {"status": "recorded", "patient_id": patient_id, "urgency": urgency}

    return {f.__name__: f for f in (get_observations, lookup_loinc, check_coding, check_units, check_critical,
                                    check_duplicates, draft_diagnostic_report, notify_human)}


def parse_status(text: str) -> str:
    from labkit.status import parse_status as _ps

    return _ps(text, ("PASS", "HOLD", "ESCALATE"))


def run_patients(agent, patient_ids: list[str], show_progress: bool = True, concurrency: int = 1,
                 previous: list[dict] | None = None) -> list[dict]:
    from labkit.batch import run_many

    done = {r["patient_id"]: r for r in (previous or []) if r.get("status") and not r.get("note")}
    todo = [p for p in patient_ids if p not in done]
    res = run_many(agent, [f"Review the laboratory results of patient {p}." for p in todo],
                   show_progress=show_progress, concurrency=concurrency) if todo else []
    from labkit.status import all_model_text

    new = [{"patient_id": p, "status": parse_status(all_model_text(r.events) or r.text), "tools": list(r.tool_calls), "text": r.text,
             "note": r.message or r.note} for p, r in zip(todo, res)]
    by_id = {**done, **{n["patient_id"]: n for n in new}}
    return [by_id[p] for p in patient_ids]


def scoreboard_html(rows: list[dict], key: dict, notifications: list[dict]) -> tuple[str, int, bool]:
    """Agent status per patient vs the answer key; and: were exactly the critical patients notified?"""
    import html as _h

    td = "padding:4px 10px;text-align:left;vertical-align:top"
    notified = {n["patient_id"] for n in notifications if str(n.get("urgency", "")).lower() == "urgent"}
    ids = {r["patient_id"] for r in rows if r["status"]}
    should = {p for p, k in key.items() if k["notify"] and p in ids}
    body, right = "", 0
    for r in rows:
        k = key[r["patient_id"]]
        notrun = not r["status"] and bool(r["note"])
        ok = r["status"] == k["status"]
        right += ok
        body += (f"<tr style='border-top:1px solid #C9D2DC'><td style='{td}'><b>{r['patient_id']}</b></td>"
                 f"<td style='{td}'>{k['status']}<br><span style='color:#5F6B7A;font-size:12px'>"
                 f"{_h.escape('; '.join(k['issues']) or 'clean')}</span></td>"
                 f"<td style='{td}'>{_h.escape(r['status'] or '-')}"
                 + (f"<br><span style='color:#B7791F;font-size:12px'>{_h.escape(r['note'])}</span>" if r["note"] else "")
                 + f"</td><td style='{td}'>{'notified' if r['patient_id'] in notified else ''}</td>"
                 f"<td style='{td};color:{'#1E7A3C' if ok else ('#5F6B7A' if notrun else '#B3261E')}'><b>"
                 f"{'right' if ok else ('not run' if notrun else 'wrong')}</b></td></tr>")
    notify_ok = notified == should
    from labkit.qc import _notrun_note, _ran

    foot = (f"<b>{right} / {_ran(rows)}</b> statuses right{_notrun_note(rows)} · notifications: "
            + ("exactly the critical patient(s)" if notify_ok else
               f"<span style='color:#B3261E'>expected {sorted(should)}, got {sorted(notified)}</span>"))
    html = ("<table style='border-collapse:collapse;font-family:Inter,Segoe UI,Roboto,sans-serif;font-size:13px'>"
            f"<tr><th style='{td}'>Patient</th><th style='{td}'>Answer key</th><th style='{td}'>Agent</th>"
            f"<th style='{td}'>Notification</th><th style='{td}'>Result</th></tr>{body}"
            f"<tr style='border-top:2px solid #1F3A5F'><td style='{td}' colspan='5'>{foot}</td></tr></table>")
    return html, right, notify_ok


HL7_FIELDS = {
    "MSH": {9: "message type (ORU^R01 = observation result)", 10: "message control id", 12: "HL7 version"},
    "PID": {3: "patient identifier (MRN)", 5: "patient name"},
    "OBR": {2: "placer order number (the request)", 4: "ordered test (LOINC)", 7: "collection date/time"},
    "OBX": {2: "value type (NM = numeric)", 3: "test code (LOINC)", 5: "value", 6: "unit (UCUM)",
            7: "reference range", 8: "abnormal flag (HH = critically high)", 11: "result status (F = final)"},
}


def hl7_guide_html(message: str) -> str:
    """Each segment of an HL7 v2 message, with the meaning of its important fields."""
    import html as _h

    td = "padding:3px 10px;text-align:left;vertical-align:top;font-size:12px"
    rows = ""
    for seg in [s for s in message.replace("\n", "\r").split("\r") if s.strip()]:
        f = seg.split("|")
        name = f[0]
        for i, meaning in HL7_FIELDS.get(name, {}).items():
            idx = i - 1 if name == "MSH" else i   # MSH-1 is the field separator itself
            if idx < len(f) and f[idx]:
                rows += (f"<tr style='border-top:1px solid #C9D2DC'><td style='{td}'><b>{name}-{i}</b></td>"
                         f"<td style='{td};font-family:monospace'>{_h.escape(f[idx])}</td><td style='{td}'>{meaning}</td></tr>")
    return ("<table style='border-collapse:collapse;font-family:Inter,Segoe UI,Roboto,sans-serif'>"
            f"<tr><th style='{td}'>Field</th><th style='{td}'>Content</th><th style='{td}'>Meaning</th></tr>{rows}</table>")
