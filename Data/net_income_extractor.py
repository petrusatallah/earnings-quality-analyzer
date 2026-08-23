"""Dedicated Net Income extraction from Task 72 annual SEC filing data."""

from dataclasses import dataclass
from typing import Any, Optional, Tuple, Union

from Data.company_identifier import CompanyIdentity, normalize_ticker_input
from Data.financial_statement_fetcher import (
    AnnualFinancialStatements,
    CandidateFinancialValue,
    FINANCIAL_FIELD_DEFINITIONS,
    FactStatus,
)
from Data.provenance import ProvenanceMixin


NET_INCOME_METRIC = "Net Income"
_NET_INCOME_DEFINITION = next(
    definition
    for definition in FINANCIAL_FIELD_DEFINITIONS
    if definition.name == NET_INCOME_METRIC
)
VALID_NET_INCOME_CONCEPTS = frozenset(
    (candidate.taxonomy, candidate.concept)
    for candidate in _NET_INCOME_DEFINITION.concepts
)


@dataclass(frozen=True)
class NetIncomeExtraction(ProvenanceMixin):
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


def extract_net_income(
    company: Union[CompanyIdentity, str],
    fiscal_year: int,
    annual_statements: AnnualFinancialStatements,
) -> NetIncomeExtraction:
    """Extract one annual Net Income fact without fetching or estimating."""

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
        and value.financial_field == NET_INCOME_METRIC
    )
    if not matches:
        return NetIncomeExtraction(
            metric_name=NET_INCOME_METRIC,
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
            status=FactStatus.MISSING,
            validation_reason=(
                "No annual Net Income record exists for the requested fiscal year."
            ),
        )
    if len(matches) > 1:
        return NetIncomeExtraction(
            metric_name=NET_INCOME_METRIC,
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
            status=FactStatus.NEEDS_VALIDATION,
            validation_reason=(
                "Multiple Net Income records exist for the same fiscal year; "
                "no value was selected."
            ),
        )

    fact = matches[0]
    concept_is_valid = (
        fact.xbrl_taxonomy,
        fact.xbrl_concept,
    ) in VALID_NET_INCOME_CONCEPTS
    raw_is_numeric = isinstance(fact.raw_value, (int, float)) and not isinstance(
        fact.raw_value, bool
    )
    can_normalize = fact.unit == "USD" and raw_is_numeric
    normalized_value = fact.raw_value / 1_000_000 if can_normalize else None

    status = fact.status
    reason = fact.validation_reason or fact.missing_reason
    if status is FactStatus.RETRIEVED and not concept_is_valid:
        status = FactStatus.NEEDS_VALIDATION
        reason = "The selected fact does not use an approved annual Net Income concept."
    elif status is FactStatus.RETRIEVED and not can_normalize:
        status = FactStatus.NEEDS_VALIDATION
        reason = (
            "Net Income was reported, but it cannot be normalized to USD millions "
            "without estimation or currency conversion."
        )

    return NetIncomeExtraction(
        metric_name=NET_INCOME_METRIC,
        company_name=annual_statements.company_name,
        ticker=annual_statements.ticker,
        raw_sec_value=fact.raw_value,
        raw_unit=fact.unit,
        normalized_usd_millions=normalized_value,
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
