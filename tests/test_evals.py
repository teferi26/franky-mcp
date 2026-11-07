"""Tool-use eval: natural questions -> expected degree ids in the top 5 of search_degrees."""

from __future__ import annotations

import json
from pathlib import Path

EVALS = Path(__file__).resolve().parents[1] / "evals" / "queries.jsonl"
K = 5
THRESHOLD = 0.85


def load_cases() -> list[dict]:
    return [json.loads(line) for line in EVALS.read_text(encoding="utf-8").splitlines() if line.strip()]


def recall_at_k(service, cases: list[dict], k: int = K) -> tuple[float, list[tuple[str, float]]]:
    per_query = []
    for case in cases:
        top = [r["id"] for r in service.search_degrees(case["query"], limit=k)["results"]]
        expected = case["expected"]
        hits = len(set(top) & set(expected))
        per_query.append((case["query"], hits / min(len(expected), k)))
    return sum(r for _, r in per_query) / len(per_query), per_query


def test_eval_ids_exist(service):
    for case in load_cases():
        for degree_id in case["expected"]:
            assert degree_id in service.ds.degrees, degree_id


def test_search_recall_at_5(service):
    cases = load_cases()
    assert len(cases) >= 20
    score, per_query = recall_at_k(service, cases)
    misses = [f"{q!r}: {r:.2f}" for q, r in per_query if r < 1]
    print(f"\nsearch_degrees recall@{K} = {score:.3f} over {len(cases)} queries; partial: {misses}")
    assert score >= THRESHOLD, f"recall@{K}={score:.3f} below {THRESHOLD}; partial: {misses}"
