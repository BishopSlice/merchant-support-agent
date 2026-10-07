import pytest

from merchant_agent.models import IssueType
from merchant_agent.tools.help_search import load_help_docs, search_help_docs


def top_doc(query: str) -> str:
    return search_help_docs(query)["results"][0]["doc_id"]


def test_every_doc_cites_a_merchant_center_help_page():
    docs = load_help_docs()
    assert len(docs) >= 10
    for doc in docs:
        assert doc.source_url.startswith("https://support.google.com/merchants/answer/")
        assert doc.passages, doc.doc_id


def test_doc_ids_are_unique():
    ids = [doc.doc_id for doc in load_help_docs()]
    assert len(ids) == len(set(ids))


@pytest.mark.parametrize("issue_type", list(IssueType))
def test_each_issue_type_finds_a_doc_covering_it_first(issue_type):
    docs = {doc.doc_id: doc for doc in load_help_docs()}
    assert issue_type.value in docs[top_doc(issue_type.value)].issue_codes


@pytest.mark.parametrize(
    ("query", "expected"),
    [
        ("my products are missing a barcode number", "gtin"),
        ("handmade product with no barcode", "identifier-exists"),
        ("the price on my website is different from my feed", "price-mismatch"),
        ("my image is a placeholder", "image-link"),
        ("how long can a product title be", "title"),
        ("feed says in stock but my site says sold out", "availability-mismatch"),
        ("I have not set a shipping cost", "shipping"),
        ("can I sell CBD candles", "cbd-unapproved-substances"),
        ("why is my account suspended for misrepresentation", "misrepresentation"),
        ("I disagree with the decision and want to appeal", "request-review"),
        ("I fixed it, how long until my products are approved again", "after-a-fix"),
    ],
)
def test_plain_language_questions_find_the_right_doc(query, expected):
    assert top_doc(query) == expected


def test_results_carry_citation_fields():
    result = search_help_docs("missing gtin")["results"][0]
    assert set(result) >= {"doc_id", "title", "source_url", "passage"}


def test_results_are_limited():
    assert len(search_help_docs("product price image title shipping", limit=2)["results"]) <= 2


@pytest.mark.parametrize(
    "query",
    [
        "what is the weather in Paris",
        "",
        "   ",
        "how do I increase my ad bids",
        "my invoice is wrong",
        "does shopify sync my products",
        "why are my products getting so few clicks",
    ],
)
def test_unrelated_questions_return_no_results_and_say_so(query):
    result = search_help_docs(query)
    assert result["results"] == []
    assert "no help doc" in result["message"].lower()
