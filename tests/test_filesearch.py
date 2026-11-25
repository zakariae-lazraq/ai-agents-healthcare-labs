"""File Search challenge helper: success path, quota error, cleanup."""

from types import SimpleNamespace as NS

import pytest

from labkit.filesearch import ask_with_file_search


class FakeClient:
    def __init__(self, fail_on=None):
        self.fail_on = fail_on
        self.deleted = []
        self.uploaded = []
        self.file_search_stores = NS(create=self._create, upload_to_file_search_store=self._upload,
                                     delete=self._delete)
        self.operations = NS(get=lambda op: NS(done=True))
        self.models = NS(generate_content=self._generate)

    def _create(self, config):
        return NS(name="fileSearchStores/test-1")

    def _upload(self, file, file_search_store_name, config):
        if self.fail_on == "upload":
            raise RuntimeError("429 RESOURCE_EXHAUSTED. {'message': 'Failed to embed content.'}")
        self.uploaded.append(config["display_name"])
        return NS(done=False)

    def _delete(self, name, config):
        self.deleted.append(name)
        if self.fail_on == "delete":
            raise RuntimeError("500 internal")

    def _generate(self, model, contents, config):
        chunks = [NS(retrieved_context=NS(title="SOP-03_Critical_Values")),
                  NS(retrieved_context=NS(title="SOP-03_Critical_Values")),
                  NS(retrieved_context=NS(title="SOP-01_Vitamin_D"))]
        cand = NS(grounding_metadata=NS(grounding_chunks=chunks))
        return NS(text="Vitamin D is not on the critical value list (SOP-03).", candidates=[cand])


@pytest.fixture
def sops(tmp_path):
    for n in ("SOP-01_Vitamin_D", "SOP-03_Critical_Values"):
        (tmp_path / f"{n}.md").write_text("# " + n, encoding="utf-8")
    return tmp_path


def test_success_returns_answer_and_unique_sources(sops):
    c = FakeClient()
    r = ask_with_file_search(sops, "Critical value for vitamin D?", "m", client=c, sleep=lambda s: None)
    assert r.message is None
    assert "not on the critical value list" in r.text
    assert r.sources == ["SOP-01_Vitamin_D", "SOP-03_Critical_Values"]
    assert c.uploaded == ["SOP-01_Vitamin_D", "SOP-03_Critical_Values"]
    assert c.deleted == ["fileSearchStores/test-1"]


def test_quota_error_gives_message_not_traceback_and_cleans_up(sops):
    c = FakeClient(fail_on="upload")
    r = ask_with_file_search(sops, "q", "m", client=c, sleep=lambda s: None)
    assert r.text == ""
    assert "quota" in r.message.lower() and "optional" in r.message.lower()
    assert c.deleted == ["fileSearchStores/test-1"]


def test_transient_quota_on_upload_is_retried(sops):
    c = FakeClient()
    real_upload, calls, waits = c._upload, [], []

    def flaky(file, file_search_store_name, config):
        calls.append(file)
        if len(calls) == 1:
            raise RuntimeError("429 RESOURCE_EXHAUSTED. Failed to embed content.")
        return real_upload(file, file_search_store_name, config)

    c.file_search_stores.upload_to_file_search_store = flaky
    r = ask_with_file_search(sops, "q", "m", client=c, sleep=waits.append)
    assert r.message is None and r.text
    assert c.uploaded == ["SOP-01_Vitamin_D", "SOP-03_Critical_Values"]
    assert 20 in waits


def test_cleanup_failure_does_not_hide_answer(sops):
    c = FakeClient(fail_on="delete")
    r = ask_with_file_search(sops, "q", "m", client=c, sleep=lambda s: None)
    assert r.message is None and r.text


def test_long_context_puts_every_sop_in_the_prompt(sops):
    from labkit.filesearch import ask_long_context
    seen = {}

    def gen(model, contents, config):
        seen["prompt"] = contents
        return NS(text="Not on the list (SOP-03).", candidates=[])

    c = NS(models=NS(generate_content=gen))
    r = ask_long_context(sops, "Critical value for vitamin D?", "m", client=c)
    assert r.message is None and r.text.startswith("Not on the list")
    assert "# SOP-01_Vitamin_D" in seen["prompt"] and "# SOP-03_Critical_Values" in seen["prompt"]
    assert r.sources == ["SOP-01_Vitamin_D", "SOP-03_Critical_Values"]


def test_long_context_error_is_a_message(sops):
    from labkit.filesearch import ask_long_context

    def gen(model, contents, config):
        raise RuntimeError("429 RESOURCE_EXHAUSTED quota")

    r = ask_long_context(sops, "q", "m", client=NS(models=NS(generate_content=gen)))
    assert r.text == "" and "quota" in r.message.lower()
