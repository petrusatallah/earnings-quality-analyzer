"""Annual duration extractors for Task 77 D&A and Capital Expenditures."""

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


DA_METRIC = "Depreciation & Amortization"
CAPEX_METRIC = "Capital Expenditures"


def _approved_concepts(metric_name: str) -> frozenset[tuple[str, str]]:
    definition = next(
        item
        for item in FINANCIAL_FIELD_DEFINITIONS
        if item.name == metric_name
    )
    return frozenset(
        (candidate.taxonomy, candidate.concept)
        for candidate in definition.concepts
    )


VALID_DA_CONCEPTS = _approved_concepts(DA_METRIC)
VALID_CAPEX_CONCEPTS = _approved_concepts(CAPEX_METRIC)

BROAD_CAPEX_CONCEPTS = frozenset(
    {
        ("us-gaap", "PaymentsToAcquireBusinessesNetOfCashAcquired"),
        ("us-gaap", "PaymentsToAcquireInvestments"),
        ("us-gaap", "PaymentsForProceedsFromOtherInvestingActivities"),
    }
)


@dataclass(frozen=True)
class AnnualDurationMetricExtraction(ProvenanceMixin):
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
    metric_name: str,
    fiscal_year: int,
    status: FactStatus,
    reason: str,
) -> AnnualDurationMetricExtraction:
    return AnnualDurationMetricExtraction(
        metric_name=metric_name,
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


def _extract_duration_metric(
    company: Union[CompanyIdentity, str],
    fiscal_year: int,
    annual_statements: AnnualFinancialStatements,
    metric_name: str,
    valid_concepts: frozenset[tuple[str, str]],
) -> AnnualDurationMetricExtraction:
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
        and value.financial_field == metric_name
    )
    if not matches:
        return _empty_result(
            annual_statements,
            metric_name,
            fiscal_year,
            FactStatus.MISSING,
            f"No annual {metric_name} record exists for the requested fiscal year.",
        )
    if len(matches) > 1:
        return _empty_result(
            annual_statements,
            metric_name,
            fiscal_year,
            FactStatus.NEEDS_VALIDATION,
            f"Conflicting {metric_name} records exist for the same fiscal year.",
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
            "The selected fact is not a validated full-fiscal-year duration; "
            "quarterly and YTD values are rejected."
        )
    elif status is FactStatus.RETRIEVED and concept_key not in valid_concepts:
        status = FactStatus.NEEDS_VALIDATION
        if metric_name == CAPEX_METRIC and concept_key in BROAD_CAPEX_CONCEPTS:
            reason = (
                "The candidate represents broader investing or acquisition cash "
                "flows and cannot be treated as Capital Expenditures."
            )
        else:
            reason = f"The selected concept is not approved for {metric_name}."

    raw_is_numeric = isinstance(fact.raw_value, (int, float)) and not isinstance(
        fact.raw_value, bool
    )
    can_normalize = (
        status is FactStatus.RETRIEVED and fact.unit == "USD" and raw_is_numeric
    )
    if status is FactStatus.RETRIEVED and not can_normalize:
        status = FactStatus.NEEDS_VALIDATION
        reason = (
            f"{metric_name} cannot be normalized to USD millions without "
            "estimation or currency conversion."
        )

    return AnnualDurationMetricExtraction(
        metric_name=metric_name,
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


def extract_depreciation_and_amortization(
    company: Union[CompanyIdentity, str],
    fiscal_year: int,
    annual_statements: AnnualFinancialStatements,
) -> AnnualDurationMetricExtraction:
    return _extract_duration_metric(
        company, fiscal_year, annual_statements, DA_METRIC, VALID_DA_CONCEPTS
    )


def extract_capital_expenditures(
    company: Union[CompanyIdentity, str],
    fiscal_year: int,
    annual_statements: AnnualFinancialStatements,
) -> AnnualDurationMetricExtraction:
    return _extract_duration_metric(
        company, fiscal_year, annual_statements, CAPEX_METRIC, VALID_CAPEX_CONCEPTS
    )
