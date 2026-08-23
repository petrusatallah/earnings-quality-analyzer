"""Annual tax-expense and deferred-tax extractors for Task 80."""

from collections import Counter
from dataclasses import dataclass
from datetime import date
from enum import Enum
from typing import Any, Optional, Tuple, Union

from Data.company_identifier import CompanyIdentity, normalize_ticker_input
from Data.financial_statement_fetcher import (
    AnnualFinancialStatements,
    AnnualFinancialValue,
    CandidateFinancialValue,
    FINANCIAL_FIELD_DEFINITIONS,
    FULL_YEAR_MAX_DAYS,
    FULL_YEAR_MIN_DAYS,
    FactStatus,
)
from Data.provenance import ProvenanceMixin


INCOME_TAX_EXPENSE_METRIC = "Income Tax Expense"
DTA_METRIC = "Deferred Tax Assets"
DTL_METRIC = "Deferred Tax Liabilities"


class DeferredTaxPresentation(str, Enum):
    GROSS_DTA = "gross DTA"
    NET_DTA = "net DTA"
    GROSS_DTL = "gross DTL"
    NET_DTL = "net DTL"
    UNKNOWN = "unknown"


def _approved_concepts(metric_name: str) -> frozenset[tuple[str, str]]:
    definition = next(
        item for item in FINANCIAL_FIELD_DEFINITIONS if item.name == metric_name
    )
    return frozenset(
        (candidate.taxonomy, candidate.concept)
        for candidate in definition.concepts
    )


VALID_TAX_EXPENSE_CONCEPTS = _approved_concepts(INCOME_TAX_EXPENSE_METRIC)
VALID_DTA_CONCEPTS = _approved_concepts(DTA_METRIC)
VALID_DTL_CONCEPTS = _approved_concepts(DTL_METRIC)
_DURATION_METRICS = frozenset(
    item.name for item in FINANCIAL_FIELD_DEFINITIONS if item.duration
)

DEFERRED_TAX_PRESENTATIONS = {
    ("us-gaap", "DeferredTaxAssetsGross"): DeferredTaxPresentation.GROSS_DTA,
    ("us-gaap", "DeferredTaxAssetsNet"): DeferredTaxPresentation.NET_DTA,
    ("us-gaap", "DeferredTaxAssetsNetCurrent"): DeferredTaxPresentation.NET_DTA,
    ("us-gaap", "DeferredTaxAssetsNetNoncurrent"): DeferredTaxPresentation.NET_DTA,
    ("us-gaap", "DeferredIncomeTaxLiabilities"): DeferredTaxPresentation.GROSS_DTL,
    ("us-gaap", "DeferredTaxLiabilities"): DeferredTaxPresentation.NET_DTL,
    ("us-gaap", "DeferredTaxLiabilitiesCurrent"): DeferredTaxPresentation.NET_DTL,
    ("us-gaap", "DeferredTaxLiabilitiesNoncurrent"): DeferredTaxPresentation.NET_DTL,
}

_PARTIAL_DEFERRED_TAX_CONCEPTS = frozenset(
    {
        ("us-gaap", "DeferredTaxAssetsNetCurrent"),
        ("us-gaap", "DeferredTaxAssetsNetNoncurrent"),
        ("us-gaap", "DeferredTaxLiabilitiesCurrent"),
        ("us-gaap", "DeferredTaxLiabilitiesNoncurrent"),
    }
)


@dataclass(frozen=True)
class TaxMetricExtraction(ProvenanceMixin):
    metric_name: str
    company_name: str
    ticker: str
    raw_sec_value: Any
    raw_unit: Optional[str]
    normalized_usd_millions: Optional[float]
    fiscal_year: int
    period_start: Optional[str]
    period_end: Optional[str]
    balance_sheet_date: Optional[str]
    filing_form: Optional[str]
    filing_date: Optional[str]
    accession_number: Optional[str]
    xbrl_taxonomy: Optional[str]
    xbrl_concept: Optional[str]
    deferred_tax_presentation_type: Optional[DeferredTaxPresentation]
    source_url: Optional[str]
    status: FactStatus
    validation_reason: Optional[str] = None
    candidate_values: Tuple[CandidateFinancialValue, ...] = ()
    candidate_facts: Tuple[AnnualFinancialValue, ...] = ()


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


