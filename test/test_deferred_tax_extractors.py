"""Live and synthetic tests for Task 80 tax extractors."""

import os
import sys
from dataclasses import replace
from datetime import date
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from Data.company_identifier import IdentificationStatus, identify_company  # noqa: E402
from Data.deferred_tax_extractors import (  # noqa: E402
    DeferredTaxPresentation,
    extract_deferred_tax_assets,
    extract_deferred_tax_liabilities,
    extract_income_tax_expense,
)
from Data.financial_statement_fetcher import (  # noqa: E402
    AnnualFinancialStatements,
    AnnualFinancialValue,
    FactStatus,
    SECFinancialStatementFetcher,
)
from Data.source_policy import SourceClassification  # noqa: E402


LIVE_TICKERS = ("AAPL", "MSFT", "AMZN")
EXTRACTORS = (
    ("Income Tax Expense", extract_income_tax_expense),
    ("Deferred Tax Assets", extract_deferred_tax_assets),
    ("Deferred Tax Liabilities", extract_deferred_tax_liabilities),
)
FACTS_URL = "https://data.sec.gov/api/xbrl/companyfacts/CIK0000000001.json"


def test_task_80_live_tax_extraction() -> None:
    user_agent = os.environ.get("SEC_USER_AGENT", "").strip()
    if not user_agent:
        raise RuntimeError(
            "Set SEC_USER_AGENT to an identifying application name and real "
            "contact email before running this live SEC test."
        )
    for ticker in LIVE_TICKERS:
        identity = identify_company(ticker)
        assert identity.status is IdentificationStatus.MATCHED
        assert identity.company is not None
        statements = SECFinancialStatementFetcher(user_agent).fetch(identity.company)
        fiscal_year = max(value.fiscal_year for value in statements.values)
        revenue = next(
            value
            for value in statements.for_fiscal_year(fiscal_year)
            if value.financial_field == "Revenue"
            and value.status is FactStatus.RETRIEVED
        )

        for metric_name, extractor in EXTRACTORS:
            source_fact = next(
                value
                for value in statements.for_fiscal_year(fiscal_year)
                if value.financial_field == metric_name
            )
            raw_before = source_fact.raw_value
            result = extractor(identity.company, fiscal_year, statements)

            assert result.status is FactStatus.RETRIEVED
            assert result.raw_sec_value == raw_before
            assert source_fact.raw_value == raw_before
            assert result.raw_unit == "USD"
            assert result.normalized_usd_millions == result.raw_sec_value / 1_000_000
            assert result.accession_number == source_fact.accession_number
            assert result.source_url == source_fact.source_url
            if metric_name == "Income Tax Expense":
                assert result.period_start and result.period_end
                days = (
                    date.fromisoformat(result.period_end)
                    - date.fromisoformat(result.period_start)
                ).days
                assert 330 <= days <= 400
                assert result.balance_sheet_date is None
                assert result.deferred_tax_presentation_type is None
            else:
                assert result.period_start is None and result.period_end is None
                assert result.balance_sheet_date == revenue.period_end
                assert result.deferred_tax_presentation_type in {
                    DeferredTaxPresentation.GROSS_DTA,
                    DeferredTaxPresentation.NET_DTA,
                    DeferredTaxPresentation.GROSS_DTL,
                    DeferredTaxPresentation.NET_DTL,
                    DeferredTaxPresentation.UNKNOWN,
                }

            print(f"Company: {result.company_name}")
            print(f"Ticker: {result.ticker}")
            print(f"Metric: {result.metric_name}")
            print(f"Raw SEC value: {result.raw_sec_value}")
            print(f"Raw unit: {result.raw_unit}")
            print(f"Normalized USD millions: {result.normalized_usd_millions:,.6f}")
            print(f"Fiscal year: {result.fiscal_year}")
            print(f"Period start: {result.period_start or 'N/A'}")
            print(f"Period end: {result.period_end or 'N/A'}")
            print(f"Balance-sheet date: {result.balance_sheet_date or 'N/A'}")
            print(f"Filing form: {result.filing_form}")
            print(f"Filing date: {result.filing_date}")
            print(f"Accession number: {result.accession_number}")
            print(f"XBRL concept: {result.xbrl_taxonomy}:{result.xbrl_concept}")
            presentation = result.deferred_tax_presentation_type
            print(f"Deferred-tax presentation: {presentation.value if presentation else 'N/A'}")
            print(f"Source: {result.source_url}")
            print(f"Status: {result.status.value}")
    print("Task 80 live deferred-tax extraction tests passed")


