from __future__ import annotations

import pytest

from franky_mcp.service import SAMPLE_DATA_NOTICE, ToolInputError


def ids(result):
    return [r["id"] for r in result["results"]]


# ------------------------------------------------------------------ search_degrees

def test_search_ranks_relevant_degree_first(service):
    res = service.search_degrees("medicina en Sevilla")
    assert ids(res)[0] == "us-medicina"
    assert res["data_notice"] == SAMPLE_DATA_NOTICE


def test_search_is_accent_insensitive(service):
    assert ids(service.search_degrees("Psicología")) == ids(service.search_degrees("psicologia"))


def test_search_synonym_informatica(service):
    top = ids(service.search_degrees("informatica", limit=5))
    assert all("ingenieria-informatica" in i for i in top)


def test_search_filters(service):
    res = service.search_degrees("ingenieria", region="cataluna", branch="ingenieria_arquitectura", limit=25)
    assert res["results"]
    assert all(r["region"] == "Cataluña" and r["branch"] == "ingenieria_arquitectura" for r in res["results"])
    uni = service.search_degrees("", university="UC3M", limit=25)
    assert {r["university_id"] for r in uni["results"]} == {"uc3m"}


def test_search_university_acronym_beats_name_substring(service):
    # 'us' is a substring of 'Euskal Herriko ...' (EHU); the exact acronym must win.
    res = service.search_degrees("", university="US", limit=25)
    assert {r["university_id"] for r in res["results"]} == {"us"}
    by_name = service.search_degrees("", university="complutense", limit=25)
    assert {r["university_id"] for r in by_name["results"]} == {"ucm"}


def test_search_branch_accepts_label(service):
    res = service.search_degrees("", branch="Ciencias de la Salud", limit=25)
    assert {r["branch"] for r in res["results"]} == {"ciencias_salud"}


def test_search_max_cutoff(service):
    res = service.search_degrees("", max_cutoff=7.0, limit=25)
    assert res["results"]
    for r in res["results"]:
        assert r["admission_without_cutoff"] or r["latest_cut_off"]["score"] <= 7.0


def test_search_limit_bounds_results(service):
    res = service.search_degrees("grado medicina", limit=3)
    assert res["returned"] == 3 and res["total_matches"] > 3


@pytest.mark.parametrize("kwargs, message", [
    ({"limit": 0}, "limit"),
    ({"limit": 26}, "limit"),
    ({"max_cutoff": 15}, "max_cutoff"),
    ({"region": "Narnia"}, "Unknown region"),
    ({"branch": "magia"}, "Unknown branch"),
    ({"university": "Hogwarts"}, "No university"),
])
def test_search_invalid_input(service, kwargs, message):
    with pytest.raises(ToolInputError, match=message):
        service.search_degrees("medicina", **kwargs)


# --------------------------------------------------------------------- get_degree

def test_get_degree_has_history(service):
    res = service.get_degree("ucm-medicina")
    deg = res["degree"]
    assert deg["name"] == "Grado en Medicina"
    assert res["university"]["id"] == "ucm"
    years = [c["year"] for c in deg["cut_off_history"]]
    assert years == sorted(years) and len(years) >= 3
    assert deg["latest_cut_off"]["year"] == years[-1]
    assert deg["cut_off_history"][-1]["academic_year"] == f"{years[-1]}/{years[-1] + 1}"
    assert deg["trend"]["direction"] in {"up", "down", "stable"}
    assert "data_notice" in res


def test_get_degree_without_cutoff(service):
    deg = service.get_degree("ucm-filosofia")["degree"]
    assert deg["admission_without_cutoff"] is True
    assert deg["latest_cut_off"] is None and deg["cut_off_history"] == []


def test_get_degree_unknown_suggests(service):
    with pytest.raises(ToolInputError, match="Did you mean: ucm-medicina"):
        service.get_degree("ucm-medicin")


# ---------------------------------------------------------------- compare_degrees

def test_compare_degrees(service):
    res = service.compare_degrees(["ucm-medicina", "us-medicina", "ucm-filosofia"])
    assert [d["id"] for d in res["degrees"]] == ["ucm-medicina", "us-medicina", "ucm-filosofia"]
    s = res["summary"]
    assert s["without_cutoff"] == ["ucm-filosofia"]
    assert s["highest_cut_off"]["score"] >= s["lowest_cut_off"]["score"]
    assert "data_notice" in res


@pytest.mark.parametrize("bad", [["ucm-medicina"], ["a", "b", "c", "d", "e", "f"], ["ucm-medicina", "ucm-medicina"]])
def test_compare_degrees_invalid(service, bad):
    with pytest.raises(ToolInputError):
        service.compare_degrees(bad)


# ---------------------------------------------------------------- admission_check