def _validate_input(
    company: Union[CompanyIdentity, str],
    fiscal_year: int,
    annual_statements: AnnualFinancialStatements,
) -> None:
    ticker = _input_ticker(company)
    if ticker != normalize_ticker_input(annual_statements.ticker):
        raise ValueError(
            f"Company input {ticker!r} does not match Task 72 data for "
            f"{annual_statements.ticker!r}."
        )
    if not isinstance(fiscal_year, int):
        raise TypeError("fiscal_year must be an integer")


def _fiscal_year_end(
    statements: AnnualFinancialStatements, fiscal_year: int
) -> Tuple[Optional[str], Optional[str]]:
    ends = [
        value.period_end
        for value in statements.values
        if value.fiscal_year == fiscal_year
        and value.financial_field in _DURATION_METRICS
        and value.status is FactStatus.RETRIEVED
        and value.period_end
    ]
    if not ends:
        return None, "No retrieved full-year fact establishes fiscal year-end."
    if len(Counter(ends)) != 1:
        return None, "Annual facts disagree on fiscal year-end; no date was selected."
    return ends[0], None


def _matches(
    statements: AnnualFinancialStatements, metric_name: str, fiscal_year: int
) -> Tuple[AnnualFinancialValue, ...]:
    return tuple(
        value
        for value in statements.values
        if value.fiscal_year == fiscal_year
        and value.financial_field == metric_name
    )


def _empty_result(
    statements: AnnualFinancialStatements,
    metric_name: str,
    fiscal_year: int,
    status: FactStatus,
    reason: str,
    *,
    candidate_facts: Tuple[AnnualFinancialValue, ...] = (),
) -> TaxMetricExtraction:
    return TaxMetricExtraction(
        metric_name=metric_name,
        company_name=statements.company_name,
        ticker=statements.ticker,
        raw_sec_value=None,
        raw_unit=None,
        normalized_usd_millions=None,
        fiscal_year=fiscal_year,
        period_start=None,
        period_end=None,
        balance_sheet_date=None,
        filing_form=None,
        filing_date=None,
        accession_number=None,
        xbrl_taxonomy=None,
        xbrl_concept=None,
        deferred_tax_presentation_type=None,
        source_url=statements.company_facts_url,
        status=status,
        validation_reason=reason,
        candidate_facts=candidate_facts,
    )