def _fact(metric, concept, *, start=None, end="2025-12-31", value=1_000_000_000, unit="USD"):
    return AnnualFinancialValue(
        financial_field=metric,
        financial_statement="Income Statement" if metric in {"Revenue", "Income Tax Expense"} else "Balance Sheet",
        fiscal_year=2025,
        status=FactStatus.RETRIEVED,
        raw_value=value,
        filing_form="10-K",
        filing_date="2026-02-15",
        accession_number="0000000001-26-000001",
        source_url="https://www.sec.gov/Archives/edgar/data/1/example/",
        sec_source_identifier="CIK0000000001:example",
        xbrl_taxonomy="us-gaap",
        xbrl_concept=concept,
        unit=unit,
        period_start=start,
        period_end=end,
    )


def _revenue():
    return _fact("Revenue", "RevenueFromContractWithCustomerExcludingAssessedTax", start="2025-01-01")


def _statements(*facts):
    return AnnualFinancialStatements(
        company_name="Example Corporation",
        ticker="EXM",
        cik="0000000001",
        source_classification=SourceClassification.PRIMARY,
        values=facts,
        company_facts_url=FACTS_URL,
    )


def test_quarterly_tax_expense_is_rejected() -> None:
    tax = _fact("Income Tax Expense", "IncomeTaxExpenseBenefit", start="2025-07-01")
    result = extract_income_tax_expense("EXM", 2025, _statements(tax))
    assert result.status is FactStatus.NEEDS_VALIDATION
    assert result.raw_sec_value == tax.raw_value
    assert result.normalized_usd_millions is None


def test_wrong_deferred_tax_balance_sheet_dates_are_rejected() -> None:
    dta = _fact("Deferred Tax Assets", "DeferredTaxAssetsNet", end="2025-11-30")
    dtl = _fact("Deferred Tax Liabilities", "DeferredTaxLiabilities", end="2025-11-30")
    statements = _statements(_revenue(), dta, dtl)
    for result in (
        extract_deferred_tax_assets("EXM", 2025, statements),
        extract_deferred_tax_liabilities("EXM", 2025, statements),
    ):
        assert result.status is FactStatus.NEEDS_VALIDATION
        assert result.normalized_usd_millions is None


def test_missing_dta_and_dtl_remain_missing() -> None:
    statements = _statements(_revenue())
    assert extract_deferred_tax_assets("EXM", 2025, statements).status is FactStatus.MISSING
    assert extract_deferred_tax_liabilities("EXM", 2025, statements).status is FactStatus.MISSING


def test_conflicting_deferred_tax_facts_need_validation() -> None:
    dta = _fact("Deferred Tax Assets", "DeferredTaxAssetsNet")
    result = extract_deferred_tax_assets(
        "EXM", 2025, _statements(_revenue(), dta, replace(dta, raw_value=1_100_000_000))
    )
    assert result.status is FactStatus.NEEDS_VALIDATION
    assert result.raw_sec_value is None


def test_gross_and_net_deferred_tax_are_not_treated_as_equivalent() -> None:
    gross = _fact("Deferred Tax Assets", "DeferredTaxAssetsGross")
    net = _fact("Deferred Tax Assets", "DeferredTaxAssetsNet", value=800_000_000)
    result = extract_deferred_tax_assets(
        "EXM", 2025, _statements(_revenue(), gross, net)
    )
    assert result.status is FactStatus.NEEDS_VALIDATION
    assert result.raw_sec_value is None
    assert len(result.candidate_facts) == 2
    assert "not equivalent" in result.validation_reason


def test_non_usd_unit_is_preserved() -> None:
    dtl = _fact("Deferred Tax Liabilities", "DeferredTaxLiabilities", unit="EUR")
    result = extract_deferred_tax_liabilities(
        "EXM", 2025, _statements(_revenue(), dtl)
    )
    assert result.status is FactStatus.NEEDS_VALIDATION
    assert result.raw_sec_value == dtl.raw_value
    assert result.raw_unit == "EUR"
    assert result.normalized_usd_millions is None


if __name__ == "__main__":
    test_quarterly_tax_expense_is_rejected()
    test_wrong_deferred_tax_balance_sheet_dates_are_rejected()
    test_missing_dta_and_dtl_remain_missing()
    test_conflicting_deferred_tax_facts_need_validation()
    test_gross_and_net_deferred_tax_are_not_treated_as_equivalent()
    test_non_usd_unit_is_preserved()
    test_task_80_live_tax_extraction()
