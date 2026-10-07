"""The search_help_docs tool: find help doc passages that answer a question.

Scoring is simple keyword overlap. The function signature and result shape are
meant to stay the same if this is swapped for embedding search later.
"""

import re
from functools import cache
from pathlib import Path

from merchant_agent.config import get_settings
from merchant_agent.models import HelpDoc

_ENGLISH_STOPWORDS = """
a an and are as at be but by can do does for from has have how i if in is it its my me no not
of on or so that the their them there these they this to was what when where which why will
with you your
"""
# Words in almost every merchant question, so they say nothing about the topic.
_DOMAIN_STOPWORDS = "product item store shop google merchant center get got"
STOPWORDS = frozenset(_ENGLISH_STOPWORDS.split() + _DOMAIN_STOPWORDS.split())
TITLE_OR_KEYWORD_WEIGHT = 2
ISSUE_CODE_WEIGHT = 5
MIN_SCORE = 3
NO_MATCH_MESSAGE = (
    "No help doc matches this question. Do not answer from memory: tell the merchant "
    "you could not find official guidance on it."
)


def _tokens(text: str) -> set[str]:
    """Lowercase words with stopwords removed and a trailing plural "s" dropped."""
    words = re.findall(r"[a-z0-9]+", text.lower())
    return {w[:-1] if len(w) > 3 and w.endswith("s") else w for w in words} - STOPWORDS


def parse_help_doc(path: Path) -> HelpDoc:
    """Read one help doc: a front matter block of "key: value" lines, then paragraphs."""
    _, front, body = path.read_text().split("---", 2)
    meta = dict(line.split(":", 1) for line in front.strip().splitlines())
    meta = {key.strip(): value.strip() for key, value in meta.items()}

    def as_list(key: str) -> list[str]:
        return [item.strip() for item in meta.get(key, "").split(",") if item.strip()]

    return HelpDoc(
        doc_id=meta["id"],
        title=meta["title"],
        source_url=meta["source_url"],
        issue_codes=as_list("issue_codes"),
        keywords=as_list("keywords"),
        passages=[p.strip() for p in body.strip().split("\n\n") if p.strip()],
    )


@cache
def _load_from(folder: Path) -> tuple[HelpDoc, ...]:
    return tuple(parse_help_doc(path) for path in sorted(folder.glob("*.md")))


def load_help_docs() -> list[HelpDoc]:
    """Load every help doc in data/help_docs."""
    return list(_load_from(get_settings().data_dir / "help_docs"))


def _score(query: str, query_tokens: set[str], doc: HelpDoc, passage: str) -> int:
    """Score how well one passage of a doc matches the query."""
    heading = _tokens(doc.title + " " + " ".join(doc.keywords))
    score = len(query_tokens & _tokens(passage))
    score += TITLE_OR_KEYWORD_WEIGHT * len(query_tokens & heading)
    score += ISSUE_CODE_WEIGHT * sum(code in query.lower() for code in doc.issue_codes)
    return score


def search_help_docs(query: str, limit: int = 3) -> dict:
    """Search the Merchant Center help docs and return the best matching passages to cite."""
    query_tokens = _tokens(query)
    scored = [
        (_score(query, query_tokens, doc, passage), doc, passage)
        for doc in load_help_docs()
        for passage in doc.passages
    ]
    scored = [item for item in scored if item[0] >= MIN_SCORE]
    scored.sort(key=lambda item: item[0], reverse=True)
    results = [
        {
            "doc_id": doc.doc_id,
            "title": doc.title,
            "source_url": doc.source_url,
            "passage": passage,
            "score": score,
        }
        for score, doc, passage in scored[:limit]
    ]
    if not results:
        return {"query": query, "results": [], "message": NO_MATCH_MESSAGE}
    return {"query": query, "results": results}
