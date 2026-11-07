"""Tool logic, independent of the MCP transport so it can be unit-tested directly.

Every public method returns a JSON-serializable dict that includes ``data_notice``.
Invalid input raises :class:`ToolInputError` with a message meant for the agent.
"""

from __future__ import annotations

import difflib
from typing import Any

from .bm25 import BM25
from .data import Dataset
from .models import BRANCH_LABELS, LEVELS, MAX_CUTOFF, Degree, Scholarship, University
from .normalize import expand_query, normalize, tokenize

SAMPLE_DATA_NOTICE = (
    "Illustrative sample data: cut-off scores, scholarship amounts and income thresholds are NOT official. "
    "Always check the university's (and the awarding body's) official publication before deciding."
)
OFFICIAL_CHECK_NOTICE = (
    "Cut-off scores and scholarship rules change every year; always confirm with the university's "
    "and the awarding body's official publication."
)
CUTOFF_CAVEAT = (
    "Cut-off scores ('notas de corte') are the grade of the last admitted student in a given year. "
    "They change every year with demand and places offered, so a past cut-off is a reference, not a guarantee."
)

MAX_SEARCH_LIMIT = 25
MAX_SCHOLARSHIP_LIMIT = 20
MAX_ADMISSION_DEGREES = 20
NAME_WEIGHT = 3


class ToolInputError(ValueError):
    """Invalid arguments for a tool. The message is returned to the agent."""


def academic_year(year: int) -> str:
    return f"{year}/{year + 1}"


def _check_limit(limit: int, maximum: int) -> int:
    if not isinstance(limit, int) or isinstance(limit, bool) or not 1 <= limit <= maximum:
        raise ToolInputError(f"limit must be an integer between 1 and {maximum} (got {limit!r}).")
    return limit


