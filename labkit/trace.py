"""Turn ADK events into readable 'trace cards' so participants can see what the agent did."""

from __future__ import annotations

import html
import json

_STYLE = ("border-radius:8px;padding:8px 12px;margin:6px 0;font-family:sans-serif;"
          "font-size:14px;line-height:1.45;border:1px solid {b};background:{bg};color:#1f1f1f")
_KINDS = {
    "call": ("🔧", "Calls tool", "#8ab4f8", "#e8f0fe"),
    "result": ("📄", "Tool result", "#a8c7a0", "#eef6ec"),
    "think": ("🧠", "Model says", "#d3d3d3", "#f6f6f6"),
    "final": ("✅", "Final answer", "#81c995", "#e6f4ea"),
}


def _short(value, limit: int = 300) -> str:
    text = value if isinstance(value, str) else json.dumps(value, ensure_ascii=False, default=str)
    return text if len(text) <= limit else text[:limit] + " …"


def _card(kind: str, body: str) -> str:
    icon, label, border, bg = _KINDS[kind]
    return (f"<div style='{_STYLE.format(b=border, bg=bg)}'><b>{icon} {label}</b>"
            f"<div style='white-space:pre-wrap;margin-top:4px'>{body}</div></div>")


def trace_html(events) -> str:
    """Build the HTML for all events: tool calls, tool results, model text; last text is the final answer."""
    items: list[tuple[str, str]] = []
    for ev in events:
        content = getattr(ev, "content", None)
        for part in (getattr(content, "parts", None) or []):
            if getattr(part, "function_call", None):
                fc = part.function_call
                items.append(("call", f"<code>{html.escape(fc.name)}</code>  {html.escape(_short(dict(fc.args or {})))}"))
            elif getattr(part, "function_response", None):
                fr = part.function_response
                items.append(("result", f"<code>{html.escape(fr.name)}</code> → {html.escape(_short(fr.response))}"))
            elif getattr(part, "text", None) and not getattr(part, "thought", False):
                items.append(("think", html.escape(part.text.strip())))
    for i in range(len(items) - 1, -1, -1):
        if items[i][0] == "think":
            items[i] = ("final", items[i][1])
            break
    return "".join(_card(k, b) for k, b in items) or "<i>No events.</i>"


def trace_cards(events):
    from IPython.display import HTML

    return HTML(trace_html(events))
