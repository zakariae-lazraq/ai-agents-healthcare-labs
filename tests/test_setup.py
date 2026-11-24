import labkit
from labkit import setup


class FakeModels:
    def __init__(self, exc=None):
        self.exc = exc

    def generate_content(self, model, contents):
        if self.exc:
            raise self.exc
        return type("R", (), {"text": "OK"})()


class FakeClient:
    def __init__(self, exc=None):
        self.models = FakeModels(exc)


def by_name(results):
    return {r.name: r for r in results}


def test_key_from_env(monkeypatch):
    monkeypatch.setenv("GOOGLE_API_KEY", "abc")
    assert setup.get_api_key() == "abc"


def test_key_from_colab_secrets(fake_colab):
    import os
    fake_colab(value="k")
    assert setup.get_api_key() == "k"
    assert os.environ["GOOGLE_API_KEY"] == "k"


def test_key_missing_gives_fix(fake_colab):
    fake_colab(exc=RuntimeError("SecretNotFoundError"))
    r = by_name(setup.check_environment(ping_pubmed=False))
    assert r["API key found"].ok is False
    assert "GOOGLE_API_KEY" in r["API key found"].fix
    assert "Notebook access" in r["API key found"].fix
    assert r["API key works"].ok is False
    assert r["API key works"].detail == "skipped"


def test_invalid_key_message(monkeypatch):
    monkeypatch.setenv("GOOGLE_API_KEY", "bad")
    monkeypatch.setattr(setup, "_make_client", lambda k: FakeClient(Exception("400 INVALID_ARGUMENT. API key not valid.")))
    r = by_name(setup.check_environment(ping_pubmed=False))
    assert r["API key works"].ok is False
    assert "aistudio.google.com/apikey" in r["API key works"].fix


def test_quota_message(monkeypatch):
    monkeypatch.setenv("GOOGLE_API_KEY", "k")
    monkeypatch.setattr(setup, "_make_client", lambda k: FakeClient(Exception("429 RESOURCE_EXHAUSTED")))
    r = by_name(setup.check_environment(ping_pubmed=False))
    assert r["API key works"].ok is False
    assert "Wait one minute" in r["API key works"].fix


def test_working_key_all_ok_and_sets_flag(monkeypatch):
    monkeypatch.setenv("GOOGLE_API_KEY", "k")
    monkeypatch.setattr(setup, "_make_client", lambda k: FakeClient())
    results = setup.check_environment(ping_pubmed=False)
    assert all(r.ok for r in results)
    assert setup.show_checks(results) is True
    assert labkit._state["setup_ok"] is True


def test_key_never_in_output(monkeypatch):
    monkeypatch.setenv("GOOGLE_API_KEY", "SECRET123")
    monkeypatch.setattr(setup, "_make_client", lambda k: FakeClient(Exception("bad key SECRET123 not valid")))
    results = setup.check_environment(ping_pubmed=False)
    for r in results:
        assert "SECRET123" not in r.detail and "SECRET123" not in r.fix
    html = setup.checks_html(results)
    assert "SECRET123" not in html



def test_checks_table_is_left_aligned():
    html = setup.checks_html([setup.CheckResult("PubMed reachable", True, "ok")])
    assert "text-align:left" in html
