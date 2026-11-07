"""Pydantic models for the dataset. Loading validates every record against these."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

Branch = Literal[
    "ciencias",
    "ciencias_salud",
    "ingenieria_arquitectura",
    "artes_humanidades",
    "ciencias_sociales_juridicas",
]

BRANCH_LABELS: dict[str, str] = {
    "ciencias": "Ciencias",
    "ciencias_salud": "Ciencias de la Salud",
    "ingenieria_arquitectura": "Ingeniería y Arquitectura",
    "artes_humanidades": "Artes y Humanidades",
    "ciencias_sociales_juridicas": "Ciencias Sociales y Jurídicas",
}

Level = Literal["bachillerato", "fp_grado_medio", "fp_grado_superior", "grado", "master"]
LEVELS: tuple[str, ...] = ("bachillerato", "fp_grado_medio", "fp_grado_superior", "grado", "master")

# Cut-off scores in Spain are expressed over 14 (PAU/EBAU admission grade). A published
# cut-off below 5 is not meaningful: 5 is the minimum admission grade.
MIN_CUTOFF = 5.0
MAX_CUTOFF = 14.0

_ID_PATTERN = r"^[a-z0-9][a-z0-9-]{0,79}$"


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, str_strip_whitespace=True)


class Metadata(_Strict):
    dataset_version: str = Field(min_length=1)
    sample: bool
    notice: str = Field(min_length=1)
    latest_cut_off_year: int = Field(ge=2000, le=2100)
    score_scale: str = ""
    description: str = ""


class University(_Strict):
    id: str = Field(pattern=_ID_PATTERN)
    name: str = Field(min_length=2)
    short_name: str = Field(min_length=1)
    city: str = Field(min_length=1)
    region: str = Field(min_length=1)
    ownership: Literal["public", "private"] = "public"
    source: str = Field(min_length=1)


class CutOff(_Strict):
    year: int = Field(ge=2000, le=2100, description="First calendar year of the academic year: 2025 = 2025/2026.")
    score: float = Field(ge=MIN_CUTOFF, le=MAX_CUTOFF)
    round: str = "ordinaria"


class Degree(_Strict):
    id: str = Field(pattern=_ID_PATTERN)
    name: str = Field(min_length=2)
    university_id: str = Field(pattern=_ID_PATTERN)
    branch: Branch
    campus: str = Field(min_length=1)
    duration_years: int = Field(ge=1, le=7)
    credits_ects: int = Field(ge=60, le=420)
    admission_without_cutoff: bool = False
    cut_offs: tuple[CutOff, ...] = ()
    keywords: tuple[str, ...] = ()
    source: str = Field(min_length=1)

    @field_validator("cut_offs")
    @classmethod
    def _unique_years(cls, value: tuple[CutOff, ...]) -> tuple[CutOff, ...]:
        years = [c.year for c in value]
        if len(years) != len(set(years)):
            raise ValueError("cut_offs has duplicate years")
        return tuple(sorted(value, key=lambda c: c.year))

    @model_validator(mode="after")
    def _cutoff_consistency(self) -> Degree:
        if self.admission_without_cutoff and self.cut_offs:
            raise ValueError("a degree with admission_without_cutoff=true must not list cut_offs")
        return self

    @property
    def latest_cut_off(self) -> CutOff | None:
        return self.cut_offs[-1] if self.cut_offs else None


class Scholarship(_Strict):
    id: str = Field(pattern=_ID_PATTERN)
    name: str = Field(min_length=2)
    provider: str = Field(min_length=1)
    scope: Literal["national", "regional"]
    regions: tuple[str, ...] = ()
    levels: tuple[Level, ...] = Field(min_length=1)
    max_family_income: float | None = Field(default=None, gt=0, description="Annual family income ceiling in EUR.")
    min_grade: float | None = Field(default=None, ge=0, le=10, description="Minimum average grade over 10.")
    amount_min_eur: float = Field(ge=0)
    amount_max_eur: float = Field(ge=0)
    description: str = ""
    requirements: tuple[str, ...] = ()
    source: str = Field(min_length=1)

    @model_validator(mode="after")
    def _check(self) -> Scholarship:
        if self.amount_max_eur < self.amount_min_eur:
            raise ValueError("amount_max_eur must be >= amount_min_eur")
        if self.scope == "regional" and not self.regions:
            raise ValueError("a regional scholarship must list at least one region")
        if self.scope == "national" and self.regions:
            raise ValueError("a national scholarship must not list regions")
        return self
