"""Live validation tests for Task 73 Revenue extraction."""

import os
import sys
from datetime import date
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from Data.company_identifier import IdentificationStatus, identify_company  # noqa: E402
from Data.financial_statement_fetcher import (  # noqa: E402
    ANNUAL_FORMS,
    FactStatus,
    SECFinancialStatementFetcher,
)
from Data.revenue_extractor import (  # noqa: E402
    VALID_REVENUE_CONCEPTS,
    extract_revenue,
)


LIVE_TICKERS = ("AAPL", "MSFT", "AMZN")


def test_task_73_live_revenue_extraction() -> None:
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
        revenue_facts = tuple(
            value
            for value in statements.values
            if value.financial_field == "Revenue"
            and value.status is FactStatus.RETRIEVED
        )
        assert revenue_facts
        latest_fiscal_year = max(value.fiscal_year for value in revenue_facts)
        source_fact = next(
            value
            for value in revenue_facts
            if value.fiscal_year == latest_fiscal_year
        )
        raw_value_before_extraction = source_fact.raw_value

        result = extract_revenue(
            identity_result.company,
            latest_fiscal_year,
            statements,
        )

        assert result.status is FactStatus.RETRIEVED
        assert result.metric_name == "Revenue"
        assert result.ticker == ticker
        assert result.fiscal_year == latest_fiscal_year
        assert result.filing_form in ANNUAL_FORMS
        assert result.filing_date
        assert result.accession_number
        assert result.source_url
        assert (result.xbrl_taxonomy, result.xbrl_concept) in VALID_REVENUE_CONCEPTS
        assert result.raw_sec_value == raw_value_before_extraction
        assert source_fact.raw_value == raw_value_before_extraction
        assert result.raw_unit == "USD"
        assert result.normalized_usd_millions == result.raw_sec_value / 1_000_000
        assert result.accession_number == source_fact.accession_number
        assert result.source_url == source_fact.source_url

        assert source_fact.period_start and source_fact.period_end
        annual_days = (
            date.fromisoformat(source_fact.period_end)
            - date.fromisoformat(source_fact.period_start)
        ).days
        assert 300 <= annual_days <= 430

        print(f"Company: {result.company_name}")
        print(f"Ticker: {result.ticker}")
        print(f"Fiscal year: {result.fiscal_year}")
        print(f"Revenue raw SEC value: {result.raw_sec_value}")
        print(f"Raw unit: {result.raw_unit}")
        print(f"Normalized USD millions: {result.normalized_usd_millions:,.6f}")
        print(f"Filing form: {result.filing_form}")
        print(f"Filing date: {result.filing_date}")
        print(f"Accession number: {result.accession_number}")
        print(f"XBRL concept: {result.xbrl_taxonomy}:{result.xbrl_concept}")
        print(f"Source: {result.source_url}")
        print(f"Status: {result.status.value}")

    print("Task 73 Revenue extraction tests passed")


if __name__ == "__main__":
    test_task_73_live_revenue_extraction()
