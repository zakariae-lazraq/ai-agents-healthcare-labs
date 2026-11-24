"""Turn ADK events into readable 'trace cards' so participants can see what the agent did."""

from __future__ import annotations

import html
import json

_STYLE = ("padding:7px 12px;margin:6px 0;font-family:Inter,Segoe UI,Roboto,Helvetica,Arial,sans-serif;"
          "font-size:14px;line-height:1.45;border-left:4px solid {b};background:{bg};color:#1B2430")
_KINDS = {  # label, border colour, background — same palette as the course figures
    "call": ("TOOL CALL", "#1F3A5F", "#F2F5F9"),
    "result": ("TOOL RESULT", "#2A7F7F", "#F0F7F7"),
    "think": ("MODEL", "#8A96A3", "#F7F8FA"),
    "final": ("ANSWER", "#1F3A5F", "#FFFFFF"),
}


def _markdown_lite(text: str) -> str:
    """Render the little markdown models use (**bold**, *italic*, bullet lists) safely: escape first."""
    import re

    out, in_list = [], False
    for line in html.escape(text).splitlines():
        m = re.match(r"^\s*[*-]\s+(.*)$", line)
        if m:
            if not in_list:
                out.append("<ul style='margin:4px 0 4px 18px;padding:0'>")
                in_list = True
            out.append(f"<li>{m.group(1)}</li>")
            continue
        if in_list:
            out.append("</ul>")
            in_list = False
        out.append(line + "<br>")
    if in_list:
        out.append("</ul>")
    body = "".join(out)
    body = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", body)
    body = re.sub(r"(?<![\w*])\*(?!\s)(.+?)(?<!\s)\*(?![\w*])", r"<i>\1</i>", body)
    return body.removesuffix("<br>")


def _short(value, limit: int = 300) -> str:
    text = value if isinstance(value, str) else json.dumps(value, ensure_ascii=False, default=str)
    return text if len(text) <= limit else text[:limit] + " …"


def _card(kind: str, body: str) -> str:
    label, border, bg = _KINDS[kind]
    return (f"<div style='{_STYLE.format(b=border, bg=bg)}'>"
            f"<span style='font-size:11px;font-weight:700;letter-spacing:.06em;color:{border}'>{label}</span>"
            f"<div style='margin-top:4px'>{body}</div></div>")


def _value_html(value) -> str:
    if isinstance(value, dict):
        return "; ".join(f"{html.escape(str(k))}: {html.escape(str(v))}" for k, v in value.items())
    if isinstance(value, list):
        return html.escape(", ".join(str(v) for v in value))
    return html.escape(str(value))


def _result_table(response) -> str:
    """Tool results in full, as a key/value table — participants verify numbers against it."""
    if not isinstance(response, dict):
        return html.escape(json.dumps(response, ensure_ascii=False, default=str))
    rows = "".join(
        f"<tr><td style='padding:2px 12px 2px 0;color:#5F6B7A;vertical-align:top;text-align:left;"
        f"white-space:nowrap'>{html.escape(str(k))}</td><td style='padding:2px 0;text-align:left'>"
        f"{_value_html(v)}</td></tr>" for k, v in response.items())
    return f"<table style='border-collapse:collapse;margin-top:2px'>{rows}</table>"


def trace_html(events) -> str:
    """Build the HTML for all events: tool calls, tool results, model text; last text is the final answer.

    Text parts of one event are joined first: Gemini may split one answer across several parts.
    """
    items: list[tuple[str, str]] = []
    for ev in events:
        content = getattr(ev, "content", None)
        text_buf: list[str] = []
        for part in (getattr(content, "parts", None) or []):
            if getattr(part, "function_call", None):
                fc = part.function_call
                items.append(("call", f"<code>{html.escape(fc.name)}</code>  {html.escape(_short(dict(fc.args or {})))}"))
            elif getattr(part, "function_response", None):
                fr = part.function_response
                items.append(("result", f"<code>{html.escape(fr.name)}</code>{_result_table(fr.response)}"))
            elif getattr(part, "text", None) and not getattr(part, "thought", False):
                text_buf.append(part.text)
        if "".join(text_buf).strip():
            items.append(("think", _markdown_lite("".join(text_buf).strip())))
    for i in range(len(items) - 1, -1, -1):
        if items[i][0] == "think":
            items[i] = ("final", items[i][1])
            break
    return "".join(_card(k, b) for k, b in items) or "<i>No events.</i>"


def trace_cards(events):
    from IPython.display import HTML

    return HTML(trace_html(events))
