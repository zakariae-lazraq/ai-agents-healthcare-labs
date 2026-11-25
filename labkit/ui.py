"""Small display helpers for participant tasks: checks, copy boxes, completion cards, guards.

Visual style: sober text labels (OK / FIX / MISSING) and the course palette — no emoji.
"""

from __future__ import annotations

import html

import labkit

BLANK = "___"

# Course palette (same as the figures)
NAVY, TEAL, AMBER, RED, GREEN, GREY = "#1F3A5F", "#2A7F7F", "#B7791F", "#B3261E", "#1E7A3C", "#5F6B7A"
FONT = "font-family:Inter,Segoe UI,Roboto,Helvetica,Arial,sans-serif"


def badge(text: str, color: str) -> str:
    return (f"<span style='display:inline-block;min-width:58px;text-align:center;padding:1px 6px;"
            f"margin-right:8px;border:1px solid {color};border-radius:4px;color:{color};"
            f"font-size:11px;font-weight:700;letter-spacing:.04em'>{html.escape(text)}</span>")


def check_html(items, optional: bool = False) -> str:
    rows = []
    for ok, what, fix in items:
        if ok:
            line = badge("OK", GREEN) + html.escape(what)
        else:
            tag = badge("MISSING", AMBER) if optional else badge("FIX", RED)
            color = AMBER if optional else RED
            line = (tag + f"<b>{html.escape(what)}</b><div style='margin:2px 0 0 74px;color:{color}'>"
                    f"How to fix: {html.escape(fix)}</div>")
        rows.append(f"<div style='margin:5px 0'>{line}</div>")
    all_ok = all(ok for ok, _, _ in items)
    if all_ok:
        footer, color = "All good — continue.", GREEN
    elif optional:
        footer, color = "Missing items are optional — tell the trainer and continue: every lab still works.", AMBER
    else:
        footer, color = "Fix the red lines, then run this cell again.", RED
    return (f"<div style='{FONT};font-size:14px;line-height:1.5'>{''.join(rows)}"
            f"<div style='margin-top:8px;font-weight:600;color:{color}'>{footer}</div></div>")


def check(items, optional: bool = False) -> bool:
    """items: list of (ok, what_is_checked, how_to_fix_if_wrong). Shows OK/FIX lines; returns all ok."""
    from IPython.display import HTML, display

    display(HTML(check_html(items, optional)))
    return all(ok for ok, _, _ in items)


def has_blank(*values) -> str | None:
    """Return a message if any value is still a blank (___ , ... or empty), else None."""
    for v in values:
        if v is Ellipsis or v is None:
            return "Something is still empty: replace every ___ with your answer."
        if isinstance(v, str) and (not v.strip() or BLANK in v):
            return "There is still a ___ to fill in: replace every ___ with your answer."
    return None


def ready(name: str, instruction: str, tools: list) -> bool:
    """True if an agent can be built from these values; otherwise shows one 'Action needed' line."""
    from IPython.display import display

    problem = has_blank(name, instruction)
    if problem is None and (not isinstance(tools, list) or not tools
                            or not all(callable(t) for t in tools)):
        problem = ("TOOLS must contain the tool function itself, e.g. TOOLS = [get_test_info] "
                   "— no quotation marks, no ().")
    if problem:
        display(error_line(problem + " Then run this cell again."))
        return False
    return True


SETUP_NOT_PASSED = ("Setup has not passed yet: scroll up to the Setup cell, fix the red lines, "
                    "run it again — then run this cell.")


def require_setup() -> None:
    if not labkit._state.get("setup_ok"):
        raise RuntimeError(SETUP_NOT_PASSED)


def error_line(message: str):
    """A clear 'action needed' box for participant-facing problems (instead of a traceback)."""
    from IPython.display import HTML

    return HTML(f"<div style='{FONT};font-size:14px;border-left:4px solid {RED};padding:6px 12px;"
                f"margin:6px 0;color:{RED}'><b>Action needed.</b> {html.escape(message)}</div>")


def copy_box(text: str, title: str = "Copy this"):
    from IPython.display import HTML

    safe = html.escape(text)
    return HTML(
        f"<div style='{FONT};border:1px solid #C9D2DC;border-radius:6px;padding:8px 12px;margin:6px 0'>"
        f"<b style='color:{NAVY}'>{html.escape(title)}</b> "
        "<button onclick=\"navigator.clipboard.writeText(this.parentElement.querySelector('pre').innerText);"
        "this.innerText='Copied'\" style='margin-left:8px'>Copy</button>"
        f"<pre style='white-space:pre-wrap;margin:6px 0 0'>{safe}</pre></div>")


def done_card(lab: str, items: list[str], complete: bool | None = None, complete_text: str = "Complete"):
    """Completion/status card. With complete=None the title is '<lab> complete' (legacy);
    with complete=True/False the title is <lab> and a coloured verdict line is added."""
    from IPython.display import HTML

    lis = "".join(f"<li style='margin:2px 0'>{html.escape(i)}</li>" for i in items)
    if complete is None:
        title, verdict, top = f"{lab} complete", "", TEAL
    else:
        title = lab
        top = TEAL if complete else RED
        verdict = (f"<div style='font-weight:700;color:{GREEN if complete else RED};margin-top:4px'>"
                   f"{complete_text if complete else 'Not complete yet — fix the lines marked FIX'}</div>")
    return HTML(
        f"<div style='{FONT};border:1px solid #C9D2DC;border-top:6px solid {top};border-radius:6px;"
        "padding:14px 20px;max-width:620px;background:#FFFFFF;color:#1B2430'>"
        f"<div style='font-size:19px;font-weight:700;color:{NAVY}'>{html.escape(title)}</div>{verdict}"
        f"<ul style='margin:10px 0 10px 18px;padding:0'>{lis}</ul>"
        f"<div style='color:{GREY};font-size:13px'>Take a screenshot of this card and post it in the course chat.</div>"
        "</div>")
