"""Dataset loading and validation."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from importlib import resources
from pathlib import Path
from typing import Any

from pydantic import BaseModel, TypeAdapter, ValidationError

from .models import Degree, Metadata, Scholarship, University

ENV_DATA_DIR = "FRANKY_DATA_DIR"
FILES = ("metadata.json", "universities.json", "degrees.json", "scholarships.json")


class DatasetError(Exception):
    """Raised when a dataset is missing, malformed or inconsistent."""


@dataclass(frozen=True)
class Dataset:
    metadata: Metadata
    universities: dict[str, University]
    degrees: dict[str, Degree]
    scholarships: dict[str, Scholarship]
    path: Path | None = None
    degrees_by_university: dict[str, list[str]] = field(default_factory=dict)

    @property
    def counts(self) -> dict[str, int]:
        return {
            "universities": len(self.universities),
            "degrees": len(self.degrees),
            "scholarships": len(self.scholarships),
        }

    @property
    def regions(self) -> list[str]:
        return sorted({u.region for u in self.universities.values()} | {
            r for s in self.scholarships.values() for r in s.regions
        })


def default_data_dir() -> Path:
    """The bundled sample dataset.

    In a source checkout / editable install this is ``<repo>/data/sample``; in a
    wheel it is packaged as ``franky_mcp/_data/sample``.
    """
    packaged = Path(str(resources.files("franky_mcp") / "_data" / "sample"))
    if packaged.is_dir():
        return packaged
    repo_root = Path(__file__).resolve().parents[2]
    return repo_root / "data" / "sample"


def resolve_data_dir(explicit: str | Path | None = None) -> Path:
    if explicit:
        return Path(explicit)
    env = os.environ.get(ENV_DATA_DIR)
    return Path(env) if env else default_data_dir()


def _read_json(path: Path) -> Any:
    if not path.is_file():
        raise DatasetError(f"Missing dataset file: {path}")
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise DatasetError(f"{path.name} is not valid JSON (line {exc.lineno}, column {exc.colno}): {exc.msg}") from exc


def _format_validation(file: str, exc: ValidationError) -> str:
    lines = [f"{file} failed validation ({exc.error_count()} error(s)):"]
    for err in exc.errors()[:10]:
        loc = ".".join(str(p) for p in err["loc"])
        lines.append(f"  - [{loc}] {err['msg']}")
    if exc.error_count() > 10:
        lines.append(f"  ... and {exc.error_count() - 10} more")
    return "\n".join(lines)


def _parse_list(file: str, raw: Any, model: type[BaseModel]) -> list[Any]:
    if not isinstance(raw, list):
        raise DatasetError(f"{file} must contain a JSON array")
    try:
        return TypeAdapter(list[model]).validate_python(raw)  # type: ignore[valid-type]
    except ValidationError as exc:
        raise DatasetError(_format_validation(file, exc)) from exc


def _index(file: str, items: list[Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for item in items:
        if item.id in out:
            raise DatasetError(f"{file}: duplicate id '{item.id}'")
        out[item.id] = item
    return out


def load_dataset(data_dir: str | Path | None = None) -> Dataset:
    """Load and validate a dataset directory. Raises DatasetError with a clear message."""
    path = resolve_data_dir(data_dir)
    if not path.is_dir():
        raise DatasetError(f"Dataset directory not found: {path}")

    try:
        metadata = Metadata.model_validate(_read_json(path / "metadata.json"))
    except ValidationError as exc:
        raise DatasetError(_format_validation("metadata.json", exc)) from exc

    universities = _index("universities.json", _parse_list(
        "universities.json", _read_json(path / "universities.json"), University))
    degrees = _index("degrees.json", _parse_list("degrees.json", _read_json(path / "degrees.json"), Degree))
    scholarships = _index("scholarships.json", _parse_list(
        "scholarships.json", _read_json(path / "scholarships.json"), Scholarship))

    by_uni: dict[str, list[str]] = {uid: [] for uid in universities}
    for degree in degrees.values():
        if degree.university_id not in universities:
            raise DatasetError(
                f"degrees.json: degree '{degree.id}' references unknown university_id '{degree.university_id}'"
            )
        by_uni[degree.university_id].append(degree.id)

    return Dataset(
        metadata=metadata,
        universities=universities,
        degrees=degrees,
        scholarships=scholarships,
        path=path,
        degrees_by_university=by_uni,
    )
