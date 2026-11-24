"""API key reading and the environment checklist shown in every lab's Setup cell."""

from __future__ import annotations

import html
import os
import sys
import urllib.request
from dataclasses import dataclass

import labkit
from labkit import DEFAULT_MODEL

KEY_NAME = "GOOGLE_API_KEY"

FIX_KEY_MISSING = (
    "Open the 🔑 Secrets panel (left sidebar) → add a secret named GOOGLE_API_KEY → "
    "paste your key → switch ON 'Notebook access' → run this cell again."
)
FIX_KEY_REJECTED = (
    "Google rejected this key. Create a new key at aistudio.google.com/apikey, "
    "replace it in Secrets, run again."
)
FIX_QUOTA = "Your key works but its free quota is used up for now. Wait one minute and run again."
FIX_PUBMED = "PubMed is not reachable from here. Labs will use saved results — tell the trainer."
FIX_PYTHON = "This notebook needs Python 3.11 or newer. Use a standard Google Colab runtime."
FIX_ADK = "Run the Setup cell again from the top; if it still fails, Runtime → Restart session, then run it again."

PUBMED_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/einfo.fcgi?db=pubmed"


@dataclass
class CheckResult:
    name: str
    ok: bool
    detail: str
    fix: str = ""


def get_api_key() -> str | None:
    """Return the Gemini API key from Colab Secrets, else the environment. Never prints it."""
    key, source = None, ""
    try:
        from google.colab import userdata  # type: ignore

        key = userdata.get(KEY_NAME)
        source = "Colab Secrets" if key else ""
    except Exception:
        key = None
    if not key and os.environ.get(KEY_NAME, "").strip():
        key, source = os.environ[KEY_NAME], "environment variable"
    key = (key or "").strip() or None
    labkit._state["key_source"] = source if key else ""
    if key:
        os.environ[KEY_NAME] = key
    return key


def _make_client(api_key: str):
    from google import genai

    return genai.Client(api_key=api_key)


def _scrub(text: str, secret: str | None) -> str:
    text = str(text)
    if secret:
        text = text.replace(secret, "•••")
    return text[:200]


FIX_MODEL_MISSING = ("This model is not available for your key. Tell the trainer; meanwhile set "
                     "MODEL = \"gemini-flash-lite-latest\" in the Setup cell and run it again.")
FIX_LOCATION = "Google does not offer the Gemini API from your location or network. Tell the trainer."
FIX_NO_FREE_QUOTA = ("This model has no free quota for your key (limit 0). Tell the trainer; meanwhile set "
                     "MODEL = \"gemini-flash-lite-latest\" in the Setup cell and run it again.")


def _classify_model_error(exc: Exception) -> str:
    msg = str(exc).lower()
    if "location is not supported" in msg or "user location" in msg:
        return FIX_LOCATION
    if "limit: 0" in msg:
        return FIX_NO_FREE_QUOTA
    if "429" in msg or "resource_exhausted" in msg or "quota" in msg:
        return FIX_QUOTA
    if "404" in msg or "not_found" in msg or "is not found" in msg:
        return FIX_MODEL_MISSING
    if any(s in msg for s in ("api key not valid", "api_key_invalid", "401", "403", "400", "permission")):
        return FIX_KEY_REJECTED
    return "Gemini did not answer. Wait a moment and run this cell again; if it repeats, tell the trainer."


def check_environment(model: str = DEFAULT_MODEL, *, ping_model: bool = True,
                      ping_pubmed: bool = True) -> list[CheckResult]:
    """Run the setup checklist in order. Later key checks are skipped when the key is missing."""
    results: list[CheckResult] = []
    py_ok = sys.version_info >= (3, 11)
    results.append(CheckResult("Python 3.11+", py_ok, sys.version.split()[0], "" if py_ok else FIX_PYTHON))

    try:
        import google.adk

        results.append(CheckResult("Google ADK installed", True, f"version {google.adk.__version__}"))
    except Exception as exc:  # pragma: no cover - environment specific
        results.append(CheckResult("Google ADK installed", False, type(exc).__name__, FIX_ADK))

    key = get_api_key()
    results.append(CheckResult("API key found", bool(key), f"found in {labkit._state.get('key_source') or 'Secrets'}" if key else "not found",
                               "" if key else FIX_KEY_MISSING))

    if not key:
        results.append(CheckResult("API key works", False, "skipped", "Fix the line above first."))
    elif ping_model:
        try:
            _make_client(key).models.generate_content(model=model, contents="Reply with OK")
            results.append(CheckResult("API key works", True, f"{model} answered"))
        except Exception as exc:
            results.append(CheckResult("API key works", False, _scrub(exc, key), _classify_model_error(exc)))

    if ping_pubmed:
        try:
            with urllib.request.urlopen(PUBMED_URL, timeout=10) as resp:
                ok = resp.status == 200
            results.append(CheckResult("PubMed reachable", ok, "ok" if ok else f"HTTP {resp.status}",
                                       "" if ok else FIX_PUBMED))
        except Exception as exc:
            results.append(CheckResult("PubMed reachable", False, type(exc).__name__, FIX_PUBMED))
    return results


def checks_html(results: list[CheckResult]) -> str:
    rows = []
    for r in results:
        icon = "✅" if r.ok else "❌"
        fix = (f"<div style='color:#b3261e;margin-top:2px'>👉 {html.escape(r.fix)}</div>"
               if (not r.ok and r.fix) else "")
        rows.append(
            f"<tr><td style='padding:4px 10px;font-size:18px'>{icon}</td>"
            f"<td style='padding:4px 10px'><b>{html.escape(r.name)}</b>"
            f"<span style='opacity:.7'> — {html.escape(r.detail)}</span>{fix}</td></tr>"
        )
    all_ok = all(r.ok for r in results)
    footer = ("🎉 Everything is ready — continue to the next step." if all_ok
              else "Fix the ❌ lines (follow the 👉 instructions), then run this cell again.")
    return (f"<table style='border-collapse:collapse;font-family:sans-serif'>{''.join(rows)}</table>"
            f"<p style='font-family:sans-serif;font-weight:bold'>{footer}</p>")


def show_checks(results: list[CheckResult]) -> bool:
    """Display the checklist; remember success for this session; return True if all passed."""
    from IPython.display import HTML, display

    # PubMed is optional for setup success: labs fall back to saved results.
    essential_ok = all(r.ok for r in results if r.name != "PubMed reachable")
    labkit._state["setup_ok"] = essential_ok
    display(HTML(checks_html(results)))
    return essential_ok
