"""Fiscal-year-end Shares Outstanding extractor for Task 79."""

from collections import Counter
from dataclasses import dataclass
from typing import Any, Optional, Tuple, Union

from Data.company_identifier import CompanyIdentity, normalize_ticker_input
from Data.financial_statement_fetcher import (
    AnnualFinancialStatements,
    AnnualFinancialValue,
    CandidateFinancialValue,
    FINANCIAL_FIELD_DEFINITIONS,
    FactStatus,
)
from Data.provenance import ProvenanceMixin


SHARES_OUTSTANDING_METRIC = "Shares Outstanding"
_SHARES_DEFINITION = next(
    definition
    for definition in FINANCIAL_FIELD_DEFINITIONS
    if definition.name == SHARES_OUTSTANDING_METRIC
)
VALID_SHARES_OUTSTANDING_CONCEPTS = frozenset(
    (candidate.taxonomy, candidate.concept)
    for candidate in _SHARES_DEFINITION.concepts
)
_DURATION_METRICS = frozenset(
    definition.name
    for definition in FINANCIAL_FIELD_DEFINITIONS
    if definition.duration
)

INVALID_SHARE_SUBSTITUTES = frozenset(
    {
        ("us-gaap", "WeightedAverageNumberOfSharesOutstandingBasic"),
        ("us-gaap", "WeightedAverageNumberOfDilutedSharesOutstanding"),
        ("us-gaap", "CommonStockSharesAuthorized"),
        ("us-gaap", "CommonStockSharesIssued"),
    }
)


@dataclass(frozen=True)
class SharesOutstandingExtraction(ProvenanceMixin):
    metric_name: str
    company_name: str
    ticker: str
    raw_sec_value: Any
    raw_unit: Optional[str]
    normalized_shares_millions: Optional[float]
    fiscal_year: int
    balance_sheet_date: Optional[str]
    filing_form: Optional[str]
    filing_date: Optional[str]
    accession_number: Optional[str]
    xbrl_taxonomy: Optional[str]
    xbrl_concept: Optional[str]
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


def _fiscal_year_end(
    annual_statements: AnnualFinancialStatements, fiscal_year: int
) -> Tuple[Optional[str], Optional[str]]:
    period_ends = [
        value.period_end
        for value in annual_statements.values
        if value.fiscal_year == fiscal_year
        and value.financial_field in _DURATION_METRICS
        and value.status is FactStatus.RETRIEVED
        and value.period_end
    ]
    if not period_ends:
        return None, "No retrieved full-year fact establishes fiscal year-end."
    counts = Counter(period_ends)
    if len(counts) != 1:
        return None, "Annual facts disagree on fiscal year-end; no date was selected."
    return period_ends[0], None


def _empty_result(
    annual_statements: AnnualFinancialStatements,
    fiscal_year: int,
    status: FactStatus,
    reason: str,
    *,
    candidate_facts: Tuple[AnnualFinancialValue, ...] = (),
) -> SharesOutstandingExtraction:
    return SharesOutstandingExtraction(
        metric_name=SHARES_OUTSTANDING_METRIC,
        company_name=annual_statements.company_name,
        ticker=annual_statements.ticker,
        raw_sec_value=None,
        raw_unit=None,
        normalized_shares_millions=None,
        fiscal_year=fiscal_year,
        balance_sheet_date=None,
        filing_form=None,
        filing_date=None,
        accession_number=None,
        xbrl_taxonomy=None,
        xbrl_concept=None,
        source_url=annual_statements.company_facts_url,
        status=status,
        validation_reason=reason,
        candidate_facts=candidate_facts,
    )


def extract_shares_outstanding(
    company: Union[CompanyIdentity, str],
    fiscal_year: int,
    annual_statements: AnnualFinancialStatements,
) -> SharesOutstandingExtraction:
    """Extract actual fiscal-year-end shares without averaging or combining."""

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
        and value.financial_field == SHARES_OUTSTANDING_METRIC
    )
    if not matches:
        return _empty_result(
            annual_statements,
            fiscal_year,
            FactStatus.MISSING,
            "No fiscal-year-end Shares Outstanding record exists.",
        )
    if len(matches) > 1:
        concepts = {(item.xbrl_taxonomy, item.xbrl_concept) for item in matches}
        reason = (
            "Multiple share-class or Shares Outstanding candidates exist; "
            "classes were not combined."
            if len(concepts) > 1
            else "Conflicting Shares Outstanding facts exist; no value was selected."
        )
        return _empty_result(
            annual_statements,
            fiscal_year,
            FactStatus.NEEDS_VALIDATION,
            reason,
            candidate_facts=matches,
        )

    fact = matches[0]
    fiscal_year_end, year_end_error = _fiscal_year_end(
        annual_statements, fiscal_year
    )
    status = fact.status
    reason = fact.validation_reason or fact.missing_reason
    concept_key = (fact.xbrl_taxonomy, fact.xbrl_concept)

    if status is FactStatus.RETRIEVED and year_end_error:
        status = FactStatus.NEEDS_VALIDATION
        reason = year_end_error
    elif status is FactStatus.RETRIEVED and fact.period_start is not None:
        status = FactStatus.NEEDS_VALIDATION
        reason = "Shares Outstanding must be point-in-time, not a duration average."
    elif status is FactStatus.RETRIEVED and fact.period_end != fiscal_year_end:
        status = FactStatus.NEEDS_VALIDATION
        reason = (
            f"Shares date {fact.period_end!r} does not match fiscal year-end "
            f"{fiscal_year_end!r}; the value was rejected."
        )
    elif status is FactStatus.RETRIEVED and concept_key not in VALID_SHARES_OUTSTANDING_CONCEPTS:
        status = FactStatus.NEEDS_VALIDATION
        if concept_key in INVALID_SHARE_SUBSTITUTES:
            reason = (
                "Weighted-average, diluted, authorized, or issued shares cannot "
                "replace fiscal-year-end Shares Outstanding."
            )
        else:
            reason = "The selected concept is not approved for Shares Outstanding."

    raw_is_numeric = isinstance(fact.raw_value, (int, float)) and not isinstance(
        fact.raw_value, bool
    )
    can_normalize = (
        status is FactStatus.RETRIEVED and fact.unit == "shares" and raw_is_numeric
    )
    if status is FactStatus.RETRIEVED and not can_normalize:
        status = FactStatus.NEEDS_VALIDATION
        reason = "Shares Outstanding must have the raw XBRL unit 'shares'."

    return SharesOutstandingExtraction(
        metric_name=SHARES_OUTSTANDING_METRIC,
        company_name=annual_statements.company_name,
        ticker=annual_statements.ticker,
        raw_sec_value=fact.raw_value,
        raw_unit=fact.unit,
        normalized_shares_millions=(
            fact.raw_value / 1_000_000 if can_normalize else None
        ),
        fiscal_year=fiscal_year,
        balance_sheet_date=fact.period_end,
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
