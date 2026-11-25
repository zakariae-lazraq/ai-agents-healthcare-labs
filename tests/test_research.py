"""Lab 7 research tools (offline, on the shipped PubMed cache) and the citation review."""
import json
import pathlib

import pytest

from labkit import research

DATA = pathlib.Path(__file__).resolve().parents[1] / "data" / "lab07"


@pytest.fixture()
def client():
    return research.PubMedClient(DATA / "pubmed_cache.json", live=False)


@pytest.fixture(scope="module")
def questions():
    return json.loads((DATA / "questions.json").read_text(encoding="utf-8"))


def test_cached_searches_cover_every_question(client, questions):
    for q in questions:
        if q["id"] == "TRAP":
            continue
        ids = [i for query in q["queries"] for i in client.search(query, 6)[0]]
        assert len(ids) >= 5, q["id"]


def test_offline_search_finds_relevant_records_for_a_new_query(client):
    ids, source = client.search("troponin rule-out myocardial infarction emergency", 5)
    assert ids and "offline" in source


def test_trap_has_no_record_about_the_biomarker(client):
    assert not any("neurovaxin" in (r["title"] + r["abstract"]).lower() for r in client.cache["records"].values())


def test_tools_record_what_was_retrieved(client):
    t = research.make_research_tools(client)
    r = t["search_pubmed"]("high-sensitivity troponin rule-out myocardial infarction", 3)
    assert r["count"] == 3 and set(r["pmids"]) <= client.retrieved
    a = t["fetch_abstracts"](r["pmids"])
    assert a["articles"] and a["articles"][0]["abstract"]


def test_support_scoring(client):
    rec = client.cache["records"]["34061019"]
    claim = "High-sensitivity troponin assays allow early rule-out of acute myocardial infarction (PMID 34061019)."
    assert research.support(claim, rec)[0] == "supported"
    assert research.support("Pembrolizumab doubles survival in melanoma (PMID 34061019).", rec)[0] == "not supported"


def test_review_summary_verdicts(client):
    t = research.make_research_tools(client)
    t["search_pubmed"]("high-sensitivity troponin rule-out myocardial infarction", 3)
    ok = "High-sensitivity troponin assays allow early rule-out of acute myocardial infarction (PMID 34061019)."
    assert research.review_summary(client, ok)["verdict"] == "RELEASE"
    unretrieved = ok + " Pembrolizumab improves survival in PD-L1 positive lung cancer (PMID 28293123)."
    assert research.review_summary(client, unretrieved)["verdict"] == "ESCALATE"
    fake = ok + " Troponin is perfect in all patients (PMID 46102733)."
    assert research.review_summary(client, fake)["verdict"] == "ESCALATE"
    no_pmid = ok + " Troponin testing is recommended in every emergency department worldwide."
    assert research.review_summary(client, no_pmid)["verdict"] == "HOLD"
    honest = "No evidence was found in PubMed for this biomarker."
    assert research.review_summary(client, honest)["verdict"] == "RELEASE"


def test_evidence_level(client):
    assert research.evidence_level(client.cache["records"]["34061019"]) in ("Systematic Review", "Meta-Analysis")
