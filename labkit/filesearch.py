"""Lab 1 challenge: two alternatives to a hand-written search tool.

1. Gemini File Search (Google-managed retrieval): a temporary store is created, the SOPs are uploaded, the question
   is asked once, and the store is always deleted. `sources` are the documents File Search reports it retrieved.
2. Long context: every SOP is placed in the prompt. There is no retrieval, so no `sources`: `in_prompt` lists what
   the model was given.
Problems come back as a plain message (never a traceback): the challenge is optional.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from pathlib import Path

from labkit.agents import BACKUP_MODELS, BUSY_MESSAGE, QUOTA_MESSAGE, _error_kind

QUOTA_FS = ("File Search reached a free-tier quota (it embeds your documents and your question). Wait one minute "
            "and run the cell again. This challenge is optional — you can skip it.")
UPLOAD_ATTEMPTS = 2
QUOTA_WAIT = 15          # seconds between upload attempts
INDEX_TIMEOUT = 60       # seconds per document


@dataclass
class FileSearchResult:
    text: str = ""
    sources: list[str] = field(default_factory=list)     # documents reported by retrieval
    in_prompt: list[str] = field(default_factory=list)   # documents placed whole in the prompt (long context)
    message: str | None = None


def _sources(resp) -> list[str]:
    titles = set()
    for cand in getattr(resp, "candidates", None) or []:
        meta = getattr(cand, "grounding_metadata", None)
        for ch in getattr(meta, "grounding_chunks", None) or []:
            title = getattr(getattr(ch, "retrieved_context", None), "title", None)
            if title:
                titles.add(title)
    return sorted(titles)


def _message(exc: Exception, quota_text: str) -> str:
    kind = _error_kind(exc)
    if kind == "quota":
        return quota_text
    if kind == "busy":
        return BUSY_MESSAGE + " This challenge is optional."
    return f"The request failed: {str(exc)[:200]}. This challenge is optional."


def ask_with_file_search(folder, question: str, model: str, client=None, sleep=time.sleep,
                         progress=print) -> FileSearchResult:
    from google.genai import types

    if client is None:
        from google import genai
        client = genai.Client()
    store = None
    try:
        store = client.file_search_stores.create(config={"display_name": "northbridge-sops"})
        for f in sorted(Path(folder).glob("*.md")):
            progress(f"  indexing {f.stem}…")
            for attempt in range(UPLOAD_ATTEMPTS):  # indexing has a tight per-minute quota: wait once and retry
                try:
                    op = client.file_search_stores.upload_to_file_search_store(
                        file=str(f), file_search_store_name=store.name,
                        config={"display_name": f.stem, "mime_type": "text/plain"})
                    break
                except Exception as exc:
                    if _error_kind(exc) != "quota" or attempt == UPLOAD_ATTEMPTS - 1:
                        raise
                    progress(f"  quota reached, waiting {QUOTA_WAIT} s…")
                    sleep(QUOTA_WAIT)
            waited = 0
            while not op.done:
                if waited >= INDEX_TIMEOUT:
                    return FileSearchResult(message="Indexing took too long. Run the cell again in a minute.")
                sleep(2)
                waited += 2
                op = client.operations.get(op)
        progress("  asking…")
        resp = client.models.generate_content(
            model=model, contents=question + " Answer only from the documents and cite them.",
            config=types.GenerateContentConfig(temperature=0, tools=[types.Tool(
                file_search=types.FileSearch(file_search_store_names=[store.name]))]))
        return FileSearchResult(text=resp.text or "", sources=_sources(resp))
    except Exception as exc:  # participant-facing: plain message instead of a traceback
        return FileSearchResult(message=_message(exc, QUOTA_FS))
    finally:
        if store is not None:
            try:
                client.file_search_stores.delete(name=store.name, config={"force": True})
            except Exception:
                pass  # temporary store; never block the participant on cleanup


def ask_long_context(folder, question: str, model: str, client=None) -> FileSearchResult:
    """The no-retrieval alternative: put every SOP in the prompt (fine for 3 short SOPs, not for 300)."""
    from google.genai import types

    if client is None:
        from google import genai
        client = genai.Client()
    files = sorted(Path(folder).glob("*.md"))
    docs = "\n\n".join(f.read_text(encoding="utf-8") for f in files)
    prompt = (f"Documents:\n\n{docs}\n\nQuestion: {question}\n"
              "Answer only from the documents above and cite the SOP number and section.")
    last = None
    for m in [model] + [b for b in BACKUP_MODELS if b != model]:
        try:
            resp = client.models.generate_content(model=m, contents=prompt,
                                                  config=types.GenerateContentConfig(temperature=0))
            return FileSearchResult(text=resp.text or "", in_prompt=[f.stem for f in files])
        except Exception as exc:
            last = exc
            if _error_kind(exc) not in ("busy", "quota"):
                break
    return FileSearchResult(message=_message(last, QUOTA_MESSAGE + " This challenge is optional."))
