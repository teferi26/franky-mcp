from __future__ import annotations

import json
from pathlib import Path

import pytest

from franky_mcp.cli import main as cli_main
from franky_mcp.data import ENV_DATA_DIR, DatasetError, load_dataset


def _edit(path: Path, fn) -> None:
    data = json.loads(path.read_text(encoding="utf-8"))
    fn(data)
    path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")


def test_sample_dataset_loads(dataset):
    assert dataset.metadata.sample is True
    assert "ILLUSTRATIVE" in dataset.metadata.notice
    assert 15 <= len(dataset.universities) <= 20
    assert 80 <= len(dataset.degrees) <= 120
    assert 12 <= len(dataset.scholarships) <= 20


def test_every_record_is_marked_sample(dataset):
    records = [*dataset.universities.values(), *dataset.degrees.values(), *dataset.scholarships.values()]
    assert all(r.source == "sample" for r in records)


def test_cutoffs_in_range_and_sorted(dataset):
    for d in dataset.degrees.values():
        years = [c.year for c in d.cut_offs]
        assert years == sorted(years)
        assert all(5 <= c.score <= 14 for c in d.cut_offs)
        if d.admission_without_cutoff:
            assert d.cut_offs == ()


def test_all_branches_present(dataset):
    assert {d.branch for d in dataset.degrees.values()} == {
        "ciencias", "ciencias_salud", "ingenieria_arquitectura", "artes_humanidades", "ciencias_sociales_juridicas",
    }


def test_some_degrees_without_cutoff(dataset):
    assert any(d.admission_without_cutoff for d in dataset.degrees.values())


def test_env_var_selects_dataset(sample_copy, monkeypatch):
    _edit(sample_copy / "metadata.json", lambda m: m.update(dataset_version="custom-1", sample=False))
    monkeypatch.setenv(ENV_DATA_DIR, str(sample_copy))
    ds = load_dataset()
    assert ds.metadata.dataset_version == "custom-1"
    assert ds.path == sample_copy


def test_score_out_of_range_fails(sample_copy):
    _edit(sample_copy / "degrees.json", lambda d: d[0]["cut_offs"][0].update(score=15.2))
    with pytest.raises(DatasetError, match=r"(?s)degrees.json failed validation.*cut_offs.0.score"):
        load_dataset(sample_copy)


def test_score_below_five_fails(sample_copy):
    _edit(sample_copy / "degrees.json", lambda d: d[0]["cut_offs"][0].update(score=4.0))
    with pytest.raises(DatasetError, match="greater than or equal to 5"):
        load_dataset(sample_copy)


def test_unknown_university_fails(sample_copy):
    _edit(sample_copy / "degrees.json", lambda d: d[0].update(university_id="nope"))
    with pytest.raises(DatasetError, match="unknown university_id 'nope'"):
        load_dataset(sample_copy)


def test_duplicate_id_fails(sample_copy):
    _edit(sample_copy / "degrees.json", lambda d: d.append(dict(d[0])))
    with pytest.raises(DatasetError, match="duplicate id"):
        load_dataset(sample_copy)


def test_duplicate_year_fails(sample_copy):
    _edit(sample_copy / "degrees.json", lambda d: d[0]["cut_offs"].append(dict(d[0]["cut_offs"][-1])))
    with pytest.raises(DatasetError, match="duplicate years"):
        load_dataset(sample_copy)


def test_without_cutoff_with_scores_fails(sample_copy):
    _edit(sample_copy / "degrees.json", lambda d: d[0].update(admission_without_cutoff=True))
    with pytest.raises(DatasetError, match="admission_without_cutoff"):
        load_dataset(sample_copy)


def test_unknown_branch_and_extra_field_fail(sample_copy):
    _edit(sample_copy / "degrees.json", lambda d: (d[0].update(branch="magia"), d[1].update(colour="red")))
    with pytest.raises(DatasetError) as exc:
        load_dataset(sample_copy)
    assert "branch" in str(exc.value) and "colour" in str(exc.value)


def test_regional_scholarship_requires_region(sample_copy):
    def bad(items):
        regional = next(s for s in items if s["scope"] == "regional")
        regional["regions"] = []
    _edit(sample_copy / "scholarships.json", bad)
    with pytest.raises(DatasetError, match="regional scholarship"):
        load_dataset(sample_copy)


def test_invalid_json_fails(sample_copy):
    (sample_copy / "universities.json").write_text("[{oops", encoding="utf-8")
    with pytest.raises(DatasetError, match="not valid JSON"):
        load_dataset(sample_copy)


def test_missing_file_and_dir_fail(sample_copy, tmp_path):
    (sample_copy / "scholarships.json").unlink()
    with pytest.raises(DatasetError, match="Missing dataset file"):
        load_dataset(sample_copy)
    with pytest.raises(DatasetError, match="directory not found"):
        load_dataset(tmp_path / "does-not-exist")


def test_not_an_array_fails(sample_copy):
    (sample_copy / "degrees.json").write_text("{}", encoding="utf-8")
    with pytest.raises(DatasetError, match="must contain a JSON array"):
        load_dataset(sample_copy)


def test_cli_check_data(capsys, sample_copy):
    assert cli_main(["--check-data"]) == 0
    assert "sample=True" in capsys.readouterr().out
    (sample_copy / "metadata.json").write_text("{}", encoding="utf-8")
    assert cli_main(["--check-data", "--data-dir", str(sample_copy)]) == 2
    assert "invalid dataset" in capsys.readouterr().err
