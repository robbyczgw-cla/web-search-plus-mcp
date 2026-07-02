import web_search_plus_mcp.quality as quality


def test_domain_matcher_rejects_lookalike_authority_domains():
    assert quality._domain_matches_rule("nist.gov", "nist.gov") is True
    assert quality._domain_matches_rule("www.nist.gov", "nist.gov") is True
    assert quality._domain_matches_rule("nist.gov.evil.example", "nist.gov") is False
    assert quality._domain_matches_rule("docs.python.org", "docs.") is True
    assert quality._domain_matches_rule("notdocs.python.org", "docs.") is False


def test_reranker_does_not_boost_lookalike_authority_domain():
    results = [
        {"title": "mirror", "url": "https://nist.gov.evil.example/report.pdf", "snippet": "fake"},
        {"title": "official", "url": "https://nist.gov/report.pdf", "snippet": "real"},
    ]

    reranked, meta = quality.rerank_results_for_intent("official policy pdf", "policy_pdf", results)

    assert meta["reranked"] is True
    assert reranked[0]["url"] == "https://nist.gov/report.pdf"
