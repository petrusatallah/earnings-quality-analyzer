"""Point-in-time extractors for Task 76 working-capital balances."""

from collections import Counter
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


_DURATION_METRICS = frozenset(
    definition.name
    for definition in FINANCIAL_FIELD_DEFINITIONS
    if definition.duration
)

VALID_BALANCE_SHEET_CONCEPTS = {
    "Accounts Receivable": frozenset(
        {
            ("us-gaap", "AccountsReceivableNetCurrent"),
            ("us-gaap", "AccountsReceivableNet"),
            ("ifrs-full", "TradeReceivablesCurrent"),
        }
    ),
    "Inventory": frozenset(
        {
            ("us-gaap", "InventoryNet"),
            (
                "us-gaap",
                "InventoryNetOfAllowancesCustomerAdvancesAndProgressBillings",
            ),
            ("ifrs-full", "Inventories"),
        }
    ),
    "Accounts Payable": frozenset(
        {
            ("us-gaap", "AccountsPayableCurrent"),
            ("ifrs-full", "TradePayablesCurrent"),
            ("ifrs-full", "TradePayables"),
        }
    ),
}

BROAD_AP_CONCEPTS = frozenset(
    {
        ("us-gaap", "AccountsPayableAndAccruedLiabilitiesCurrent"),
        ("ifrs-full", "TradeAndOtherCurrentPayables"),
    }
)


@dataclass(frozen=True)
class BalanceSheetMetricExtraction(ProvenanceMixin):
    metric_name: str
    company_name: str
    ticker: str
    raw_sec_value: Any
    raw_unit: Optional[str]
    normalized_usd_millions: Optional[float]
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
        return None, "No retrieved full-year duration fact establishes fiscal year-end."

    counts = Counter(period_ends)
    if len(counts) != 1:
        return None, (
            "Retrieved annual duration facts disagree on the fiscal-year-end date; "
            "no balance-sheet date was selected."
        )
    return period_ends[0], None


def _empty_result(
    annual_statements: AnnualFinancialStatements,
    metric_name: str,
    fiscal_year: int,
    status: FactStatus,
    reason: str,
) -> BalanceSheetMetricExtraction:
    return BalanceSheetMetricExtraction(
        metric_name=metric_name,
        company_name=annual_statements.company_name,
        ticker=annual_statements.ticker,
        raw_sec_value=None,
        raw_unit=None,
        normalized_usd_millions=None,
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
    )


def _extract_balance_sheet_metric(
    company: Union[CompanyIdentity, str],
    fiscal_year: int,
    annual_statements: AnnualFinancialStatements,
    metric_name: str,
) -> BalanceSheetMetricExtraction:
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
            f"Multiple {metric_name} records exist for the same fiscal year.",
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
        reason = "A balance-sheet fact must be point-in-time, not a duration fact."
    elif status is FactStatus.RETRIEVED and fact.period_end != fiscal_year_end:
        status = FactStatus.NEEDS_VALIDATION
        reason = (
            f"Fact date {fact.period_end!r} does not match fiscal year-end "
            f"{fiscal_year_end!r}; the value was rejected."
        )
    elif status is FactStatus.RETRIEVED and concept_key not in VALID_BALANCE_SHEET_CONCEPTS[metric_name]:
        status = FactStatus.NEEDS_VALIDATION
        if metric_name == "Accounts Payable" and concept_key in BROAD_AP_CONCEPTS:
            reason = (
                "The candidate combines Accounts Payable with accrued or other "
                "liabilities and cannot replace pure Accounts Payable."
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

    return BalanceSheetMetricExtraction(
        metric_name=metric_name,
        company_name=annual_statements.company_name,
        ticker=annual_statements.ticker,
        raw_sec_value=fact.raw_value,
        raw_unit=fact.unit,
        normalized_usd_millions=(fact.raw_value / 1_000_000 if can_normalize else None),
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


def extract_accounts_receivable(
    company: Union[CompanyIdentity, str],
    fiscal_year: int,
    annual_statements: AnnualFinancialStatements,
) -> BalanceSheetMetricExtraction:
    return _extract_balance_sheet_metric(
        company, fiscal_year, annual_statements, "Accounts Receivable"
    )


def extract_inventory(
    company: Union[CompanyIdentity, str],
    fiscal_year: int,
    annual_statements: AnnualFinancialStatements,
) -> BalanceSheetMetricExtraction:
    return _extract_balance_sheet_metric(
        company, fiscal_year, annual_statements, "Inventory"
    )


def extract_accounts_payable(
    company: Union[CompanyIdentity, str],
    fiscal_year: int,
    annual_statements: AnnualFinancialStatements,
) -> BalanceSheetMetricExtraction:
    return _extract_balance_sheet_metric(
        company, fiscal_year, annual_statements, "Accounts Payable"
    )
