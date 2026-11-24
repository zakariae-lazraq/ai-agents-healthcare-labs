import os
import pathlib
import sys
import types

import pytest

import labkit

ROOT_ENV = pathlib.Path(__file__).resolve().parents[2] / ".env"


def _load_dotenv():
    if ROOT_ENV.exists() and not os.environ.get("GOOGLE_API_KEY"):
        for line in ROOT_ENV.read_text().splitlines():
            if line.strip().startswith("GOOGLE_API_KEY="):
                os.environ["LIVE_GOOGLE_API_KEY"] = line.split("=", 1)[1].strip()


_load_dotenv()


@pytest.fixture(autouse=True)
def clean_state(monkeypatch):
    """Each test starts with no key in env, no fake colab, setup not done."""
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    for name in ("google.colab", "google.colab.userdata"):
        monkeypatch.delitem(sys.modules, name, raising=False)
    labkit._state["setup_ok"] = False
    yield


@pytest.fixture
def fake_colab(monkeypatch):
    """Install a fake google.colab.userdata whose get() returns a chosen value or raises."""
    def install(value=None, exc=None):
        userdata = types.ModuleType("google.colab.userdata")

        def get(name):
            if exc:
                raise exc
            return value

        userdata.get = get
        colab = types.ModuleType("google.colab")
        colab.userdata = userdata
        monkeypatch.setitem(sys.modules, "google.colab", colab)
        monkeypatch.setitem(sys.modules, "google.colab.userdata", userdata)
    return install


@pytest.fixture
def live_key(monkeypatch):
    key = os.environ.get("LIVE_GOOGLE_API_KEY")
    if not key:
        pytest.skip("no GOOGLE_API_KEY in .env")
    monkeypatch.setenv("GOOGLE_API_KEY", key)
    return key
