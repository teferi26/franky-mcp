# Dataset schema

franky-mcp loads a dataset from a directory containing four JSON files. The bundled
one lives in `data/sample/`; point `FRANKY_DATA_DIR` (or `--data-dir`) at another
directory with the same layout to use your own data.

```
<data dir>/
  metadata.json       object
  universities.json   array of University
  degrees.json        array of Degree
  scholarships.json   array of Scholarship
```

Every file is validated on load with the pydantic models in
[`src/franky_mcp/models.py`](../src/franky_mcp/models.py). Unknown fields are
rejected (`extra="forbid"`), and the server refuses to start with a message that
names the file, the record path and the problem, for example:

```
franky-mcp: invalid dataset
degrees.json failed validation (1 error(s)):
  - [3.cut_offs.0.score] Input should be less than or equal to 14
```

Validate a directory without starting the server:

```bash
franky-mcp --check-data --data-dir ./my-data
```

## Conventions

- **ids** match `^[a-z0-9][a-z0-9-]{0,79}$` and are unique within their file.
  Degree ids in the sample are `<university id>-<slug>`, e.g. `ucm-medicina`.
- **Text matching** (regions, university names, search) is accent- and
  case-insensitive, so `Andalucia` matches `Andalucía`.
- **source**: free text describing provenance. Every record in the bundled
  dataset has `"source": "sample"`.

## metadata.json

| field | type | notes |
|---|---|---|
| `dataset_version` | string | required |
| `sample` | bool | required. `true` makes every tool response carry the illustrative-data notice |
| `notice` | string | required. Shown in the metadata resource; used as `data_notice` when `sample` is `false` |
| `latest_cut_off_year` | int | first calendar year of the latest academic year covered (2025 = 2025/2026) |
| `score_scale` | string | optional, human-readable |
| `description` | string | optional |

## University

| field | type | notes |
|---|---|---|
| `id` | string | e.g. `usal` |
| `name` | string | e.g. `Universidad de Salamanca` |
| `short_name` | string | acronym, e.g. `USAL` (usable as the `university` filter) |
| `city` | string | |
| `region` | string | autonomous community, e.g. `Castilla y León` |
| `ownership` | `"public"` \| `"private"` | default `"public"` |
| `source` | string | |

## Degree

| field | type | notes |
|---|---|---|
| `id` | string | |
| `name` | string | e.g. `Grado en Medicina` |
| `university_id` | string | must exist in `universities.json` |
| `branch` | enum | `ciencias`, `ciencias_salud`, `ingenieria_arquitectura`, `artes_humanidades`, `ciencias_sociales_juridicas` |
| `campus` | string | city/campus where it is taught |
| `duration_years` | int | 1-7 |
| `credits_ects` | int | 60-420 |
| `admission_without_cutoff` | bool | default `false`. `true` means every eligible applicant was admitted ("sin nota de corte"); then `cut_offs` must be empty |
| `cut_offs` | array of CutOff | at most one entry per year; sorted by year on load |
| `keywords` | array of string | extra search terms (indexed by BM25 with lower weight than the name) |
| `source` | string | |

### CutOff

| field | type | notes |
|---|---|---|
| `year` | int | first calendar year of the academic year: `2025` = 2025/2026 |
| `score` | float | **5 to 14** (Spanish PAU/EBAU admission grade over 14: 10 from the access phase plus up to 4 from the specific phase). Values outside this range are rejected |
| `round` | string | default `"ordinaria"` |

## Scholarship

| field | type | notes |
|---|---|---|
| `id` | string | |
| `name` | string | |
| `provider` | string | awarding body, described generically |
| `scope` | `"national"` \| `"regional"` | |
| `regions` | array of string | required (non-empty) for `regional`, must be empty for `national` |
| `levels` | array of enum | non-empty; `bachillerato`, `fp_grado_medio`, `fp_grado_superior`, `grado`, `master` |
| `max_family_income` | float \| null | annual family income ceiling in EUR; `null` = no ceiling |
| `min_grade` | float \| null | minimum average grade **over 10**; `null` = none |
| `amount_min_eur`, `amount_max_eur` | float | `amount_max_eur >= amount_min_eur` |
| `description` | string | optional |
| `requirements` | array of string | optional, human-readable |
| `source` | string | |

## Minimal example

```json
// degrees.json
[
  {
    "id": "usal-medicina",
    "name": "Grado en Medicina",
    "university_id": "usal",
    "branch": "ciencias_salud",
    "campus": "Salamanca",
    "duration_years": 6,
    "credits_ects": 360,
    "cut_offs": [{ "year": 2024, "score": 12.9 }, { "year": 2025, "score": 13.0 }],
    "keywords": ["medico"],
    "source": "sample"
  }
]
```

The sample dataset is produced by `scripts/generate_sample_data.py`, which is a
working reference for writing a converter from another source.
