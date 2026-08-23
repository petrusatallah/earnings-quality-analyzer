"""Investor-focused interpretation of Task 90 working-capital results.

This module describes existing flags, classifications, and severities.  It
does not calculate working-capital values or create new warning thresholds.
"""

from typing import Any, Mapping, Sequence

from Analysis.conclusion_safety import apply_conclusion_safety


_REQUIRED_TASK_90_SECTIONS = {"company", "working_capital"}


def _records(value: Any) -> Sequence[Mapping[str, Any]]:
    if not isinstance(value, list) or not all(
        isinstance(record, Mapping) for record in value
    ):
        raise TypeError(
            "Task 90 section 'working_capital' must be a list of records."
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


def interpret_working_capital(
    structured_input: Mapping[str, Any],
) -> dict[str, Any]:
    """Interpret supplied Task 90 working-capital records without recalculation."""

    if not isinstance(structured_input, Mapping):
        raise TypeError("structured_input must be the dictionary from Task 90.")
    missing_sections = _REQUIRED_TASK_90_SECTIONS.difference(structured_input)
    if missing_sections:
        missing = ", ".join(sorted(missing_sections))
        raise ValueError(f"Task 90 structured input is missing: {missing}.")

    records = _records(structured_input["working_capital"])
    fiscal_years = []
    positives = []
    concerns = []
    yearly_assessments = []

    for record in records:
        fiscal_year = record.get("Fiscal Year")
        if fiscal_year is not None and fiscal_year not in fiscal_years:
            fiscal_years.append(fiscal_year)

        evidence = {
            "revenue_growth": _first_present(record, "Revenue Growth"),
            "inventory_growth": _first_present(record, "Inventory Growth"),
            "ap_growth": _first_present(record, "AP Growth"),
            "ocf_growth": _first_present(record, "OCF Growth"),
            "ar_change": _first_present(record, "AR Change"),
            "inventory_change": _first_present(record, "Inventory Change"),
            "ap_change": _first_present(record, "AP Change"),
            "net_working_capital_cash_effect": _first_present(
                record,
                "Net Working Capital Cash Effect",
                "Net Working-Capital Cash Effect",
            ),
            "inventory_flag": _first_present(record, "Inventory Flag"),
            "ap_classification": _first_present(record, "AP Classification"),
            "working_capital_cash_use": _first_present(
                record, "Working Capital Cash Use"
            ),
        }
        severity = _first_present(
            record, "Overall Severity", "Working Capital Severity"
        )
        source_explanation = _first_present(record, "Explanation")
        unavailable = [
            field for field, value in evidence.items() if value is None
        ]
        if severity is None:
            unavailable.append("overall_severity")
        if source_explanation is None:
            unavailable.append("explanation")

        year_positives = []
        year_concerns = []

        if evidence["inventory_flag"] is True:
            year_concerns.append(
                "The existing inventory rule triggered, so inventory build-up "
                "warrants investor review."
            )
        elif evidence["inventory_flag"] is False:
            year_positives.append(
                "The existing inventory-growth rule did not trigger."
            )

        ap_classification = evidence["ap_classification"]
        if ap_classification == "Possible payment pressure":
            year_concerns.append(
                "The supplied AP classification identifies possible payment pressure."
            )
        elif ap_classification == "Normal supplier financing pattern":
            year_concerns.append(
                "The supplied AP classification identifies a supplier-financing "
                "pattern that requires review."
            )
        elif ap_classification == "No AP concern triggered":
            year_positives.append(
                "The existing accounts-payable rules did not identify a concern."
            )

        if evidence["working_capital_cash_use"] is True:
            year_concerns.append(
                "The selected-account working-capital proxy suggests a cash use."
            )
        elif (
            evidence["working_capital_cash_use"] is False
            and evidence["net_working_capital_cash_effect"] is not None
            and evidence["net_working_capital_cash_effect"] > 0
        ):
            year_positives.append(
                "The selected-account working-capital proxy suggests a cash benefit."
            )
        elif evidence["working_capital_cash_use"] is False:
            year_positives.append(
                "The selected-account working-capital proxy suggests no cash use or "
                "benefit."
            )

        if year_concerns:
            assessment = "Existing results identify working-capital items for review."
        elif year_positives:
            assessment = (
                "Existing results do not identify a working-capital concern under "
                "the supplied rules."
            )
        else:
            assessment = (
                "Working-capital assessment is unavailable because classification "
                "and flag evidence is missing."
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
            "working-capital signals."
        )
    elif concerns:
        overall_assessment = (
            "Supplied fiscal-year results identify working-capital items for review."
        )
    elif positives:
        overall_assessment = (
            "Supplied fiscal-year results do not trigger the existing "
            "working-capital warnings."
        )
    else:
        overall_assessment = (
            "Working-capital assessment is unavailable because the Task 90 input "
            "contains no usable classification or flag evidence."
        )

    explanation = (
        "This interpretation follows the supplied inventory flag, AP classification, "
        "selected-account working-capital proxy result, and existing severity. The "
        "proxy uses only accounts receivable, inventory, and accounts payable; other "
        "working-capital accounts, acquisitions, foreign exchange, and non-cash "
        "effects may cause it to differ from the cash-flow statement. Numeric growth, "
        "movement, and legacy cash-effect fields are retained only as supporting "
        "evidence."
    )
    if not yearly_assessments or any(
        item["unavailable_evidence"] for item in yearly_assessments
    ):
        explanation += " Missing evidence is marked unavailable and was not estimated."

    return apply_conclusion_safety({
        "area": "Working Capital",
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
