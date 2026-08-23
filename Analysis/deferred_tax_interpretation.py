"""Investor-focused interpretation of Task 90 deferred-tax results.

This module describes supplied tax flags and severity.  It does not calculate
tax ratios, growth, movements, thresholds, or new tax rules.
"""

from typing import Any, Mapping, Sequence

from Analysis.conclusion_safety import apply_conclusion_safety


_REQUIRED_TASK_90_SECTIONS = {"company", "financial_summary", "taxes"}


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


def _from_sources(
    primary: Mapping[str, Any],
    secondary: Mapping[str, Any],
    *fields: str,
) -> Any:
    value = _first_present(primary, *fields)
    return value if value is not None else _first_present(secondary, *fields)


def _with_year(fiscal_year: Any, text: str) -> str:
    label = "Fiscal year unavailable" if fiscal_year is None else f"FY{fiscal_year}"
    return f"{label}: {text}"


def interpret_deferred_taxes(
    structured_input: Mapping[str, Any],
) -> dict[str, Any]:
    """Interpret existing deferred-tax results from Task 90 structured input."""

    if not isinstance(structured_input, Mapping):
        raise TypeError("structured_input must be the dictionary from Task 90.")
    missing_sections = _REQUIRED_TASK_90_SECTIONS.difference(structured_input)
    if missing_sections:
        missing = ", ".join(sorted(missing_sections))
        raise ValueError(f"Task 90 structured input is missing: {missing}.")

    tax_records = _records(structured_input["taxes"], "taxes")
    financial_by_year = _by_fiscal_year(
        _records(structured_input["financial_summary"], "financial_summary"),
        "financial_summary",
    )

    fiscal_years = []
    positives = []
    concerns = []
    yearly_assessments = []

    for tax_record in tax_records:
        fiscal_year = tax_record.get("Fiscal Year")
        if fiscal_year is not None and fiscal_year not in fiscal_years:
            fiscal_years.append(fiscal_year)
        financial = financial_by_year.get(fiscal_year, {})

        evidence = {
            "tax_expense": _from_sources(
                tax_record, financial, "Tax Expense", "Income Tax Expense"
            ),
            "deferred_tax_assets": _from_sources(
                tax_record, financial, "Deferred Tax Assets", "DTA"
            ),
            "deferred_tax_liabilities": _from_sources(
                tax_record, financial, "Deferred Tax Liabilities", "DTL"
            ),
            "dta_to_net_income": _from_sources(
                tax_record, financial, "DTA / Net Income"
            ),
            "dta_growth": _from_sources(tax_record, financial, "DTA Growth"),
            "dtl_growth": _from_sources(tax_record, financial, "DTL Growth"),
            "deferred_tax_movement_flag": _first_present(
                tax_record, "Deferred Tax Movement Flag"
            ),
            "dta_risk_flag": _first_present(tax_record, "DTA Risk Flag"),
            "tax_signal": _first_present(tax_record, "Tax Signal"),
        }
        severity = _first_present(
            tax_record, "Overall Tax Severity", "Tax Severity"
        )
        source_explanation = _first_present(tax_record, "Explanation")
        unavailable = [
            field for field, value in evidence.items() if value is None
        ]
        if severity is None:
            unavailable.append("overall_tax_severity")
        if source_explanation is None:
            unavailable.append("explanation")

        year_positives = []
        year_concerns = []
        if evidence["dta_risk_flag"] is True:
            year_concerns.append(
                "The existing DTA risk flag triggered, so deferred-tax-asset "
                "recoverability warrants investor review."
            )
        elif evidence["dta_risk_flag"] is False:
            year_positives.append(
                "The existing deferred-tax-asset risk rule did not trigger."
            )

        if evidence["deferred_tax_movement_flag"] is True:
            year_concerns.append(
                "The existing deferred-tax movement flag triggered, indicating "
                "that the supplied DTA or DTL movement requires review."
            )
        elif evidence["deferred_tax_movement_flag"] is False:
            year_positives.append(
                "The existing deferred-tax movement rule did not trigger."
            )

        if year_concerns:
            assessment = "Existing results identify deferred-tax items for review."
        elif year_positives:
            assessment = (
                "Existing results do not identify a deferred-tax concern under "
                "the supplied rules."
            )
        else:
            assessment = (
                "Deferred-tax assessment is unavailable because the existing "
                "tax flags are missing."
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
            "deferred-tax signals."
        )
    elif concerns:
        overall_assessment = (
            "Supplied fiscal-year results identify deferred-tax items for review."
        )
    elif positives:
        overall_assessment = (
            "Supplied fiscal-year results do not trigger the existing deferred-tax warnings."
        )
    else:
        overall_assessment = (
            "Deferred-tax assessment is unavailable because the Task 90 input "
            "contains no usable deferred-tax flag evidence."
        )

    explanation = (
        "This interpretation follows the supplied DTA risk flag, deferred-tax "
        "movement flag, existing severity, and source explanation. Tax balances, "
        "ratios, and growth values are retained only as supporting evidence."
    )
    if not yearly_assessments or any(
        item["unavailable_evidence"] for item in yearly_assessments
    ):
        explanation += " Missing evidence is marked unavailable and was not estimated."

    return apply_conclusion_safety({
        "area": "Deferred Taxes",
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
