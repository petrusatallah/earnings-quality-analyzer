"""Dedicated annual Stock-Based Compensation extractor for Task 78."""

from dataclasses import dataclass
from datetime import date
from typing import Any, Optional, Tuple, Union

from Data.company_identifier import CompanyIdentity, normalize_ticker_input
from Data.financial_statement_fetcher import (
    AnnualFinancialStatements,
    CandidateFinancialValue,
    FINANCIAL_FIELD_DEFINITIONS,
    FULL_YEAR_MAX_DAYS,
    FULL_YEAR_MIN_DAYS,
    FactStatus,
)
from Data.provenance import ProvenanceMixin


SBC_METRIC = "Stock-Based Compensation"
_SBC_DEFINITION = next(
    definition
    for definition in FINANCIAL_FIELD_DEFINITIONS
    if definition.name == SBC_METRIC
)
VALID_SBC_CONCEPTS = frozenset(
    (candidate.taxonomy, candidate.concept)
    for candidate in _SBC_DEFINITION.concepts
)

BROAD_COMPENSATION_CONCEPTS = frozenset(
    {
        ("us-gaap", "LaborAndRelatedExpense"),
        ("us-gaap", "EmployeeBenefitsAndShareBasedCompensation"),
        ("us-gaap", "SalariesAndWages"),
        ("us-gaap", "PaymentsRelatedToTaxWithholdingForShareBasedCompensation"),
        ("us-gaap", "ProceedsFromStockOptionsExercised"),
    }
)


@dataclass(frozen=True)
class StockBasedCompensationExtraction(ProvenanceMixin):
    metric_name: str
    company_name: str
    ticker: str
    raw_sec_value: Any
    raw_unit: Optional[str]
    normalized_usd_millions: Optional[float]
    fiscal_year: int
    period_start: Optional[str]
    period_end: Optional[str]
    filing_form: Optional[str]
    filing_date: Optional[str]
    accession_number: Optional[str]
    xbrl_taxonomy: Optional[str]
    xbrl_concept: Optional[str]
    source_url: Optional[str]
    status: FactStatus
    validation_reason: Optional[str] = None
    candidate_values: Tuple[CandidateFinancialValue, ...] = ()


def _input_ticker(company: Union[CompanyIdentity, str]) -> str:
    if isinstance(company, CompanyIdentity):
        ticker = normalize_ticker_input(company.ticker)
    elif isinstance(company, str):
        ticker = normalize_ticker_input(company)
    else:
        raise TypeError("company must be a CompanyIdentity or ticker string")
    if not ticker:
        raise ValueError("A standardized company identity or valid ticker is required.")
    return ticker


def _empty_result(
    annual_statements: AnnualFinancialStatements,
    fiscal_year: int,
    status: FactStatus,
    reason: str,
) -> StockBasedCompensationExtraction:
    return StockBasedCompensationExtraction(
        metric_name=SBC_METRIC,
        company_name=annual_statements.company_name,
        ticker=annual_statements.ticker,
        raw_sec_value=None,
        raw_unit=None,
        normalized_usd_millions=None,
        fiscal_year=fiscal_year,
        period_start=None,
        period_end=None,
        filing_form=None,
        filing_date=None,
        accession_number=None,
        xbrl_taxonomy=None,
        xbrl_concept=None,
        source_url=annual_statements.company_facts_url,
        status=status,
        validation_reason=reason,
    )


def extract_stock_based_compensation(
    company: Union[CompanyIdentity, str],
    fiscal_year: int,
    annual_statements: AnnualFinancialStatements,
) -> StockBasedCompensationExtraction:
    """Extract annual SBC without fetching, combining, or estimating values."""

    ticker = _input_ticker(company)
    if ticker != normalize_ticker_input(annual_statements.ticker):
        raise ValueError(
            f"Company input {ticker!r} does not match Task 72 data for "
            f"{annual_statements.ticker!r}."
        )
    if not isinstance(fiscal_year, int):
        raise TypeError("fiscal_year must be an integer")

    matches = tuple(
        value
        for value in annual_statements.values
        if value.fiscal_year == fiscal_year
        and value.financial_field == SBC_METRIC
    )
    if not matches:
        return _empty_result(
            annual_statements,
            fiscal_year,
            FactStatus.MISSING,
            "No annual Stock-Based Compensation record exists for the requested fiscal year.",
        )
    if len(matches) > 1:
        return _empty_result(
            annual_statements,
            fiscal_year,
            FactStatus.NEEDS_VALIDATION,
            "Conflicting Stock-Based Compensation records exist for the fiscal year.",
        )

    fact = matches[0]
    status = fact.status
    reason = fact.validation_reason or fact.missing_reason
    concept_key = (fact.xbrl_taxonomy, fact.xbrl_concept)

    period_days = None
    if fact.period_start and fact.period_end:
        try:
            period_days = (
                date.fromisoformat(fact.period_end)
                - date.fromisoformat(fact.period_start)
            ).days
        except ValueError:
            pass

    if status is FactStatus.RETRIEVED and (
        period_days is None
        or not FULL_YEAR_MIN_DAYS <= period_days <= FULL_YEAR_MAX_DAYS
    ):
        status = FactStatus.NEEDS_VALIDATION
        reason = (
            "The selected SBC fact is not a validated full-fiscal-year duration; "
            "quarterly and YTD values are rejected."
        )
    elif status is FactStatus.RETRIEVED and concept_key not in VALID_SBC_CONCEPTS:
        status = FactStatus.NEEDS_VALIDATION
        if concept_key in BROAD_COMPENSATION_CONCEPTS:
            reason = (
                "The candidate is broader compensation, payroll, equity issuance, "
                "withholding, or option-proceeds data and cannot replace SBC expense."
            )
        else:
            reason = "The selected concept is not approved for Stock-Based Compensation."

    raw_is_numeric = isinstance(fact.raw_value, (int, float)) and not isinstance(
        fact.raw_value, bool
    )
    can_normalize = (
        status is FactStatus.RETRIEVED and fact.unit == "USD" and raw_is_numeric
    )
    if status is FactStatus.RETRIEVED and not can_normalize:
        status = FactStatus.NEEDS_VALIDATION
        reason = (
            "Stock-Based Compensation cannot be normalized to USD millions without "
            "estimation or currency conversion."
        )

    return StockBasedCompensationExtraction(
        metric_name=SBC_METRIC,
        company_name=annual_statements.company_name,
        ticker=annual_statements.ticker,
        raw_sec_value=fact.raw_value,
        raw_unit=fact.unit,
        normalized_usd_millions=(fact.raw_value / 1_000_000 if can_normalize else None),
        fiscal_year=fiscal_year,
        period_start=fact.period_start,
        period_end=fact.period_end,
        filing_form=fact.filing_form,
        filing_date=fact.filing_date,
        accession_number=fact.accession_number,
        xbrl_taxonomy=fact.xbrl_taxonomy,
        xbrl_concept=fact.xbrl_concept,
        source_url=fact.source_url,
        status=status,
        validation_reason=reason,
        candidate_values=fact.candidate_values,
    )
