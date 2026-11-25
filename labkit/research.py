"""Lab 7: a research agent with verified citations — PubMed search and abstracts (NCBI E-utilities), claim checks.

Live E-utilities first (no API key: NCBI allows about 3 requests per second per IP), then the shipped cache if the
network or NCBI fails, so the lab always works. Citation review reuses the Lab 6 guardian idea: every PMID must exist,
must have been retrieved by the agent, and its abstract must support the sentence.
"""

from __future__ import annotations

import html as _html
import json
import re
import time
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path

BASE = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/"
STOP = set("the and for with from that this were was are is of in on to a an by as at or be not than more less into "
           "using use used our their its can may has have had which what how does did study studies patients".split())


class PubMedClient:
    def __init__(self, cache_file=None, live: bool = True, tool_name: str = "ai-agents-course"):
        self.cache_file = Path(cache_file) if cache_file else None
        self.cache = {"searches": {}, "records": {}}
        if self.cache_file and self.cache_file.exists():
            self.cache = json.loads(self.cache_file.read_text(encoding="utf-8"))
        self.live = live
        self.tool_name = tool_name
        self.retrieved: set[str] = set()     # every PMID the agent has seen in this session
        self._last = 0.0

    # ------------------------------------------------------------ network (polite: ≤ 3 requests per second)
    def _get(self, endpoint: str, params: dict) -> bytes:
        wait = 0.34 - (time.time() - self._last)
        if wait > 0:
            time.sleep(wait)
        self._last = time.time()
        url = BASE + endpoint + "?" + urllib.parse.urlencode({**params, "tool": self.tool_name})
        return urllib.request.urlopen(url, timeout=15).read()

    def search(self, query: str, max_results: int = 5) -> tuple[list[str], str]:
        if self.live:
            try:
                data = json.loads(self._get("esearch.fcgi", {"db": "pubmed", "term": query, "retmax": max_results,
                                                             "retmode": "json", "sort": "relevance"}))
                ids = data["esearchresult"]["idlist"]
                self.cache["searches"][query] = ids
                return ids, "PubMed (live)"
            except Exception:
                pass
        if query in self.cache["searches"]:
            return self.cache["searches"][query][:max_results], "PubMed (cached copy)"
        words = _terms(query)
        scored = sorted(((len(words & _terms(r["title"] + " " + r.get("abstract", ""))), pmid)
                         for pmid, r in self.cache["records"].items()), reverse=True)
        return [p for s, p in scored[:max_results] if s >= max(2, len(words) // 2)], "cached records (offline search)"

    def fetch(self, pmids: list[str]) -> tuple[dict, str]:
        missing = [p for p in pmids if p not in self.cache["records"]]
        source = "PubMed (cached copy)"
        if missing and self.live:
            try:
                root = ET.fromstring(self._get("efetch.fcgi", {"db": "pubmed", "id": ",".join(missing), "retmode": "xml"}))
                for art in root.iter("PubmedArticle"):
                    rec = _parse_article(art)
                    self.cache["records"][rec["pmid"]] = rec
                source = "PubMed (live)"
            except Exception:
                pass
        return {p: self.cache["records"][p] for p in pmids if p in self.cache["records"]}, source

    def save(self) -> None:
        if self.cache_file:
            self.cache_file.write_text(json.dumps(self.cache, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")


def _parse_article(art) -> dict:
    pmid = art.findtext(".//PMID")
    title = "".join(art.find(".//ArticleTitle").itertext()).strip()
    abstract = " ".join("".join(t.itertext()).strip() for t in art.iter("AbstractText"))
    year = art.findtext(".//PubDate/Year") or (art.findtext(".//PubDate/MedlineDate") or "")[:4]
    journal = art.findtext(".//Journal/Title") or ""
    first = art.find(".//AuthorList/Author")
    author = f"{first.findtext('LastName') or ''} {first.findtext('Initials') or ''}".strip() if first is not None else ""
    pubtypes = [p.text for p in art.iter("PublicationType") if p.text]
    return {"pmid": pmid, "title": title, "abstract": abstract, "year": year, "journal": journal,
            "first_author": author, "pubtypes": pubtypes}


def _terms(text: str) -> set[str]:
    return {w for w in re.findall(r"[a-z0-9][a-z0-9\-]+", (text or "").lower()) if len(w) > 2 and w not in STOP}


def support(claim: str, record: dict) -> tuple[str, float]:
    """How much of the claim's vocabulary (and every number in it) appears in the title + abstract."""
    text = (record.get("title", "") + " " + record.get("abstract", "")).lower()
    clean = re.sub(r"\(?PMID[:\s]*\d+\)?", "", claim, flags=re.I)
    words = _terms(clean)
    nums = re.findall(r"\d+(?:\.\d+)?", clean)
    if not words:
        return "not checkable", 0.0
    score = sum(w in text for w in words) / len(words)
    if nums and not all(n in text for n in nums):
        score = min(score, 0.4)
    return ("supported" if score >= 0.6 else "weak" if score >= 0.35 else "not supported"), round(score, 2)


EVIDENCE_ORDER = ["Meta-Analysis", "Systematic Review", "Randomized Controlled Trial", "Practice Guideline",
                  "Clinical Trial", "Multicenter Study", "Comparative Study", "Observational Study", "Review",
                  "Journal Article"]


def evidence_level(record: dict) -> str:
    for t in EVIDENCE_ORDER:
        if t in record.get("pubtypes", []):
            return t
    return "unknown"


# ---------------------------------------------------------------- tools for the agent
def make_research_tools(client: PubMedClient) -> dict:
    def search_pubmed(query: str, max_results: int = 5) -> dict:
        """Search PubMed. Returns the PMIDs of the most relevant articles (max_results ≤ 8). Use precise terms, e.g.
        'high-sensitivity troponin rule-out myocardial infarction'."""
        ids, source = client.search(query, min(int(max_results or 5), 8))
        client.retrieved.update(ids)
        return {"query": query, "pmids": ids, "count": len(ids), "source": source,
                "note": "no article found" if not ids else ""}

    def fetch_abstracts(pmids: list[str]) -> dict:
        """Fetch title, year, journal, publication type and abstract for a list of PMIDs (max 8)."""
        recs, source = client.fetch([str(p) for p in pmids][:8])
        client.retrieved.update(recs)
        return {"source": source, "articles": [
            {"pmid": p, "title": r["title"], "year": r["year"], "journal": r["journal"],
             "evidence_type": evidence_level(r), "abstract": r["abstract"][:1500]} for p, r in recs.items()]}

    def verify_claim(claim: str, pmid: str) -> dict:
        """Check whether one sentence is supported by the abstract of the PMID it cites (vocabulary and numbers)."""
        recs, _ = client.fetch([str(pmid)])
        if str(pmid) not in recs:
            return {"pmid": pmid, "verdict": "PMID not found", "score": 0.0}
        v, s = support(claim, recs[str(pmid)])
        return {"pmid": pmid, "verdict": v, "score": s}

    return {f.__name__: f for f in (search_pubmed, fetch_abstracts, verify_claim)}


# ---------------------------------------------------------------- review of a summary (the Lab 6 guardian idea)
def cited_sentences(summary: str) -> list[tuple[str, list[str]]]:
    parts = re.split(r"(?<=[.!?])\s+(?=[A-Z0-9*\-•])", (summary or "").replace("\n", " "))
    out = []
    for s in parts:
        s = s.strip(" -•*")
        if len(s) < 25 or re.match(r"(status|evidence strength|verdict)\s*:", s, re.I):
            continue
        out.append((s, re.findall(r"PMID[:\s]*(\d{5,9})", s, re.I)))
    return out


def review_summary(client: PubMedClient, summary: str) -> dict:
    """Every sentence must cite a PMID that exists, was retrieved by the agent, and supports it."""
    rows, issues = [], []
    for sent, pmids in cited_sentences(summary):
        if not pmids:
            if re.search(r"no (evidence|article|stud)|not found|could not find|insufficient", sent, re.I):
                rows.append({"sentence": sent, "pmid": "", "check": "states missing evidence", "ok": True})
            else:
                rows.append({"sentence": sent, "pmid": "", "check": "no PMID", "ok": False})
                issues.append("claim without a PMID")
            continue
        recs, _ = client.fetch(pmids)
        for p in pmids:
            if p not in recs:
                rows.append({"sentence": sent, "pmid": p, "check": "PMID does not exist", "ok": False})
                issues.append(f"PMID {p} does not exist")
            elif p not in client.retrieved:
                rows.append({"sentence": sent, "pmid": p, "check": "never retrieved by the agent", "ok": False})
                issues.append(f"PMID {p} was cited but never retrieved (possible fabrication)")
            else:
                v, s = support(sent, recs[p])
                rows.append({"sentence": sent, "pmid": p, "check": f"{v} ({s})", "ok": v == "supported"})
                if v == "not supported":
                    issues.append(f"PMID {p} does not support the sentence")
    severe = [i for i in issues if "does not exist" in i or "never retrieved" in i]
    verdict = "ESCALATE" if severe else ("HOLD" if issues else "RELEASE")
    return {"verdict": verdict, "issues": issues, "rows": rows}


def review_html(review: dict) -> str:
    td = "padding:4px 10px;text-align:left;vertical-align:top;font-size:12px"
    body = "".join(
        f"<tr style='border-top:1px solid #C9D2DC'><td style='{td}'>{_html.escape(r['sentence'][:220])}</td>"
        f"<td style='{td}'>" + (f"<a href='https://pubmed.ncbi.nlm.nih.gov/{r['pmid']}/' target='_blank'>{r['pmid']}</a>"
                                if r["pmid"] else "") +
        f"</td><td style='{td};color:{'#1E7A3C' if r['ok'] else '#B3261E'}'>{_html.escape(r['check'])}</td></tr>"
        for r in review["rows"])
    color = {"RELEASE": "#1E7A3C", "HOLD": "#B7791F", "ESCALATE": "#B3261E"}[review["verdict"]]
    return (f"<div style='font-family:Inter,Segoe UI,Roboto,sans-serif;font-size:14px;margin:6px 0'><b>Guardian verdict: "
            f"<span style='color:{color}'>{review['verdict']}</span></b></div>"
            "<table style='border-collapse:collapse;font-family:Inter,Segoe UI,Roboto,sans-serif'>"
            f"<tr><th style='{td}'>Sentence</th><th style='{td}'>PMID (click)</th><th style='{td}'>Check</th></tr>"
            f"{body}</table>")