def test_admission_check_margins(service, dataset):
    cut = dataset.degrees["ub-psicologia"].latest_cut_off
    res = service.admission_check(cut.score + 0.6, degree_ids=["ub-psicologia"])
    row = res["results"][0]
    assert row["status"] == "above" and row["meets_cut_off"] is True
    assert row["margin"] == pytest.approx(0.6, abs=1e-3)
    assert row["year_used"] == cut.year and row["band"] == "safe"
    assert "change every year" in res["caveat"]
    assert "data_notice" in res

    low = service.admission_check(cut.score - 0.5, degree_ids=["ub-psicologia"])["results"][0]
    assert low["status"] == "below" and low["band"] == "reach" and low["margin"] < 0
    far = service.admission_check(5.0, degree_ids=["ucm-medicina"])["results"][0]
    assert far["band"] == "long_shot"


def test_admission_check_equal_is_match(service, dataset):
    cut = dataset.degrees["us-derecho"].latest_cut_off.score
    row = service.admission_check(cut, degree_ids=["us-derecho"])["results"][0]
    assert row["status"] == "above" and row["margin"] == 0 and row["band"] == "match"


def test_admission_check_without_cutoff(service):
    row = service.admission_check(6.0, degree_ids=["ucm-filosofia"])["results"][0]
    assert row["status"] == "no_cutoff" and row["meets_cut_off"] is True


def test_admission_check_by_query(service):
    res = service.admission_check(11.0, query="enfermeria", limit=5)
    assert len(res["results"]) == 5
    assert sum(res["summary"].values()) == 5
    assert all("enfermeria" in r["id"] for r in res["results"])


@pytest.mark.parametrize("kwargs", [
    {"grade": 15, "degree_ids": ["ucm-medicina"]},
    {"grade": -1, "degree_ids": ["ucm-medicina"]},
    {"grade": 10},
    {"grade": 10, "degree_ids": ["ucm-medicina"], "query": "medicina"},
    {"grade": 10, "degree_ids": ["nope"]},
    {"grade": 10, "degree_ids": [f"x{i}" for i in range(21)]},
])
def test_admission_check_invalid(service, kwargs):
    with pytest.raises(ToolInputError):
        service.admission_check(**kwargs)


# ------------------------------------------------------------- find_scholarships

def test_find_scholarships_regional_filtering(service):
    res = service.find_scholarships(region="madrid", level="grado", max_family_income=15000, min_grade=9.5)
    found = {r["id"] for r in res["results"]}
    assert "sch-madrid-excelencia" in found
    assert "sch-general-ministerio" in found
    assert not any(r["scope"] == "regional" and "Madrid" not in r["regions"] for r in res["results"])
    assert all(r["eligibility"] == "likely" for r in res["results"])
    excluded = {e["id"]: e["reason"] for e in res["excluded"]}
    assert "Only for" in excluded["sch-cataluna-matricula"]
    assert "data_notice" in res


def test_find_scholarships_income_and_grade_exclusion(service):
    res = service.find_scholarships(region="Galicia", level="grado", max_family_income=60000, min_grade=6.0)
    found = {r["id"] for r in res["results"]}
    assert "sch-general-ministerio" not in found
    assert "sch-movilidad-internacional" in found  # no income ceiling
    reasons = {e["id"]: e["reason"] for e in res["excluded"]}
    assert "exceeds the ceiling" in reasons["sch-general-ministerio"]
    assert "below the minimum" in reasons["sch-excelencia-estatal"]


def test_find_scholarships_missing_profile_marks_check(service):
    res = service.find_scholarships(limit=20)
    assert res["total_matches"] == len(service.ds.scholarships)
    assert all(r["eligibility"] == "check" for r in res["results"])
    assert all(r["eligibility_reasons"] for r in res["results"])


def test_find_scholarships_level_filter(service):
    res = service.find_scholarships(level="fp_grado_medio", limit=20)
    assert res["results"] and all("fp_grado_medio" in r["levels"] for r in res["results"])


@pytest.mark.parametrize("kwargs", [
    {"level": "doctorado"}, {"region": "Atlantis"}, {"min_grade": 11}, {"max_family_income": -5}, {"limit": 0},
])
def test_find_scholarships_invalid(service, kwargs):
    with pytest.raises(ToolInputError):
        service.find_scholarships(**kwargs)


# -------------------------------------------------------------- list_universities

def test_list_universities(service, dataset):
    res = service.list_universities()
    assert res["count"] == len(dataset.universities)
    assert sum(u["degree_count"] for u in res["universities"]) == len(dataset.degrees)
    madrid = service.list_universities("MADRID")
    assert {u["id"] for u in madrid["universities"]} == {"ucm", "uam", "uc3m", "upm"}
    assert "data_notice" in madrid


def test_resources(service):
    meta = service.metadata_resource()
    assert meta["sample"] is True and meta["counts"]["degrees"] == len(service.ds.degrees)
    uni = service.university_resource("ub")
    assert uni["university"]["name"] == "Universitat de Barcelona" and uni["degrees"]
    with pytest.raises(ToolInputError):
        service.university_resource("nope")
