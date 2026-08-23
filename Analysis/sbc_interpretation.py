"""Investor-focused interpretation of Task 90 stock-compensation results.

This module describes supplied SBC flags, buyback classifications, and
severity.  It does not calculate dilution, offset ratios, or warning rules.
"""

from typing import Any, Mapping, Sequence

from Analysis.conclusion_safety import apply_conclusion_safety


_REQUIRED_TASK_90_SECTIONS = {"company", "sbc"}


def _records(value: Any) -> Sequence[Mapping[str, Any]]:
    if not isinstance(value, list) or not all(
        isinstance(record, Mapping) for record in value
    ):
        raise TypeError("Task 90 section 'sbc' must be a list of records.")
    return value


def _first_present(record: Mapping[str, Any], *fields: str) -> Any:
    for field in fields:
        if field in record:
            return record[field]
    return None


def _with_year(fiscal_year: Any, text: str) -> str:
    label = "Fiscal year unavailable" if fiscal_year is None else f"FY{fiscal_year}"
    return f"{label}: {text}"


def interpret_sbc(structured_input: Mapping[str, Any]) -> dict[str, Any]:
    """Interpret existing SBC results from a Task 90 structured dictionary."""

    if not isinstance(structured_input, Mapping):
        raise TypeError("structured_input must be the dictionary from Task 90.")
    missing_sections = _REQUIRED_TASK_90_SECTIONS.difference(structured_input)
    if missing_sections:
        missing = ", ".join(sorted(missing_sections))
        raise ValueError(f"Task 90 structured input is missing: {missing}.")

    records = _records(structured_input["sbc"])
    fiscal_years = []
    positives = []
    concerns = []
    yearly_assessments = []

    for record in records:
        fiscal_year = record.get("Fiscal Year")
        if fiscal_year is not None and fiscal_year not in fiscal_years:
            fiscal_years.append(fiscal_year)

        evidence = {
            "sbc": _first_present(record, "SBC", "Stock-Based Compensation"),
            "sbc_to_net_income": _first_present(record, "SBC / Net Income"),
            "shares_outstanding": _first_present(record, "Shares Outstanding"),
            "shares_outstanding_growth": _first_present(
                record, "Shares Outstanding Growth"
            ),
            "large_sbc_flag": _first_present(record, "Large SBC Flag"),
            "dilution_flag": _first_present(record, "Dilution Flag"),
            "shares_repurchased": _first_present(record, "Shares Repurchased"),
            "shares_issued": _first_present(
                record, "Shares Issued", "Shares Issued Net"
            ),
            "net_share_effect": _first_present(record, "Net Share Effect"),
            "buyback_offset_ratio": _first_present(
                record, "Buyback Offset Ratio"
            ),
            "buyback_offset_classification": _first_present(
                record, "Buyback Offset Classification"
            ),
            "buyback_offset_flag": _first_present(record, "Buyback Offset Flag"),
        }
        severity = _first_present(
            record, "Overall SBC Severity", "SBC Severity"
        )
        source_explanation = _first_present(record, "Explanation")
        unavailable = [
            field for field, value in evidence.items() if value is None
        ]
        if severity is None:
            unavailable.append("overall_sbc_severity")
        if source_explanation is None:
            unavailable.append("explanation")

        year_positives = []
        year_concerns = []

        if evidence["large_sbc_flag"] is True:
            year_concerns.append(
                "The existing large-SBC flag triggered, so the economic significance "
                "of stock compensation warrants investor review."
            )
        elif evidence["large_sbc_flag"] is False:
            year_positives.append("The existing large-SBC rule did not trigger.")

        if evidence["dilution_flag"] is True:
            year_concerns.append(
                "The existing dilution flag triggered, indicating that the supplied "
                "share-count result requires review."
            )
        elif evidence["dilution_flag"] is False:
            year_positives.append("The existing dilution rule did not trigger.")

        offset_classification = evidence["buyback_offset_classification"]
        if offset_classification == "Buybacks more than offset share issuance":
            year_positives.append(
                "The supplied classification says buybacks more than offset share issuance."
            )
            year_concerns.append(
                "The supplied analysis identifies the buyback and issuance interaction "
                "for review; repurchases still use company cash."
            )
        elif offset_classification == "Buybacks partially offset share issuance":
            year_concerns.append(
                "The supplied classification says buybacks only partially offset "
                "share issuance."
            )
        elif offset_classification == "No positive net share issuance to offset":
            year_positives.append(
                "The supplied classification identifies no positive net share issuance "
                "for buybacks to offset."
            )

        if year_concerns:
            assessment = "Existing results identify SBC or dilution items for review."
        elif year_positives:
            assessment = (
                "Existing results do not identify an SBC or dilution concern under "
                "the supplied rules."
            )
        else:
            assessment = (
                "SBC assessment is unavailable because the existing flags and "
                "buyback-offset classification are missing."
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
            "SBC and dilution signals."
        )
    elif concerns:
        overall_assessment = (
            "Supplied fiscal-year results identify SBC or dilution items for review."
        )
    elif positives:
        overall_assessment = (
            "Supplied fiscal-year results do not trigger the existing SBC or dilution warnings."
        )
    else:
        overall_assessment = (
            "SBC assessment is unavailable because the Task 90 input contains no "
            "usable SBC flags or buyback-offset classification."
        )

    explanation = (
        "This interpretation follows the supplied SBC and dilution flags, buyback-offset "
        "classification, existing severity, and source explanation. Compensation, "
        "share-count, issuance, repurchase, and offset values are supporting evidence only."
    )
    if not yearly_assessments or any(
        item["unavailable_evidence"] for item in yearly_assessments
    ):
        explanation += " Missing evidence is marked unavailable and was not estimated."

    return apply_conclusion_safety({
        "area": "Stock-Based Compensation",
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
