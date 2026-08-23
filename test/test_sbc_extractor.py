"""Live and synthetic tests for Task 78 SBC extraction."""

import os
import sys
from dataclasses import replace
from datetime import date
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
from Data.sbc_extractor import (  # noqa: E402
    VALID_SBC_CONCEPTS,
    extract_stock_based_compensation,
)
from Data.source_policy import SourceClassification  # noqa: E402


LIVE_TICKERS = ("AAPL", "MSFT", "AMZN")
FACTS_URL = "https://data.sec.gov/api/xbrl/companyfacts/CIK0000000001.json"


def test_task_78_live_sbc_extraction() -> None:
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
        source_fact = next(
            value
            for value in statements.for_fiscal_year(latest_fiscal_year)
            if value.financial_field == "Stock-Based Compensation"
        )
        raw_before_extraction = source_fact.raw_value

        result = extract_stock_based_compensation(
            identity_result.company, latest_fiscal_year, statements
        )

        assert result.status is FactStatus.RETRIEVED
        assert result.metric_name == "Stock-Based Compensation"
        assert result.raw_sec_value == raw_before_extraction
        assert source_fact.raw_value == raw_before_extraction
        assert result.raw_unit == "USD"
        assert result.normalized_usd_millions == result.raw_sec_value / 1_000_000
        assert result.period_start and result.period_end
        period_days = (
            date.fromisoformat(result.period_end)
            - date.fromisoformat(result.period_start)
        ).days
        assert 330 <= period_days <= 400
        assert result.filing_form == source_fact.filing_form
        assert result.filing_date == source_fact.filing_date
        assert result.accession_number == source_fact.accession_number
        assert result.source_url == source_fact.source_url
        assert (
            result.xbrl_taxonomy,
            result.xbrl_concept,
        ) in VALID_SBC_CONCEPTS

        print(f"Company: {result.company_name}")
        print(f"Ticker: {result.ticker}")
        print(f"Metric: {result.metric_name}")
        print(f"Raw SEC value: {result.raw_sec_value}")
        print(f"Raw unit: {result.raw_unit}")
        print(f"Normalized USD millions: {result.normalized_usd_millions:,.6f}")
        print(f"Fiscal year: {result.fiscal_year}")
        print(f"Period start: {result.period_start}")
        print(f"Period end: {result.period_end}")
        print(f"Filing form: {result.filing_form}")
        print(f"Filing date: {result.filing_date}")
        print(f"Accession number: {result.accession_number}")
        print(f"XBRL concept: {result.xbrl_taxonomy}:{result.xbrl_concept}")
        print(f"Source: {result.source_url}")
        print(f"Status: {result.status.value}")

    print("Task 78 live SBC extraction tests passed")


def _fact(
    concept="ShareBasedCompensation",
    *,
    start="2025-01-01",
    end="2025-12-31",
    value=1_000_000_000,
    unit="USD",
):
    return AnnualFinancialValue(
        financial_field="Stock-Based Compensation",
        financial_statement="Cash Flow Statement",
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


def _statements(*facts):
    return AnnualFinancialStatements(
        company_name="Example Corporation",
        ticker="EXM",
        cik="0000000001",
        source_classification=SourceClassification.PRIMARY,
        values=facts,
        company_facts_url=FACTS_URL,
    )


def test_quarterly_and_ytd_sbc_are_rejected() -> None:
    ytd = _fact(start="2025-04-01")
    result = extract_stock_based_compensation("EXM", 2025, _statements(ytd))
    assert result.status is FactStatus.NEEDS_VALIDATION
    assert result.raw_sec_value == ytd.raw_value
    assert result.normalized_usd_millions is None


def test_missing_sbc_remains_missing() -> None:
    result = extract_stock_based_compensation("EXM", 2025, _statements())
    assert result.status is FactStatus.MISSING
    assert result.raw_sec_value is None


def test_conflicting_sbc_candidates_need_validation() -> None:
    sbc = _fact()
    conflict = replace(sbc, raw_value=1_100_000_000)
    result = extract_stock_based_compensation(
        "EXM", 2025, _statements(sbc, conflict)
    )
    assert result.status is FactStatus.NEEDS_VALIDATION
    assert result.raw_sec_value is None


def test_broader_compensation_does_not_replace_sbc() -> None:
    broad = _fact(concept="LaborAndRelatedExpense")
    result = extract_stock_based_compensation(
        "EXM", 2025, _statements(broad)
    )
    assert result.status is FactStatus.NEEDS_VALIDATION
    assert result.raw_sec_value == broad.raw_value
    assert result.normalized_usd_millions is None
    assert "broader compensation" in result.validation_reason


def test_non_usd_unit_is_preserved() -> None:
    sbc = _fact(unit="EUR")
    result = extract_stock_based_compensation("EXM", 2025, _statements(sbc))
    assert result.status is FactStatus.NEEDS_VALIDATION
    assert result.raw_sec_value == sbc.raw_value
    assert result.raw_unit == "EUR"
    assert result.normalized_usd_millions is None


if __name__ == "__main__":
    test_quarterly_and_ytd_sbc_are_rejected()
    test_missing_sbc_remains_missing()
    test_conflicting_sbc_candidates_need_validation()
    test_broader_compensation_does_not_replace_sbc()
    test_non_usd_unit_is_preserved()
    test_task_78_live_sbc_extraction()
