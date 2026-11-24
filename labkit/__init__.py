"""labkit: tiny helpers for the AI Agents for Healthcare and Diagnostics labs.

Only plumbing lives here (API key, retries, running an agent, trace cards,
task checks). Everything participants should learn stays in the notebooks.
"""

__version__ = "0.1.0"

REPO_URL = "https://github.com/eliem08/ai-agents-healthcare-labs"
DEFAULT_MODEL = "gemini-3.5-flash-lite"

# Shared session flag: setup.show_checks() sets it, ui.require_setup() reads it.
_state: dict = {"setup_ok": False}
