"""MCP server wiring: exposes FrankyService as tools, resources and a prompt."""

from __future__ import annotations

import json
from collections.abc import Callable
from functools import wraps
from typing import Annotated, Any

from mcp.server.fastmcp import FastMCP
from mcp.server.fastmcp.exceptions import ToolError
from pydantic import Field

from .data import Dataset, load_dataset
from .service import MAX_SCHOLARSHIP_LIMIT, MAX_SEARCH_LIMIT, FrankyService, ToolInputError

INSTRUCTIONS = """\
Query Spanish university admissions data: universities, degree offerings ("grados"),
cut-off grades ("notas de corte", over 14) per academic year, and scholarships ("becas").
Typical flow: search_degrees -> get_degree / compare_degrees -> admission_check.
Every response carries a data_notice: the bundled dataset is an ILLUSTRATIVE SAMPLE, so
always tell the user to confirm figures in the university's official publication.
"""

def _tool_errors[F: Callable[..., Any]](fn: F) -> F:
    """Turn ToolInputError into an MCP tool error with a clean message."""

    @wraps(fn)
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        try:
            return fn(*args, **kwargs)
        except ToolInputError as exc:
            raise ToolError(str(exc)) from exc

    return wrapper  # type: ignore[return-value]


def build_server(dataset: Dataset | None = None, host: str = "127.0.0.1", port: int = 8000) -> FastMCP:
    """Create the MCP server. Loads (and validates) the dataset eagerly so bad data fails at startup."""
    svc = FrankyService(dataset if dataset is not None else load_dataset())
    mcp = FastMCP("franky", instructions=INSTRUCTIONS, host=host, port=port)

    @mcp.tool()
    @_tool_errors
    def search_degrees(
        query: Annotated[str, Field(description="Free text, e.g. 'informatica en Madrid' or 'medicina'. "
                                                "Accent- and case-insensitive. May be empty if filters are set.")],
        region: Annotated[str | None, Field(description="Autonomous community, e.g. 'Madrid', 'Cataluña', "
                                                        "'Andalucia'.")] = None,
        branch: Annotated[str | None, Field(description="Knowledge branch: ciencias, ciencias_salud, "
                                                        "ingenieria_arquitectura, artes_humanidades, "
                                                        "ciencias_sociales_juridicas.")] = None,
        university: Annotated[str | None, Field(description="University id, acronym (e.g. 'UCM') or part of "
                                                            "its name.")] = None,
        max_cutoff: Annotated[float | None, Field(ge=5, le=14, description="Only degrees whose latest cut-off "
                                                  "is at or below this grade (over 14).")] = None,
        limit: Annotated[int, Field(ge=1, le=MAX_SEARCH_LIMIT, description="Max results.")] = 10,
    ) -> dict[str, Any]:
        """Search degree offerings by free text and filters, ranked with BM25.

        Returns degree ids, university, region, branch and the latest cut-off grade
        (over 14). Use the ids with get_degree, compare_degrees or admission_check.
        """
        return svc.search_degrees(query, region, branch, university, max_cutoff, limit)

    @mcp.tool()
    @_tool_errors
    def get_degree(
        degree_id: Annotated[str, Field(description="Degree id from search_degrees, e.g. 'ucm-medicina'.")],
    ) -> dict[str, Any]:
        """Get one degree offering with its university and cut-off history by academic year."""
        return svc.get_degree(degree_id)

    @mcp.tool()
    @_tool_errors
    def compare_degrees(
        degree_ids: Annotated[list[str], Field(min_length=2, max_length=5,
                                               description="2 to 5 degree ids to compare side by side.")],
    ) -> dict[str, Any]:
        """Compare 2-5 degree offerings: cut-off history, latest cut-off, trend, duration and credits."""
        return svc.compare_degrees(degree_ids)

    @mcp.tool()
    @_tool_errors
    def admission_check(
        grade: Annotated[float, Field(ge=0, le=14, description="Student's admission grade over 14 "
                                                               "(PAU/EBAU: access phase + specific phase).")],
        degree_ids: Annotated[list[str] | None, Field(max_length=20, description="Degree ids to check. "
                                                      "Provide this OR query.")] = None,
        query: Annotated[str | None, Field(description="Free-text search to pick degrees to check. "
                                                       "Provide this OR degree_ids.")] = None,
        limit: Annotated[int, Field(ge=1, le=MAX_SEARCH_LIMIT, description="Max degrees when using query.")] = 10,
    ) -> dict[str, Any]:
        """Compare a grade with the latest cut-off of each degree.

        For each degree returns status (above / below / no_cutoff / no_data), the
        margin, the academic year used and a band (safe / match / reach / long_shot).
        Cut-offs change every year: the result is a reference, not a prediction.
        """
        return svc.admission_check(grade, degree_ids, query, limit)

    @mcp.tool()
    @_tool_errors
    def find_scholarships(
        region: Annotated[str | None, Field(description="Region of residence/study, e.g. 'Madrid'.")] = None,
        level: Annotated[str | None, Field(description="Study level: bachillerato, fp_grado_medio, "
                                                       "fp_grado_superior, grado, master.")] = None,
        max_family_income: Annotated[float | None, Field(ge=0, description="Applicant's annual family "
                                                         "income in EUR; schemes whose ceiling is lower are "
                                                         "excluded.")] = None,
        min_grade: Annotated[float | None, Field(ge=0, le=10, description="Applicant's average grade over 10; "
                                                 "schemes requiring more are excluded.")] = None,
        limit: Annotated[int, Field(ge=1, le=MAX_SCHOLARSHIP_LIMIT, description="Max results.")] = 10,
    ) -> dict[str, Any]:
        """Find scholarship schemes matching a student profile, with eligibility reasons.

        Missing profile fields do not exclude a scheme; they mark it as 'check'
        instead of 'likely'. Excluded schemes are listed with the reason.
        """
        return svc.find_scholarships(region, level, max_family_income, min_grade, limit)

    @mcp.tool()
    @_tool_errors
    def list_universities(
        region: Annotated[str | None, Field(description="Optional autonomous community filter.")] = None,
    ) -> dict[str, Any]:
        """List universities in the dataset (optionally by region) with their number of degree offerings."""
        return svc.list_universities(region)

    @mcp.resource("franky://dataset/metadata", mime_type="application/json")
    def dataset_metadata() -> str:
        """Dataset version, record counts, regions, branches and the sample-data notice."""
        return json.dumps(svc.metadata_resource(), ensure_ascii=False)

    @mcp.resource("franky://universities/{university_id}", mime_type="application/json")
    def university_resource(university_id: str) -> str:
        """A university and all its degree offerings."""
        return json.dumps(svc.university_resource(university_id), ensure_ascii=False)

    @mcp.prompt()
    def plan_applications(grade: str, interests: str, region: str = "") -> str:
        """Plan a reach / match / safe list of degree applications for a grade (over 14) and interests."""
        where = f" Prefer degrees in {region}." if region else ""
        return (
            f"I have an admission grade of {grade} out of 14 and I am interested in: {interests}.{where}\n\n"
            "Using the franky tools, build an application plan:\n"
            "1. Call search_degrees for each interest (use the region filter if given) to collect candidates.\n"
            f"2. Call admission_check with grade={grade} and the candidate degree_ids.\n"
            "3. Group the results into REACH (band 'reach' or 'long_shot'), MATCH (band 'match') and SAFE "
            "(band 'safe' or admission without cut-off). Aim for 2-3 per group.\n"
            "4. For borderline options, call get_degree to look at the cut-off trend across years.\n"
            "5. Optionally call find_scholarships for the region and level 'grado'.\n"
            "Present a short table per group with degree, university, latest cut-off, year and margin. "
            "End with the data_notice from the tool responses: the figures are illustrative and must be "
            "checked against each university's official publication."
        )

    return mcp
