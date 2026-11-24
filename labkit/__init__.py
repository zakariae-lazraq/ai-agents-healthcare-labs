"""labkit: tiny helpers for the AI Agents for Healthcare and Diagnostics labs.

Only plumbing lives here (API key, retries, running an agent, trace cards,
task checks). Everything participants should learn stays in the notebooks.
"""

import pathlib as _pathlib

__version__ = "0.1.0"

# Course data shipped with the repo (repo/data), found relative to this package.
DATA_DIR = _pathlib.Path(__file__).resolve().parents[1] / "data"

REPO_URL = "https://github.com/eliem08/ai-agents-healthcare-labs"
DEFAULT_MODEL = "gemini-3.5-flash-lite"

# Shared session flag: setup.show_checks() sets it, ui.require_setup() reads it.
_state: dict = {"setup_ok": False}
