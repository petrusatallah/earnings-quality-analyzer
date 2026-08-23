"""Investor-focused interpretation of Task 90 normalized-earnings results.

This module describes supplied normalization flags, classifications, review
status, and severity.  It does not calculate adjustments, differences, or new
normalization rules.
"""

from typing import Any, Mapping, Sequence

from Analysis.conclusion_safety import apply_conclusion_safety


_REQUIRED_TASK_90_SECTIONS = {"company", "normalized_earnings"}
_REVIEW_REQUIRED_STATUSES = {
    "Review",
    "Review required",
    "Needs investigation",
}
_NO_REVIEW_STATUSES = {
    "No review required",
    "No investigation triggered",
}


def _records(value: Any) -> Sequence[Mapping[str, Any]]:
    if not isinstance(value, list) or not all(
        isinstance(record, Mapping) for record in value
    ):
        raise TypeError(
            "Task 90 section 'normalized_earnings' must be a list of records."
        )
    return value


def _first_present(record: Mapping[str, Any], *fields: str) -> Any:
    for field in fields:
        if field in record:
            return record[field]
    return None


def _with_year(fiscal_year: Any, text: str) -> str:
    label = "Fiscal year unavailable" if fiscal_year is None else f"FY{fiscal_year}"
    return f"{label}: {text}"


def interpret_normalized_earnings(
    structured_input: Mapping[str, Any],
) -> dict[str, Any]:
    """Interpret existing normalized-earnings results from Task 90 input."""

    if not isinstance(structured_input, Mapping):
        raise TypeError("structured_input must be the dictionary from Task 90.")
    missing_sections = _REQUIRED_TASK_90_SECTIONS.difference(structured_input)
    if missing_sections:
        missing = ", ".join(sorted(missing_sections))
        raise ValueError(f"Task 90 structured input is missing: {missing}.")

    records = _records(structured_input["normalized_earnings"])
    fiscal_years = []
    positives = []
    concerns = []
    yearly_assessments = []

    for record in records:
        fiscal_year = record.get("Fiscal Year")
        if fiscal_year is not None and fiscal_year not in fiscal_years:
            fiscal_years.append(fiscal_year)

        evidence = {
            "reported_net_income": _first_present(record, "Reported Net Income"),
            "normalization_adjustment": _first_present(
                record, "Normalization Adjustment"
            ),
            "normalized_net_income": _first_present(
                record, "Normalized Net Income"
            ),
            "normalization_difference": _first_present(
                record, "Normalization Difference", "Difference"
            ),
            "normalization_difference_percentage": _first_present(
                record,
                "Normalization Difference %",
                "Normalization Difference Percentage",
                "Percentage Difference",
            ),
            "one_off_category": _first_present(
                record, "One-Off Category", "One-Off Categories Identified"
            ),
            "one_off_description": _first_present(
                record, "One-Off Description"
            ),
            "classification": _first_present(record, "Classification"),
            "review_status": _first_present(record, "Review Status"),
            "large_normalization_difference_flag": _first_present(
                record, "Large Normalization Difference Flag"
            ),
            "repeated_one_off_flag": _first_present(
                record, "Repeated One-Off Flag"
            ),
            "normalization_signal": _first_present(
                record, "Normalization Signal"
            ),
        }
        severity = _first_present(
            record, "Overall Severity", "Normalization Severity", "Severity"
        )
        source_explanation = _first_present(record, "Explanation")
        unavailable = [
            field for field, value in evidence.items() if value is None
        ]
        if severity is None:
            unavailable.append("severity")
        if source_explanation is None:
            unavailable.append("explanation")

        year_positives = []
        year_concerns = []
        if evidence["large_normalization_difference_flag"] is True:
            year_concerns.append(
                "The existing large-normalization-difference flag triggered, so "
                "the supplied earnings adjustment warrants investor review."
            )
        elif evidence["large_normalization_difference_flag"] is False:
            year_positives.append(
                "The existing large-normalization-difference rule did not trigger."
            )

        if evidence["repeated_one_off_flag"] is True:
            year_concerns.append(
                "The existing repeated-one-off flag triggered, so the recurring "
                "nature of the identified category requires review."
            )
        elif evidence["repeated_one_off_flag"] is False:
            year_positives.append(
                "The existing repeated-one-off rule did not trigger."
            )

        review_status = evidence["review_status"]
        if review_status in _REVIEW_REQUIRED_STATUSES:
            year_concerns.append(
                f"The supplied one-off review status is {review_status!r}."
            )
        elif review_status in _NO_REVIEW_STATUSES:
            year_positives.append(
                f"The supplied one-off review status is {review_status!r}."
            )

        if year_concerns:
            assessment = (
                "Existing results identify normalized-earnings items for review."
            )
        elif year_positives:
            assessment = (
                "Existing results do not identify a normalization concern under "
                "the supplied rules."
            )
        else:
            assessment = (
                "Normalized-earnings assessment is unavailable because the existing "
                "flags and review status are missing."
            )

        positives.extend(_with_year(fiscal_year, item) for item in year_positives)
        concerns.extend(_with_year(fiscal_year, item) for item in year_concerns)
        yearly_assessments.append(
            {
                "fiscal_year": fiscal_year,
                "existing_severity": severity,
                "assessment": assessment,
                "positive_signals": year_positives,
                "concerns": year_concerns,
                "supporting_evidence": evidence,
                "one_off_classification": evidence["classification"],
                "review_status": review_status,
                "source_explanation": source_explanation,
                "unavailable_evidence": unavailable,
            }
        )

    if concerns and positives:
        overall_assessment = (
            "Supplied fiscal-year results contain both positive and concerning "
            "normalized-earnings signals."
        )
    elif concerns:
        overall_assessment = (
            "Supplied fiscal-year results identify normalized-earnings items for review."
        )
    elif positives:
        overall_assessment = (
            "Supplied fiscal-year results do not trigger the existing normalization warnings."
        )
    else:
        overall_assessment = (
            "Normalized-earnings assessment is unavailable because the Task 90 "
            "input contains no usable normalization flags or review status."
        )

    explanation = (
        "This interpretation follows the supplied normalization flags, one-off "
        "classification, review status, existing severity, and source explanation. "
        "Reported earnings, adjustments, and differences are supporting evidence only."
    )
    if not yearly_assessments or any(
        item["unavailable_evidence"] for item in yearly_assessments
    ):
        explanation += " Missing evidence is marked unavailable and was not estimated."

    return apply_conclusion_safety({
        "area": "Normalized Earnings",
        "overall_assessment": overall_assessment,
        "fiscal_years_discussed": fiscal_years,
        "existing_severities": [
            {
                "fiscal_year": item["fiscal_year"],
                "severity": item["existing_severity"],
            }
            for item in yearly_assessments
        ],
        "positive_signals": positives,
        "concerns": concerns,
        "explanation": explanation,
        "yearly_assessments": yearly_assessments,
    })
