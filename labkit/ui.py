"""Small display helpers for participant tasks: checks, copy boxes, completion cards, guards."""

from __future__ import annotations

import html

import labkit

BLANK = "___"


def check_html(items) -> str:
    rows = []
    for ok, what, fix in items:
        line = f"✅ {html.escape(what)}" if ok else (
            f"❌ {html.escape(what)} — <span style='color:#b3261e'>👉 {html.escape(fix)}</span>")
        rows.append(f"<div style='margin:3px 0'>{line}</div>")
    all_ok = all(ok for ok, _, _ in items)
    footer = "🎉 All good — continue." if all_ok else "Fix the ❌ lines and run this cell again."
    return (f"<div style='font-family:sans-serif;font-size:14px'>{''.join(rows)}"
            f"<p><b>{footer}</b></p></div>")


def check(items) -> bool:
    """items: list of (ok, what_is_checked, how_to_fix_if_wrong). Shows ✅/❌ lines; returns all ok."""
    from IPython.display import HTML, display

    display(HTML(check_html(items)))
    return all(ok for ok, _, _ in items)


def has_blank(*values) -> str | None:
    """Return a message if any value is still a blank (___ , ... or empty), else None."""
    for v in values:
        if v is Ellipsis or v is None:
            return "Something is still empty: replace every ___ with your answer."
        if isinstance(v, str) and (not v.strip() or BLANK in v):
            return "There is still a ___ to fill in: replace every ___ with your answer."
    return None


def require_setup() -> None:
    if not labkit._state.get("setup_ok"):
        raise RuntimeError("Run the Setup cell (step 1) first, then this cell again.")


def copy_box(text: str, title: str = "Copy this"):
    from IPython.display import HTML

    safe = html.escape(text)
    return HTML(
        "<div style='font-family:sans-serif;border:1px solid #c4c7c5;border-radius:8px;padding:8px 12px;margin:6px 0'>"
        f"<b>{html.escape(title)}</b> "
        "<button onclick=\"navigator.clipboard.writeText(this.parentElement.querySelector('pre').innerText);"
        "this.innerText='Copied ✓'\" style='margin-left:8px'>Copy</button>"
        f"<pre style='white-space:pre-wrap;margin:6px 0 0'>{safe}</pre></div>")


def done_card(lab: str, items: list[str]):
    from IPython.display import HTML

    lis = "".join(f"<li>{html.escape(i)}</li>" for i in items)
    return HTML(
        "<div style='font-family:sans-serif;border:2px solid #34a853;border-radius:12px;padding:14px 18px;"
        "background:#e6f4ea;color:#0d652d'>"
        f"<div style='font-size:20px;font-weight:bold'>{html.escape(lab)} complete ✅</div>"
        f"<ul>{lis}</ul>"
        "<div>📸 Take a screenshot of this card and post it in the chat.</div></div>")
