"""Live and synthetic tests for Task 76 balance-sheet extractors."""

import os
import sys
from dataclasses import replace
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from Data.company_identifier import IdentificationStatus, identify_company  # noqa: E402
from Data.financial_statement_fetcher import (  # noqa: E402
    AnnualFinancialStatements,
    AnnualFinancialValue,
    FactStatus,
    SECFinancialStatementFetcher,
)
from Data.source_policy import SourceClassification  # noqa: E402
from Data.working_capital_extractors import (  # noqa: E402
    VALID_BALANCE_SHEET_CONCEPTS,
    extract_accounts_payable,
    extract_accounts_receivable,
    extract_inventory,
)


LIVE_TICKERS = ("AAPL", "MSFT", "AMZN")
EXTRACTORS = (
    ("Accounts Receivable", extract_accounts_receivable),
    ("Inventory", extract_inventory),
    ("Accounts Payable", extract_accounts_payable),
)
FACTS_URL = "https://data.sec.gov/api/xbrl/companyfacts/CIK0000000001.json"


def test_task_76_live_working_capital_extraction() -> None:
    user_agent = os.environ.get("SEC_USER_AGENT", "").strip()
    if not user_agent:
        raise RuntimeError(
            "Set SEC_USER_AGENT to an identifying application name and real "
            "contact email before running this live SEC test."
        )

    for ticker in LIVE_TICKERS:
        identity_result = identify_company(ticker)
        assert identity_result.status is IdentificationStatus.MATCHED
        assert identity_result.company is not None
        statements = SECFinancialStatementFetcher(user_agent).fetch(
            identity_result.company
        )
        latest_fiscal_year = max(value.fiscal_year for value in statements.values)
        annual_revenue = next(
            value
            for value in statements.for_fiscal_year(latest_fiscal_year)
            if value.financial_field == "Revenue"
            and value.status is FactStatus.RETRIEVED
        )
        fiscal_year_end = annual_revenue.period_end

        for metric_name, extractor in EXTRACTORS:
            source_fact = next(
                value
                for value in statements.for_fiscal_year(latest_fiscal_year)
                if value.financial_field == metric_name
            )
            raw_before_extraction = source_fact.raw_value
            result = extractor(
                identity_result.company, latest_fiscal_year, statements
            )

            assert result.status is FactStatus.RETRIEVED
            assert result.metric_name == metric_name
            assert result.raw_sec_value == raw_before_extraction
            assert source_fact.raw_value == raw_before_extraction
            assert result.raw_unit == "USD"
            assert result.normalized_usd_millions == result.raw_sec_value / 1_000_000
            assert result.balance_sheet_date == fiscal_year_end
            assert result.filing_form == source_fact.filing_form
            assert result.filing_date == source_fact.filing_date
            assert result.accession_number == source_fact.accession_number
            assert result.source_url == source_fact.source_url
            assert (
                result.xbrl_taxonomy,
                result.xbrl_concept,
            ) in VALID_BALANCE_SHEET_CONCEPTS[metric_name]

            print(f"Company: {result.company_name}")
            print(f"Ticker: {result.ticker}")
            print(f"Metric: {result.metric_name}")
            print(f"Raw SEC value: {result.raw_sec_value}")
            print(f"Raw unit: {result.raw_unit}")
            print(f"Normalized USD millions: {result.normalized_usd_millions:,.6f}")
            print(f"Fiscal year: {result.fiscal_year}")
            print(f"Balance-sheet date: {result.balance_sheet_date}")
            print(f"Filing form: {result.filing_form}")
            print(f"Filing date: {result.filing_date}")
            print(f"Accession number: {result.accession_number}")
            print(f"XBRL concept: {result.xbrl_taxonomy}:{result.xbrl_concept}")
            print(f"Source: {result.source_url}")
            print(f"Status: {result.status.value}")

    print("Task 76 live working-capital extraction tests passed")


def _fact(metric, concept, *, end="2025-12-31", value=1_000_000_000):
    return AnnualFinancialValue(
        financial_field=metric,
        financial_statement=(
            "Income Statement" if metric == "Revenue" else "Balance Sheet"
        ),
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
        unit="USD",
        period_start="2025-01-01" if metric == "Revenue" else None,
        period_end=end,
    )


def _statements(*facts):
    return AnnualFinancialStatements(
        company_name="Example Corporation",
        ticker="EXM",
        cik="0000000001",
        source_classification=SourceClassification.PRIMARY,
        values=facts,
        company_facts_url=FACTS_URL,
    )


def test_wrong_balance_sheet_date_is_rejected() -> None:
    revenue = _fact("Revenue", "RevenueFromContractWithCustomerExcludingAssessedTax")
    receivable = _fact(
        "Accounts Receivable", "AccountsReceivableNetCurrent", end="2025-09-30"
    )
    result = extract_accounts_receivable(
        "EXM", 2025, _statements(revenue, receivable)
    )
    assert result.status is FactStatus.NEEDS_VALIDATION
    assert result.raw_sec_value == receivable.raw_value
    assert result.normalized_usd_millions is None
    assert "does not match fiscal year-end" in result.validation_reason


def test_missing_inventory_remains_missing() -> None:
    revenue = _fact("Revenue", "RevenueFromContractWithCustomerExcludingAssessedTax")
    result = extract_inventory("EXM", 2025, _statements(revenue))
    assert result.status is FactStatus.MISSING
    assert result.raw_sec_value is None
    assert result.normalized_usd_millions is None


def test_conflicting_candidate_facts_need_validation() -> None:
    revenue = _fact("Revenue", "RevenueFromContractWithCustomerExcludingAssessedTax")
    inventory = _fact("Inventory", "InventoryNet")
    conflicting = replace(inventory, raw_value=1_100_000_000)
    result = extract_inventory(
        "EXM", 2025, _statements(revenue, inventory, conflicting)
    )
    assert result.status is FactStatus.NEEDS_VALIDATION
    assert result.raw_sec_value is None
    assert result.normalized_usd_millions is None


def test_broad_ap_concept_does_not_replace_accounts_payable() -> None:
    revenue = _fact("Revenue", "RevenueFromContractWithCustomerExcludingAssessedTax")
    broad_ap = _fact(
        "Accounts Payable", "AccountsPayableAndAccruedLiabilitiesCurrent"
    )
    result = extract_accounts_payable(
        "EXM", 2025, _statements(revenue, broad_ap)
    )
    assert result.status is FactStatus.NEEDS_VALIDATION
    assert result.raw_sec_value == broad_ap.raw_value
    assert result.normalized_usd_millions is None
    assert "combines Accounts Payable" in result.validation_reason


if __name__ == "__main__":
    test_wrong_balance_sheet_date_is_rejected()
    test_missing_inventory_remains_missing()
    test_conflicting_candidate_facts_need_validation()
    test_broad_ap_concept_does_not_replace_accounts_payable()
    test_task_76_live_working_capital_extraction()
