"""Read the fixed ending lines that agents write ('STATUS: …', 'SAMPLES ON HOLD: …', 'VERDICT: …').

Robust to what real models do: per-check lines before the final one (the LAST status line wins), markdown
(**Status**: HOLD), a closing sentence after the report (read every model text of the run), sample lists on
following lines, and ranges such as 'B04-S11 to B04-S15'.
"""

from __future__ import annotations

import re


def all_model_text(events) -> str:
    """Every text the model wrote during one run, in order (not only the last one)."""
    out = []
    for ev in events or []:
        content = getattr(ev, "content", None)
        if getattr(content, "role", "model") != "model":
            continue
        for part in getattr(content, "parts", None) or []:
            if getattr(part, "text", None) and not getattr(part, "thought", False):
                out.append(part.text)
    return "\n".join(out)


def parse_status(text: str, allowed: tuple[str, ...], word: str = "status") -> str:
    """The last line of the form '<word>: X' with X in allowed (case-insensitive, markdown tolerated)."""
    alts = "|".join(re.escape(a.lower()) for a in allowed)
    rx = re.compile(rf"(?im)^[\W_]*{word}[\W_]*({alts})\b")
    found = rx.findall(text or "")
    return found[-1].upper() if found else ""


def parse_samples(text: str, id_pattern: str, label: str = "samples? on hold") -> list[str]:
    """Ids listed after the last '<label>:' up to a blank line; 'X to Y' ranges are expanded."""
    m = list(re.finditer(rf"(?i){label}[\W_]*[:\-–]", text or ""))
    if not m:
        return []
    block = re.split(r"\n\s*\n", (text or "")[m[-1].end():], maxsplit=1)[0]
    ids = []
    for a, b in re.findall(rf"({id_pattern})[ 	]*(?:to|through|–)[ 	]*({id_pattern})", block):
        pa, na = re.match(r"(.*?)(\d+)$", a).groups()
        pb, nb = re.match(r"(.*?)(\d+)$", b).groups()
        if pa == pb:
            ids += [f"{pa}{n:0{len(na)}d}" for n in range(int(na), int(nb) + 1)]
    for i in re.findall(id_pattern, block):
        if i not in ids:
            ids.append(i)
    return sorted(set(ids))