class FrankyService:
    def __init__(self, dataset: Dataset) -> None:
        self.ds = dataset
        self._degree_ids = sorted(dataset.degrees)
        docs = [self._degree_tokens(dataset.degrees[i]) for i in self._degree_ids]
        self._bm25 = BM25(docs)
        if dataset.metadata.sample:
            self.data_notice = SAMPLE_DATA_NOTICE
        else:
            self.data_notice = f"{dataset.metadata.notice} {OFFICIAL_CHECK_NOTICE}".strip()

    # ------------------------------------------------------------------ helpers

    def _degree_tokens(self, degree: Degree) -> list[str]:
        uni = self.ds.universities[degree.university_id]
        name_tokens = tokenize(degree.name)
        other = " ".join([
            " ".join(degree.keywords),
            BRANCH_LABELS[degree.branch],
            uni.name,
            uni.short_name,
            uni.city,
            degree.campus,
            uni.region,
        ])
        return name_tokens * NAME_WEIGHT + tokenize(other)

    def _wrap(self, payload: dict[str, Any]) -> dict[str, Any]:
        payload["data_notice"] = self.data_notice
        return payload

    def _resolve_region(self, region: str | None) -> str | None:
        if region is None or not region.strip():
            return None
        target = normalize(region)
        for known in self.ds.regions:
            if normalize(known) == target:
                return known
        raise ToolInputError(
            f"Unknown region '{region}'. Valid regions in this dataset: {', '.join(self.ds.regions)}."
        )

    def _resolve_branch(self, branch: str | None) -> str | None:
        if branch is None or not branch.strip():
            return None
        target = normalize(branch).replace(" ", "_")
        for key, label in BRANCH_LABELS.items():
            if target == key or normalize(label).replace(" ", "_") == target:
                return key
        valid = ", ".join(f"{k} ({v})" for k, v in BRANCH_LABELS.items())
        raise ToolInputError(f"Unknown branch '{branch}'. Valid branches: {valid}.")

    def _resolve_universities(self, university: str | None) -> set[str] | None:
        if university is None or not university.strip():
            return None
        target = normalize(university)
        unis = self.ds.universities.values()
        # An exact id or acronym wins, so 'US' does not also match 'Euskal ...' by substring.
        matches = {u.id for u in unis if target in (normalize(u.id), normalize(u.short_name))}
        if not matches:
            matches = {u.id for u in unis if target in normalize(u.name)}
        if not matches:
            raise ToolInputError(
                f"No university matches '{university}'. Use list_universities to see ids and names."
            )
        return matches

    def _degree(self, degree_id: str) -> Degree:
        degree = self.ds.degrees.get(degree_id.strip() if isinstance(degree_id, str) else degree_id)
        if degree is None:
            close = difflib.get_close_matches(str(degree_id), self._degree_ids, n=3, cutoff=0.5)
            hint = f" Did you mean: {', '.join(close)}?" if close else " Use search_degrees to find valid ids."
            raise ToolInputError(f"Unknown degree_id '{degree_id}'.{hint}")
        return degree

    @staticmethod
    def _admission_label(degree: Degree) -> str:
        if degree.admission_without_cutoff:
            return "Admission without cut-off (sin nota de corte)"
        latest = degree.latest_cut_off
        if latest is None:
            return "No cut-off published in this dataset"
        return f"{latest.score:.3f} ({academic_year(latest.year)})"

    def _university_dict(self, uni: University) -> dict[str, Any]:
        return {
            "id": uni.id,
            "name": uni.name,
            "short_name": uni.short_name,
            "city": uni.city,
            "region": uni.region,
            "ownership": uni.ownership,
            "degree_count": len(self.ds.degrees_by_university.get(uni.id, [])),
            "source": uni.source,
        }

    def degree_summary(self, degree: Degree) -> dict[str, Any]:
        uni = self.ds.universities[degree.university_id]
        latest = degree.latest_cut_off
        return {
            "id": degree.id,
            "name": degree.name,
            "university_id": uni.id,
            "university": uni.name,
            "city": degree.campus,
            "region": uni.region,
            "branch": degree.branch,
            "branch_label": BRANCH_LABELS[degree.branch],
            "admission_without_cutoff": degree.admission_without_cutoff,
            "latest_cut_off": None if latest is None else {
                "year": latest.year,
                "academic_year": academic_year(latest.year),
                "score": latest.score,
            },
            "admission_label": self._admission_label(degree),
            "source": degree.source,
        }

    @staticmethod
    def _trend(degree: Degree) -> dict[str, Any] | None:
        if len(degree.cut_offs) < 2:
            return None
        prev, last = degree.cut_offs[-2], degree.cut_offs[-1]
        delta = round(last.score - prev.score, 3)
        direction = "up" if delta > 0.05 else "down" if delta < -0.05 else "stable"
        return {"from_year": prev.year, "to_year": last.year, "delta": delta, "direction": direction}

    # -------------------------------------------------------------------- tools

    def search_degrees(
        self,
        query: str,
        region: str | None = None,
        branch: str | None = None,
        university: str | None = None,
        max_cutoff: float | None = None,
        limit: int = 10,
    ) -> dict[str, Any]:
        _check_limit(limit, MAX_SEARCH_LIMIT)
        if not isinstance(query, str):
            raise ToolInputError("query must be a string.")
        if len(query) > 300:
            raise ToolInputError("query is too long (max 300 characters).")
        if max_cutoff is not None and not 5 <= max_cutoff <= MAX_CUTOFF:
            raise ToolInputError("max_cutoff must be between 5 and 14 (Spanish admission grade over 14).")
        region_key = self._resolve_region(region)
        branch_key = self._resolve_branch(branch)
        uni_ids = self._resolve_universities(university)

        candidates: list[int] = []
        for idx, did in enumerate(self._degree_ids):
            d = self.ds.degrees[did]
            uni = self.ds.universities[d.university_id]
            if region_key and normalize(uni.region) != normalize(region_key):
                continue
            if branch_key and d.branch != branch_key:
                continue
            if uni_ids is not None and d.university_id not in uni_ids:
                continue
            if max_cutoff is not None and not d.admission_without_cutoff:
                latest = d.latest_cut_off
                if latest is None or latest.score > max_cutoff:
                    continue
            candidates.append(idx)

        tokens = tokenize(expand_query(query))
        if tokens:
            ranked = self._bm25.rank(tokens, candidates)
        else:
            # No meaningful query terms: list filtered degrees alphabetically.
            ordered = sorted(candidates, key=lambda i: (self.ds.degrees[self._degree_ids[i]].name, self._degree_ids[i]))
            ranked = [(i, 0.0) for i in ordered]

        results = []
        for idx, score in ranked[:limit]:
            item = self.degree_summary(self.ds.degrees[self._degree_ids[idx]])
            item["relevance"] = round(score, 4)
            results.append(item)
        return self._wrap({
            "query": query,
            "filters": {"region": region_key, "branch": branch_key, "university": university,
                        "max_cutoff": max_cutoff},
            "total_matches": len(ranked),
            "returned": len(results),
            "results": results,
        })

    def get_degree(self, degree_id: str) -> dict[str, Any]:
        degree = self._degree(degree_id)
        uni = self.ds.universities[degree.university_id]
        detail = self.degree_summary(degree)
        detail.update({
            "campus": degree.campus,
            "duration_years": degree.duration_years,
            "credits_ects": degree.credits_ects,
            "keywords": list(degree.keywords),
            "cut_off_history": [
                {"year": c.year, "academic_year": academic_year(c.year), "score": c.score, "round": c.round}
                for c in degree.cut_offs
            ],
            "trend": self._trend(degree),
        })
        return self._wrap({"degree": detail, "university": self._university_dict(uni), "caveat": CUTOFF_CAVEAT})

    def compare_degrees(self, degree_ids: list[str]) -> dict[str, Any]:
        if not isinstance(degree_ids, list) or not 2 <= len(degree_ids) <= 5:
            raise ToolInputError("degree_ids must be a list of 2 to 5 degree ids.")
        if len(set(degree_ids)) != len(degree_ids):
            raise ToolInputError("degree_ids must not contain duplicates.")
        degrees = [self._degree(d) for d in degree_ids]
        rows = []
        for d in degrees:
            row = self.degree_summary(d)
            row.update({
                "duration_years": d.duration_years,
                "credits_ects": d.credits_ects,
                "cut_off_history": {str(c.year): c.score for c in d.cut_offs},
                "trend": self._trend(d),
            })
            rows.append(row)
        with_score = [r for r in rows if r["latest_cut_off"]]
        summary: dict[str, Any] = {}
        if with_score:
            hi = max(with_score, key=lambda r: r["latest_cut_off"]["score"])
            lo = min(with_score, key=lambda r: r["latest_cut_off"]["score"])
            summary = {
                "highest_cut_off": {"id": hi["id"], "score": hi["latest_cut_off"]["score"]},
                "lowest_cut_off": {"id": lo["id"], "score": lo["latest_cut_off"]["score"]},
                "spread": round(hi["latest_cut_off"]["score"] - lo["latest_cut_off"]["score"], 3),
            }
        summary["without_cutoff"] = [r["id"] for r in rows if r["admission_without_cutoff"]]
        return self._wrap({"degrees": rows, "summary": summary, "caveat": CUTOFF_CAVEAT})

    @staticmethod
    def _band(margin: float) -> str:
        if margin >= 0.5:
            return "safe"
        if margin >= 0:
            return "match"
        if margin >= -1.0:
            return "reach"
        return "long_shot"

    def admission_check(
        self,
        grade: float,
        degree_ids: list[str] | None = None,
        query: str | None = None,
        limit: int = 10,
    ) -> dict[str, Any]:
        if isinstance(grade, bool) or not isinstance(grade, int | float) or not 0 <= grade <= MAX_CUTOFF:
            raise ToolInputError("grade must be a number between 0 and 14 (Spanish admission grade over 14).")
        has_ids = bool(degree_ids)
        has_query = bool(query and query.strip())
        if has_ids == has_query:
            raise ToolInputError("Provide exactly one of degree_ids (list of ids) or query (free text).")
        if has_ids:
            assert degree_ids is not None
            if len(degree_ids) > MAX_ADMISSION_DEGREES:
                raise ToolInputError(f"degree_ids accepts at most {MAX_ADMISSION_DEGREES} ids.")
            degrees = [self._degree(d) for d in dict.fromkeys(degree_ids)]
        else:
            found = self.search_degrees(query or "", limit=limit)["results"]
            degrees = [self.ds.degrees[r["id"]] for r in found]

        results = []
        counts = {"above": 0, "below": 0, "no_cutoff": 0, "no_data": 0}
        for d in degrees:
            row = self.degree_summary(d)
            latest = d.latest_cut_off
            if d.admission_without_cutoff:
                row.update({"status": "no_cutoff", "meets_cut_off": True, "margin": None, "year_used": None,
                            "band": "safe", "explanation": "Admission without cut-off: all eligible applicants "
                            "were admitted in the reference year. Check access requirements."})
            elif latest is None:
                row.update({"status": "no_data", "meets_cut_off": None, "margin": None, "year_used": None,
                            "band": None, "explanation": "No cut-off in this dataset for this degree."})
            else:
                margin = round(grade - latest.score, 3)
                status = "above" if margin >= 0 else "below"
                row.update({
                    "status": status,
                    "meets_cut_off": margin >= 0,
                    "cut_off": latest.score,
                    "margin": margin,
                    "year_used": latest.year,
                    "academic_year_used": academic_year(latest.year),
                    "band": self._band(margin),
                    "explanation": (
                        f"Your grade {grade:.3f} is {abs(margin):.3f} {'above' if margin >= 0 else 'below'} "
                        f"the {academic_year(latest.year)} cut-off of {latest.score:.3f}."
                    ),
                })
            counts[row["status"]] += 1
            results.append(row)
        return self._wrap({
            "grade": grade,
            "grade_scale": "0-14 (PAU/EBAU admission grade)",
            "results": results,
            "summary": counts,
            "caveat": CUTOFF_CAVEAT,
        })

    def _evaluate_scholarship(
        self,
        s: Scholarship,
        region: str | None,
        level: str | None,
        income: float | None,
        grade: float | None,
    ) -> tuple[str, list[str]]:
        """Return (status, reasons) where status is 'likely', 'check' or 'excluded'."""
        reasons: list[str] = []
        pending = False
        if s.scope == "regional":
            if region is None:
                pending = True
                reasons.append(f"Regional scheme for {', '.join(s.regions)}: confirm residence/study region.")
            elif not any(normalize(r) == normalize(region) for r in s.regions):
                return "excluded", [f"Only for {', '.join(s.regions)} (you said {region})."]
            else:
                reasons.append(f"Region matches ({region}).")
        else:
            reasons.append("National scheme: open in every region.")

        if level is None:
            pending = True
            reasons.append(f"Study level not given; covers: {', '.join(s.levels)}.")
        elif level not in s.levels:
            return "excluded", [f"Not for level '{level}' (covers: {', '.join(s.levels)})."]
        else:
            reasons.append(f"Covers level '{level}'.")

        if s.max_family_income is None:
            reasons.append("No family income ceiling.")
        elif income is None:
            pending = True
            reasons.append(f"Income ceiling of {s.max_family_income:,.0f} EUR/year: confirm your family income.")
        elif income > s.max_family_income:
            return "excluded", [
                f"Family income {income:,.0f} EUR exceeds the ceiling of {s.max_family_income:,.0f} EUR."
            ]
        else:
            reasons.append(f"Family income {income:,.0f} EUR is within the {s.max_family_income:,.0f} EUR ceiling.")

        if s.min_grade is None:
            reasons.append("No minimum grade.")
        elif grade is None:
            pending = True
            reasons.append(f"Requires an average grade of at least {s.min_grade:.1f}/10: confirm your grade.")
        elif grade < s.min_grade:
            return "excluded", [f"Grade {grade:.2f} is below the minimum of {s.min_grade:.1f}/10."]
        else:
            reasons.append(f"Grade {grade:.2f} meets the minimum of {s.min_grade:.1f}/10.")
        return ("check" if pending else "likely"), reasons

    def find_scholarships(
        self,
        region: str | None = None,
        level: str | None = None,
        max_family_income: float | None = None,
        min_grade: float | None = None,
        limit: int = 10,
    ) -> dict[str, Any]:
        _check_limit(limit, MAX_SCHOLARSHIP_LIMIT)
        region_key = self._resolve_region(region)
        level_key = None
        if level is not None and level.strip():
            level_key = normalize(level).replace(" ", "_")
            if level_key not in LEVELS:
                raise ToolInputError(f"Unknown level '{level}'. Valid levels: {', '.join(LEVELS)}.")
        if max_family_income is not None and max_family_income < 0:
            raise ToolInputError("max_family_income must be a non-negative amount in EUR per year.")
        if min_grade is not None and not 0 <= min_grade <= 10:
            raise ToolInputError("min_grade is the applicant's average grade over 10 (0-10).")

        matched, excluded = [], []
        for s in self.ds.scholarships.values():
            status, reasons = self._evaluate_scholarship(s, region_key, level_key, max_family_income, min_grade)
            if status == "excluded":
                excluded.append({"id": s.id, "name": s.name, "reason": reasons[0]})
                continue
            matched.append({
                "id": s.id,
                "name": s.name,
                "provider": s.provider,
                "scope": s.scope,
                "regions": list(s.regions),
                "levels": list(s.levels),
                "eligibility": status,
                "eligibility_reasons": reasons,
                "income_ceiling_eur": s.max_family_income,
                "min_grade": s.min_grade,
                "amount_range_eur": [s.amount_min_eur, s.amount_max_eur],
                "description": s.description,
                "requirements": list(s.requirements),
                "source": s.source,
            })
        matched.sort(key=lambda m: (m["eligibility"] != "likely", -m["amount_range_eur"][1], m["id"]))
        return self._wrap({
            "profile": {"region": region_key, "level": level_key, "family_income_eur": max_family_income,
                        "average_grade": min_grade},
            "total_matches": len(matched),
            "results": matched[:limit],
            "excluded": excluded[:MAX_SCHOLARSHIP_LIMIT],
            "caveat": "Eligibility here is a first filter. Each call has more requirements (credits passed, "
                      "residence, deadlines); read the official call (convocatoria).",
        })

    def list_universities(self, region: str | None = None) -> dict[str, Any]:
        region_key = self._resolve_region(region)
        unis = [
            self._university_dict(u) for u in self.ds.universities.values()
            if region_key is None or normalize(u.region) == normalize(region_key)
        ]
        unis.sort(key=lambda u: (normalize(u["region"]), normalize(u["name"])))
        return self._wrap({"region": region_key, "count": len(unis), "universities": unis})

    # ---------------------------------------------------------------- resources

    def metadata_resource(self) -> dict[str, Any]:
        m = self.ds.metadata
        return self._wrap({
            "dataset_version": m.dataset_version,
            "sample": m.sample,
            "notice": m.notice,
            "latest_cut_off_year": m.latest_cut_off_year,
            "score_scale": m.score_scale,
            "description": m.description,
            "counts": self.ds.counts,
            "regions": self.ds.regions,
            "branches": BRANCH_LABELS,
            "levels": list(LEVELS),
        })

    def university_resource(self, university_id: str) -> dict[str, Any]:
        uni = self.ds.universities.get(university_id)
        if uni is None:
            raise ToolInputError(f"Unknown university id '{university_id}'.")
        degrees = [self.degree_summary(self.ds.degrees[d]) for d in sorted(self.ds.degrees_by_university[uni.id])]
        return self._wrap({"university": self._university_dict(uni), "degrees": degrees})
