import math

from franky_mcp.bm25 import BM25

DOCS = [
    ["medicina", "madrid"],
    ["derecho", "madrid", "madrid"],
    ["medicina", "medicina", "sevilla"],
    ["historia", "arte", "sevilla", "museo", "patrimonio"],
]


def test_idf_rare_terms_weigh_more():
    bm = BM25(DOCS)
    assert bm.idf("historia") > bm.idf("madrid") > 0
    assert bm.idf("unknown") == 0.0


def test_rank_orders_by_relevance_and_drops_zero():
    bm = BM25(DOCS)
    ranked = bm.rank(["medicina"])
    assert [i for i, _ in ranked] == [2, 0]
    assert all(score > 0 for _, score in ranked)


def test_multi_term_query_prefers_docs_matching_both():
    bm = BM25(DOCS)
    assert bm.rank(["medicina", "madrid"])[0][0] == 0


def test_candidates_restrict_pool_and_ties_are_deterministic():
    bm = BM25([["a"], ["a"], ["b"]])
    assert [i for i, _ in bm.rank(["a"])] == [0, 1]
    assert [i for i, _ in bm.rank(["a"], candidates=[1, 2])] == [1]


def test_score_matches_formula():
    bm = BM25(DOCS, k1=1.2, b=0.75)
    tf, dl = 2, 3
    norm = 1.2 * (1 - 0.75 + 0.75 * dl / bm.avgdl)
    expected = bm.idf("medicina") * tf * 2.2 / (tf + norm)
    assert math.isclose(bm.score(["medicina"], 2), expected)


def test_empty_corpus():
    assert BM25([]).rank(["x"]) == []
