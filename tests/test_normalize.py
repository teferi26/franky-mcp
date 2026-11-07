from franky_mcp.normalize import expand_query, normalize, same, stem, tokenize


def test_normalize_strips_accents_and_case():
    assert normalize("  Ingeniería   INFORMÁTICA ") == "ingenieria informatica"
    assert normalize("Cataluña") == "cataluna"
    assert normalize("País Vasco / Euskal-Herria") == "pais vasco euskal herria"


def test_same_is_accent_insensitive():
    assert same("Andalucía", "andalucia")
    assert not same("Madrid", "Murcia")


def test_stem_collapses_plurals():
    assert stem("matematicas") == stem("matematica")
    assert stem("ingleses") == stem("ingles")
    assert stem("relaciones") == stem("relacion")
    assert stem("ade") == "ade"


def test_tokenize_drops_stopwords():
    assert tokenize("Quiero estudiar el grado de Medicina en Madrid") == ["medicina", "madrid"]


def test_expand_query_adds_synonyms():
    assert expand_query("Informática") == "informatica ingenieria informatica"
    assert "administracion" in expand_query("ADE")
    assert expand_query("medicina") == "medicina"
