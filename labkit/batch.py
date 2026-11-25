"""Run one agent on many questions, and show several agents side by side."""

from __future__ import annotations

import html

from labkit import agents
from labkit.trace import _markdown_lite

FONT = "font-family:Inter,Segoe UI,Roboto,Helvetica,Arial,sans-serif;font-size:13px"


def run_many(agent, questions: list[str], show_progress: bool = True, saved: dict | None = None,
             concurrency: int = 3) -> list:
    """Ask each question in a fresh conversation, a few in parallel; return RunResults in question order.

    If Gemini cannot answer a question (busy, quota) and `saved` holds a recorded answer for it,
    the recorded answer is used and labelled in `.note` — never silently.
    """
    import asyncio

    handle = None
    if show_progress:
        from IPython.display import HTML, display
        handle = display(HTML(f"<i style='{FONT};color:#5F6B7A'>Asking {len(questions)} questions…</i>"),
                         display_id=True)
    done = [0]

    async def one(q, sem):
        async with sem:
            r = await agents.arun(agent, q)
        done[0] += 1
        if handle:
            handle.update(HTML(f"<i style='{FONT};color:#5F6B7A'>{done[0]} of {len(questions)} answered…</i>"))
        return r

    async def all_():
        sem = asyncio.Semaphore(concurrency)
        return await asyncio.gather(*(one(q, sem) for q in questions))

    with agents._quiet_adk_logs():
        results = list(agents._run_coro(all_()))
    used_saved = 0
    for i, (q, r) in enumerate(zip(questions, results)):
        if r.message and saved and q in saved:
            results[i] = agents.RunResult(saved[q], [], [], "", note="saved answer (Gemini was not available)")
            used_saved += 1
    if handle:
        extra = f" — {used_saved} from saved answers" if used_saved else ""
        handle.update(HTML(f"<i style='{FONT};color:#5F6B7A'>{len(questions)} questions answered{extra}.</i>"))
    return results


FOLD_AT = 600  # characters shown before "Show full answer"


def _answer_html(text: str) -> str:
    """Long answers are folded so the 12-row table stays scannable."""
    if len(text) <= FOLD_AT + 100:
        return _markdown_lite(text)
    cut = text[:FOLD_AT]
    cut = cut[:max(cut.rfind(" "), FOLD_AT // 2)] + " …"
    return (f"{_markdown_lite(cut)}<details style='margin-top:4px'><summary style='cursor:pointer;color:#2A7F7F;"
            f"font-size:12px'>Show full answer ({len(text)} characters)</summary>{_markdown_lite(text)}</details>")


def side_by_side(questions: list[dict], results: dict[str, list]) -> str:
    """HTML table: one row per question, one column per agent (answer + tools used)."""
    names = list(results)
    width = 76 // max(1, len(names))
    head = "".join(f"<th style='padding:6px 10px;text-align:left;width:{width}%'>{html.escape(n)}</th>"
                   for n in names)
    rows = []
    for i, q in enumerate(questions):
        cells = ""
        for n in names:
            r = results[n][i]
            body = _answer_html(r.text) if r.text else f"<i>{html.escape(r.message or 'no answer')}</i>"
            tools = (f"<div style='color:#2A7F7F;font-size:11px;margin-top:4px'>tool used: "
                     f"{html.escape(', '.join(r.tool_calls))}</div>") if r.tool_calls else ""
            cells += f"<td style='padding:6px 10px;text-align:left;vertical-align:top'>{body}{tools}</td>"
        rows.append(f"<tr style='border-top:1px solid #C9D2DC'><td style='padding:6px 10px;text-align:left;"
                    f"vertical-align:top'><b>{q['id']}</b><br>{html.escape(q['question'])}</td>{cells}</tr>")
    return (f"<table style='border-collapse:collapse;{FONT};width:100%'><tr><th style='padding:6px 10px;"
            f"text-align:left;width:24%'>Question</th>{head}</tr>{''.join(rows)}</table>")
