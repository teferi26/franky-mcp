"""Text normalization shared by search and filters (accent- and case-insensitive)."""

from __future__ import annotations

import re
import unicodedata

_NON_WORD = re.compile(r"[^a-z0-9]+")

# Words that carry no signal in Spanish (and a few English) degree queries.
STOPWORDS = frozenset(
    """
    a al algo con como de del el en es esta este grado grados carrera carreras estudiar estudio
    hacer la las lo los me mi para por que quiero quisiera se sobre su un una uno y o u e
    universidad universidades donde cual cuales hay puedo busco buscando gustaria gusta
    the of in and for to i want study degree degrees
    """.split()
)

# Query-side expansions for a few common colloquial terms. Keys and values are
# already normalized. The expansion is appended to the query, so the original term
# still counts.
SYNONYMS: dict[str, str] = {
    "informatica": "ingenieria informatica",
    "computacion": "ingenieria informatica",
    "programacion": "ingenieria informatica",
    "ade": "administracion direccion empresas",
    "empresariales": "administracion direccion empresas",
    "empresas": "administracion direccion empresas",
    "magisterio": "maestro educacion primaria",
    "maestro": "maestro educacion primaria",
    "teleco": "telecomunicacion",
    "aeronautica": "aeroespacial",
    "aviones": "aeroespacial",
    "fisio": "fisioterapia",
    "psico": "psicologia",
    "mates": "matematicas",
    "ingles": "estudios ingleses",
    "dentista": "odontologia",
    "abogado": "derecho",
    "medico": "medicina",
    "traductor": "traduccion interpretacion",
    "ia": "ciencia datos inteligencia artificial",
    "datos": "ciencia ingenieria datos",
    "arquitecto": "arquitectura",
}


def normalize(text: str) -> str:
    """Lower-case, strip accents and collapse non-alphanumerics to single spaces."""
    decomposed = unicodedata.normalize("NFD", text)
    without_accents = "".join(ch for ch in decomposed if unicodedata.category(ch) != "Mn")
    return _NON_WORD.sub(" ", without_accents.lower()).strip()


def stem(token: str) -> str:
    """Very light plural stripping so 'matematicas' and 'matematica' match.

    Applied until it reaches a fixed point, so singular and plural forms
    ('ingles' / 'ingleses', 'relacion' / 'relaciones') collapse to the same stem.
    """
    while True:
        if len(token) > 5 and token.endswith("es") and token[-3] not in "aeiou":
            token = token[:-2]
        elif len(token) > 4 and token.endswith("s"):
            token = token[:-1]
        else:
            return token


def tokenize(text: str) -> list[str]:
    """Normalize, drop stopwords and stem."""
    return [stem(t) for t in normalize(text).split() if t not in STOPWORDS]


def expand_query(text: str) -> str:
    """Append synonym expansions for any colloquial term found in the query."""
    words = normalize(text).split()
    extra = [SYNONYMS[w] for w in words if w in SYNONYMS]
    return " ".join([*words, *extra])


def same(a: str, b: str) -> bool:
    """Accent/case-insensitive equality."""
    return normalize(a) == normalize(b)
