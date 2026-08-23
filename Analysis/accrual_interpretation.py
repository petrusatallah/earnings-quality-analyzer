"""Investor-focused interpretation of Task 90 accrual-quality inputs.

The logic in this module describes supplied results.  It does not calculate
financial metrics, recreate red-flag rules, or assign severity.
"""

from typing import Any, Mapping, Sequence

from Analysis.conclusion_safety import apply_conclusion_safety


_REQUIRED_TASK_90_SECTIONS = {
    "company",
    "financial_summary",
    "cash_conversion",
    "working_capital",
}


def _records(value: Any, section: str) -> Sequence[Mapping[str, Any]]:
    if not isinstance(value, list) or not all(
        isinstance(record, Mapping) for record in value
    ):
        raise TypeError(f"Task 90 section {section!r} must be a list of records.")
    return value


def _by_fiscal_year(
    records: Sequence[Mapping[str, Any]], section: str
) -> dict[Any, Mapping[str, Any]]:
    indexed: dict[Any, Mapping[str, Any]] = {}
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


def _signal_text(fiscal_year: Any, text: str) -> str:
    year = "Fiscal year unavailable" if fiscal_year is None else f"FY{fiscal_year}"
    return f"{year}: {text}"


def interpret_accrual_quality(
    structured_input: Mapping[str, Any],
) -> dict[str, Any]:
    """Interpret existing accrual outputs from a Task 90 dictionary.

    Flags and severities are copied exactly.  The supplied numeric fields are
    exposed as supporting evidence only and are never combined or compared.
    """

    if not isinstance(structured_input, Mapping):
        raise TypeError("structured_input must be the dictionary from Task 90.")
    missing_sections = _REQUIRED_TASK_90_SECTIONS.difference(structured_input)
    if missing_sections:
        missing = ", ".join(sorted(missing_sections))
        raise ValueError(f"Task 90 structured input is missing: {missing}.")

    cash_records = _records(
        structured_input["cash_conversion"], "cash_conversion"
    )
    financial_by_year = _by_fiscal_year(
        _records(structured_input["financial_summary"], "financial_summary"),
        "financial_summary",
    )
    working_capital_by_year = _by_fiscal_year(
        _records(structured_input["working_capital"], "working_capital"),
        "working_capital",
    )

    yearly_assessments = []
    positives = []
    concerns = []
    fiscal_years = []

    for cash_record in cash_records:
        fiscal_year = cash_record.get("Fiscal Year")
        if fiscal_year is not None and fiscal_year not in fiscal_years:
            fiscal_years.append(fiscal_year)
        financial_record = financial_by_year.get(fiscal_year, {})
        working_capital_record = working_capital_by_year.get(fiscal_year, {})

        severity = _first_present(
            cash_record, "Accrual Severity", "Severity"
        )
        if severity is None:
            severity = _first_present(financial_record, "Accrual Severity")

        evidence = {
            "net_income": _first_present(financial_record, "Net Income"),
            "operating_cash_flow": _first_present(
                financial_record, "Operating Cash Flow", "OCF"
            ),
            "revenue_growth": _first_present(cash_record, "Revenue Growth"),
            "ar_growth": _first_present(cash_record, "AR Growth"),
            "ar_revenue_gap": _first_present(
                cash_record, "AR Revenue Gap", "AR / Revenue Gap"
            ),
            "net_working_capital_cash_effect": _first_present(
                working_capital_record,
                "Net Working Capital Cash Effect",
                "Net Working-Capital Cash Effect",
            ),
            "ar_flag": _first_present(cash_record, "AR Flag"),
            "ni_ocf_flag": _first_present(cash_record, "NI OCF Flag"),
            "combined_accrual_flag": _first_present(
                cash_record, "Combined Accrual Flag"
            ),
        }
        unavailable = [
            field for field, value in evidence.items() if value is None
        ]

        year_positives = []
        year_concerns = []
        if evidence["ar_flag"] is False:
            year_positives.append(
                "The existing AR-versus-revenue rule did not trigger."
            )
        elif evidence["ar_flag"] is True:
            year_concerns.append(
                "The existing AR-versus-revenue rule triggered, indicating that "
                "receivables growth warrants investor review."
            )

        if evidence["ni_ocf_flag"] is False:
            year_positives.append(
                "The existing net-income-versus-operating-cash-flow rule did not trigger."
            )
        elif evidence["ni_ocf_flag"] is True:
            year_concerns.append(
                "The existing net-income-versus-operating-cash-flow rule triggered, "
                "indicating weaker earnings-to-cash alignment."
            )

        if evidence["combined_accrual_flag"] is True:
            year_concerns.append(
                "The supplied analysis identifies a combined accrual warning."
            )
        elif evidence["combined_accrual_flag"] is False:
            year_positives.append(
                "The supplied analysis does not identify a combined accrual warning."
            )

        if year_concerns:
            assessment = "Existing results identify an accrual-quality concern."
        elif year_positives:
            assessment = (
                "Existing results do not identify an accrual-quality concern under "
                "the supplied tests."
            )
        else:
            assessment = "Accrual assessment is unavailable because flag evidence is missing."

        positives.extend(
            _signal_text(fiscal_year, signal) for signal in year_positives
        )
        concerns.extend(
            _signal_text(fiscal_year, signal) for signal in year_concerns
        )
        yearly_assessments.append(
            {
                "fiscal_year": fiscal_year,
                "existing_severity": severity,
                "assessment": assessment,
                "positives": year_positives,
                "concerns": year_concerns,
                "evidence": evidence,
                "unavailable_evidence": unavailable,
            }
        )

    if concerns and positives:
        overall_assessment = (
            "Supplied fiscal-year results contain both positive and concerning "
            "accrual-quality signals."
        )
    elif concerns:
        overall_assessment = (
            "Supplied fiscal-year results identify accrual-quality concerns."
        )
    elif positives:
        overall_assessment = (
            "Supplied fiscal-year results do not trigger the existing accrual warnings."
        )
    else:
        overall_assessment = (
            "Accrual quality is unavailable because the Task 90 input contains no "
            "usable accrual flag evidence."
        )

    unavailable_years = [
        item["fiscal_year"]
        for item in yearly_assessments
        if item["unavailable_evidence"]
    ]
    explanation = (
        "This interpretation follows the supplied AR, earnings-to-cash, and "
        "combined-accrual flags and preserves their existing severities."
    )
    if unavailable_years or not yearly_assessments:
        explanation += " Missing evidence is reported as unavailable and was not estimated."

    return apply_conclusion_safety({
        "area": "Accrual Quality",
        "overall_assessment": overall_assessment,
        "fiscal_years_discussed": fiscal_years,
        "existing_severities": [
            {
                "fiscal_year": item["fiscal_year"],
                "severity": item["existing_severity"],
            }
            for item in yearly_assessments
        ],
        "key_positive_signals": positives,
        "key_concerns": concerns,
        "explanation": explanation,
        "yearly_assessments": yearly_assessments,
    })
