"""Investor-focused interpretation of Task 90 CapEx results.

Only supplied CapEx evidence, classifications, flags, severities, and
explanations are described here.  No financial ratios or warning rules are
calculated in this module.
"""

from typing import Any, Mapping, Sequence

from Analysis.conclusion_safety import apply_conclusion_safety


_REQUIRED_TASK_90_SECTIONS = {"company", "financial_summary", "red_flags"}
_CAPEX_METRICS = {"CapEx", "CapEx vs D&A", "Capital Expenditures"}


def _records(value: Any, section: str) -> Sequence[Mapping[str, Any]]:
    if not isinstance(value, list) or not all(
        isinstance(record, Mapping) for record in value
    ):
        raise TypeError(f"Task 90 section {section!r} must be a list of records.")
    return value


def _by_fiscal_year(
    records: Sequence[Mapping[str, Any]], section: str
) -> dict[Any, Mapping[str, Any]]:
    indexed = {}
    for record in records:
        fiscal_year = record.get("Fiscal Year")
        if fiscal_year is None:
            continue
        if fiscal_year in indexed:
            raise ValueError(
                f"Task 90 section {section!r} contains duplicate fiscal years."
            )
        indexed[fiscal_year] = record
    return indexed


def _first_present(record: Mapping[str, Any], *fields: str) -> Any:
    for field in fields:
        if field in record:
            return record[field]
    return None


def _with_year(fiscal_year: Any, text: str) -> str:
    label = "Fiscal year unavailable" if fiscal_year is None else f"FY{fiscal_year}"
    return f"{label}: {text}"


def interpret_capex(structured_input: Mapping[str, Any]) -> dict[str, Any]:
    """Interpret existing CapEx results from a Task 90 structured dictionary."""

    if not isinstance(structured_input, Mapping):
        raise TypeError("structured_input must be the dictionary from Task 90.")
    missing_sections = _REQUIRED_TASK_90_SECTIONS.difference(structured_input)
    if missing_sections:
        missing = ", ".join(sorted(missing_sections))
        raise ValueError(f"Task 90 structured input is missing: {missing}.")

    financial_records = _records(
        structured_input["financial_summary"], "financial_summary"
    )
    red_flag_records = [
        record
        for record in _records(structured_input["red_flags"], "red_flags")
        if record.get("Metric") in _CAPEX_METRICS
    ]
    financial_by_year = _by_fiscal_year(financial_records, "financial_summary")
    red_flags_by_year = _by_fiscal_year(red_flag_records, "CapEx red_flags")

    fiscal_years = list(financial_by_year)
    fiscal_years.extend(
        year for year in red_flags_by_year if year not in financial_by_year
    )
    positives = []
    concerns = []
    yearly_assessments = []

    for fiscal_year in fiscal_years:
        financial = financial_by_year.get(fiscal_year, {})
        red_flag = red_flags_by_year.get(fiscal_year, {})

        capex_flag = _first_present(
            financial, "CapEx Review Flag", "CapEx Flag"
        )
        classification = _first_present(
            financial,
            "CapEx Investigation Result",
            "CapEx Result",
            "CapEx Classification",
        )
        consolidated_result = _first_present(red_flag, "Result")
        severity = _first_present(red_flag, "Severity")
        if severity is None:
            severity = _first_present(financial, "CapEx Severity", "Severity")
        source_explanation = _first_present(red_flag, "Explanation")
        if source_explanation is None:
            source_explanation = _first_present(
                financial, "CapEx Explanation", "Explanation"
            )

        evidence = {
            "capex": _first_present(
                financial, "CapEx", "Capital Expenditures"
            ),
            "capex_growth": _first_present(financial, "CapEx Growth"),
            "capex_to_revenue": _first_present(financial, "CapEx / Revenue"),
            "capex_to_da": _first_present(financial, "CapEx / D&A"),
            "revenue": _first_present(financial, "Revenue"),
            "da": _first_present(
                financial, "D&A", "Depreciation & Amortization"
            ),
            "capex_flag": capex_flag,
            "capex_classification": classification,
            "consolidated_result": consolidated_result,
        }
        unavailable = [
            field for field, value in evidence.items() if value is None
        ]
        if severity is None:
            unavailable.append("severity")
        if source_explanation is None:
            unavailable.append("explanation")

        # Follow existing results in order of specificity.  Numeric evidence is
        # intentionally not inspected to recreate the CapEx rule.
        if capex_flag is True:
            existing_concern = True
        elif capex_flag is False:
            existing_concern = False
        elif consolidated_result in {"Flag", "Review"}:
            existing_concern = True
        elif consolidated_result == "No Flag":
            existing_concern = False
        elif classification == "Needs investigation":
            existing_concern = True
        elif classification == "No investigation triggered":
            existing_concern = False
        else:
            existing_concern = None

        year_positives = []
        year_concerns = []
        if existing_concern is True:
            year_concerns.append(
                "The existing CapEx result requires investigation; investors may "
                "need to review the purpose and expected returns of the spending."
            )
            assessment = "The supplied results identify a CapEx item for review."
        elif existing_concern is False:
            year_positives.append(
                "The existing CapEx review rule did not identify a warning."
            )
            assessment = (
                "The supplied results do not identify a CapEx concern under the "
                "existing rule."
            )
        else:
            assessment = (
                "CapEx assessment is unavailable because the existing flag or "
                "classification is missing."
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
                "source_explanation": source_explanation,
                "unavailable_evidence": unavailable,
            }
        )

    if concerns and positives:
        overall_assessment = (
            "Supplied fiscal-year results contain both positive and concerning "
            "CapEx signals."
        )
    elif concerns:
        overall_assessment = "Supplied fiscal-year results identify CapEx items for review."
    elif positives:
        overall_assessment = (
            "Supplied fiscal-year results do not trigger the existing CapEx warning."
        )
    else:
        overall_assessment = (
            "CapEx assessment is unavailable because the Task 90 input contains "
            "no usable CapEx flag or classification."
        )

    explanation = (
        "This interpretation follows the supplied CapEx flag, classification, "
        "consolidated result, severity, and explanation. CapEx amounts, growth, "
        "and ratios are retained only as supporting evidence."
    )
    if not yearly_assessments or any(
        item["unavailable_evidence"] for item in yearly_assessments
    ):
        explanation += " Missing evidence is marked unavailable and was not estimated."

    return apply_conclusion_safety({
        "area": "CapEx",
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
