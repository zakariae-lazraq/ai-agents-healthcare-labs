"""Load the course SOPs (markdown, one section per "## n. Title") and build a search tool for an agent."""

from __future__ import annotations

import pathlib
import re
from dataclasses import dataclass

STOP = {"the", "and", "for", "what", "which", "with", "this", "that", "are", "is", "a", "an", "of", "in", "on",
        "to", "do", "we", "can", "how", "long", "should", "must", "be", "it", "its", "at", "by", "or", "our"}

SYNONYMS = {"phone": "telephone", "phoned": "telephone", "call": "telephone", "called": "telephone",
            "r2": "r²", "hemolysed": "haemolysed", "hemolysis": "haemolysis"}


@dataclass
class Section:
    sop: str
    sop_title: str
    number: str
    title: str
    text: str


def load_sops(folder) -> list[Section]:
    """Read every *.md SOP in a folder into numbered sections."""
    sections = []
    for path in sorted(pathlib.Path(folder).glob("*.md")):
        sop_id, sop_title, cur = "", "", None
        for line in path.read_text(encoding="utf-8").splitlines():
            if line.startswith("# "):
                sop_id, _, sop_title = line[2:].partition(" — ")
            elif line.startswith("## "):
                num, _, title = line[3:].partition(". ")
                cur = Section(sop_id.strip(), sop_title.strip(), num.strip(), title.strip(), "")
                sections.append(cur)
            elif cur is not None and line.strip():
                cur.text = (cur.text + " " + line.strip()).strip()
    return sections


def _tokens(text: str) -> set[str]:
    text = text.lower().replace("hemo", "haemo").replace("²", "2")
    words = re.findall(r"[a-z0-9]+(?:[-.][a-z0-9]+)*", text)
    words = [SYNONYMS.get(w, w) for w in words]
    return {w[:6] for w in words if w not in STOP and (len(w) >= 3 or any(c.isdigit() for c in w))}


def make_search_tool(sections: list[Section], k: int = 3):
    """Return a search_sop(query) tool over the given sections (keyword overlap, titles weigh double)."""
    index = [(s, _tokens(s.text + " " + s.sop_title), _tokens(s.title)) for s in sections]

    def search_sop(query: str) -> dict:
        """Search the Northbridge laboratory SOPs (SOP-01 vitamin D by LC-MS/MS, SOP-02 specimen acceptance,
        SOP-03 critical values).

        Returns up to 3 relevant sections, each with the SOP id, section number, title and full text.
        Use precise keywords, for example "ion ratio tolerance" or "haemolysis potassium".
        Quote the SOP id and section number (for example SOP-01 §5) in your answer.
        """
        q = _tokens(query)
        scored = []
        for s, body, head in index:
            score = len(q & body) + 2 * len(q & head)
            if score:
                scored.append((score, s))
        scored.sort(key=lambda x: -x[0])
        results = [{"sop": s.sop, "section": s.number, "title": s.title, "text": s.text} for _, s in scored[:k]]
        if not results:
            return {"results": [], "message": "No SOP section matches this query."}
        return {"results": results}

    return search_sop