def extract_income_tax_expense(
    company: Union[CompanyIdentity, str],
    fiscal_year: int,
    annual_statements: AnnualFinancialStatements,
) -> TaxMetricExtraction:
    _validate_input(company, fiscal_year, annual_statements)
    matches = _matches(annual_statements, INCOME_TAX_EXPENSE_METRIC, fiscal_year)
    if not matches:
        return _empty_result(
            annual_statements,
            INCOME_TAX_EXPENSE_METRIC,
            fiscal_year,
            FactStatus.MISSING,
            "No annual Income Tax Expense record exists.",
        )
    if len(matches) > 1:
        return _empty_result(
            annual_statements,
            INCOME_TAX_EXPENSE_METRIC,
            fiscal_year,
            FactStatus.NEEDS_VALIDATION,
            "Conflicting Income Tax Expense facts exist.",
            candidate_facts=matches,
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
        reason = "Quarterly or YTD Income Tax Expense is not valid annual data."
    elif status is FactStatus.RETRIEVED and concept_key not in VALID_TAX_EXPENSE_CONCEPTS:
        status = FactStatus.NEEDS_VALIDATION
        reason = "The selected concept is not approved for Income Tax Expense."

    return _result_from_fact(
        annual_statements, fact, status, reason, presentation=None, point_in_time=False
    )


def _extract_deferred_tax(
    company: Union[CompanyIdentity, str],
    fiscal_year: int,
    statements: AnnualFinancialStatements,
    metric_name: str,
    valid_concepts: frozenset[tuple[str, str]],
) -> TaxMetricExtraction:
    _validate_input(company, fiscal_year, statements)
    matches = _matches(statements, metric_name, fiscal_year)
    if not matches:
        return _empty_result(
            statements,
            metric_name,
            fiscal_year,
            FactStatus.MISSING,
            f"No fiscal-year-end {metric_name} record exists.",
        )
    if len(matches) > 1:
        presentations = {
            DEFERRED_TAX_PRESENTATIONS.get(
                (item.xbrl_taxonomy, item.xbrl_concept),
                DeferredTaxPresentation.UNKNOWN,
            )
            for item in matches
        }
        reason = (
            "Gross and net deferred-tax candidates coexist and are not equivalent; "
            "no value was selected."
            if len(presentations) > 1
            else f"Conflicting {metric_name} facts exist; no value was selected."
        )
        return _empty_result(
            statements,
            metric_name,
            fiscal_year,
            FactStatus.NEEDS_VALIDATION,
            reason,
            candidate_facts=matches,
        )

    fact = matches[0]
    status = fact.status
    reason = fact.validation_reason or fact.missing_reason
    concept_key = (fact.xbrl_taxonomy, fact.xbrl_concept)
    presentation = DEFERRED_TAX_PRESENTATIONS.get(
        concept_key, DeferredTaxPresentation.UNKNOWN
    )
    fiscal_year_end, year_end_error = _fiscal_year_end(statements, fiscal_year)

    if status is FactStatus.RETRIEVED and year_end_error:
        status = FactStatus.NEEDS_VALIDATION
        reason = year_end_error
    elif status is FactStatus.RETRIEVED and fact.period_start is not None:
        status = FactStatus.NEEDS_VALIDATION
        reason = f"{metric_name} must be a point-in-time fact."
    elif status is FactStatus.RETRIEVED and fact.period_end != fiscal_year_end:
        status = FactStatus.NEEDS_VALIDATION
        reason = (
            f"Fact date {fact.period_end!r} does not match fiscal year-end "
            f"{fiscal_year_end!r}."
        )
    elif status is FactStatus.RETRIEVED and concept_key not in valid_concepts:
        status = FactStatus.NEEDS_VALIDATION
        reason = f"The selected concept is not approved for {metric_name}."
    elif status is FactStatus.RETRIEVED and concept_key in _PARTIAL_DEFERRED_TAX_CONCEPTS:
        status = FactStatus.NEEDS_VALIDATION
        reason = (
            "The concept represents only a current or noncurrent portion, not a "
            "confident total deferred-tax balance."
        )

    return _result_from_fact(
        statements, fact, status, reason, presentation=presentation, point_in_time=True
    )


def _result_from_fact(
    statements: AnnualFinancialStatements,
    fact: AnnualFinancialValue,
    status: FactStatus,
    reason: Optional[str],
    *,
    presentation: Optional[DeferredTaxPresentation],
    point_in_time: bool,
) -> TaxMetricExtraction:
    raw_is_numeric = isinstance(fact.raw_value, (int, float)) and not isinstance(
        fact.raw_value, bool
    )
    can_normalize = (
        status is FactStatus.RETRIEVED and fact.unit == "USD" and raw_is_numeric
    )
    if status is FactStatus.RETRIEVED and not can_normalize:
        status = FactStatus.NEEDS_VALIDATION
        reason = (
            f"{fact.financial_field} cannot be normalized to USD millions without "
            "estimation or currency conversion."
        )
    return TaxMetricExtraction(
        metric_name=fact.financial_field,
        company_name=statements.company_name,
        ticker=statements.ticker,
        raw_sec_value=fact.raw_value,
        raw_unit=fact.unit,
        normalized_usd_millions=(fact.raw_value / 1_000_000 if can_normalize else None),
        fiscal_year=fact.fiscal_year,
        period_start=None if point_in_time else fact.period_start,
        period_end=None if point_in_time else fact.period_end,
        balance_sheet_date=fact.period_end if point_in_time else None,
        filing_form=fact.filing_form,
        filing_date=fact.filing_date,
        accession_number=fact.accession_number,
        xbrl_taxonomy=fact.xbrl_taxonomy,
        xbrl_concept=fact.xbrl_concept,
        deferred_tax_presentation_type=presentation,
        source_url=fact.source_url,
        status=status,
        validation_reason=reason,
        candidate_values=fact.candidate_values,
    )


def extract_deferred_tax_assets(
    company: Union[CompanyIdentity, str],
    fiscal_year: int,
    annual_statements: AnnualFinancialStatements,
) -> TaxMetricExtraction:
    return _extract_deferred_tax(
        company, fiscal_year, annual_statements, DTA_METRIC, VALID_DTA_CONCEPTS
    )


def extract_deferred_tax_liabilities(
    company: Union[CompanyIdentity, str],
    fiscal_year: int,
    annual_statements: AnnualFinancialStatements,
) -> TaxMetricExtraction:
    return _extract_deferred_tax(
        company, fiscal_year, annual_statements, DTL_METRIC, VALID_DTL_CONCEPTS
    )
