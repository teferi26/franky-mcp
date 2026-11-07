"""A small, dependency-free Okapi BM25 ranker."""

from __future__ import annotations

import math
from collections import Counter
from collections.abc import Sequence


class BM25:
    """Okapi BM25 over pre-tokenized documents.

    ``k1`` controls term-frequency saturation and ``b`` length normalization; the
    defaults are the usual textbook values.
    """

    def __init__(self, documents: Sequence[Sequence[str]], k1: float = 1.5, b: float = 0.75) -> None:
        self.k1 = k1
        self.b = b
        self._tfs = [Counter(doc) for doc in documents]
        self._lengths = [len(doc) for doc in documents]
        self.n_docs = len(documents)
        self.avgdl = (sum(self._lengths) / self.n_docs) if self.n_docs else 0.0
        df: Counter[str] = Counter()
        for tf in self._tfs:
            df.update(tf.keys())
        # BM25+ style non-negative IDF (Lucene variant).
        self._idf = {term: math.log(1 + (self.n_docs - n + 0.5) / (n + 0.5)) for term, n in df.items()}

    def idf(self, term: str) -> float:
        return self._idf.get(term, 0.0)

    def score(self, query: Sequence[str], index: int) -> float:
        tf = self._tfs[index]
        length = self._lengths[index]
        norm = self.k1 * (1 - self.b + self.b * length / self.avgdl) if self.avgdl else self.k1
        total = 0.0
        for term in set(query):
            freq = tf.get(term, 0)
            if freq:
                total += self.idf(term) * freq * (self.k1 + 1) / (freq + norm)
        return total

    def rank(self, query: Sequence[str], candidates: Sequence[int] | None = None) -> list[tuple[int, float]]:
        """Return (doc index, score) for documents with a positive score, best first.

        Ties are broken by document index so results are deterministic.
        """
        pool = range(self.n_docs) if candidates is None else candidates
        scored = [(i, self.score(query, i)) for i in pool]
        return sorted((s for s in scored if s[1] > 0), key=lambda s: (-s[1], s[0]))
