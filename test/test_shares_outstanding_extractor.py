"""Live and synthetic tests for Shares Outstanding extraction."""

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
    FINANCIAL_FIELD_DEFINITIONS,
    FactStatus,
    SECFinancialStatementFetcher,
    _extract_field,
)
from Data.shares_outstanding_extractor import (  # noqa: E402
    VALID_SHARES_OUTSTANDING_CONCEPTS,
    extract_shares_outstanding,
)
from Data.source_policy import SourceClassification  # noqa: E402


LIVE_TICKERS = ("AAPL", "MSFT", "AMZN")
FACTS_URL = "https://data.sec.gov/api/xbrl/companyfacts/CIK0000000001.json"
SHARES_DEFINITION = next(
    definition
    for definition in FINANCIAL_FIELD_DEFINITIONS
    if definition.name == "Shares Outstanding"
)


def _sec_entry(
    value,
    *,
    fiscal_year=2024,
    end="2024-09-28",
    start=None,
    form="10-K",
    fiscal_period="FY",
    filed="2024-11-01",
    accession="0000000001-24-000123",
):
    entry = {
        "fy": fiscal_year,
        "fp": fiscal_period,
        "end": end,
        "val": value,
        "form": form,
        "filed": filed,
        "accn": accession,
    }
    if start is not None:
        entry["start"] = start
    return entry


def _companyfacts(*, common=(), entity=(), weighted=()):
    return {
        "facts": {
            "us-gaap": {
                "RevenueFromContractWithCustomerExcludingAssessedTax": {
                    "units": {
                        "USD": [
                            _sec_entry(
                                400_000_000_000,
                                start="2023-10-01",
                            )
                        ]
                    }
                },
                "CommonStockSharesOutstanding": {
                    "units": {"shares": list(common)}
                },
                "WeightedAverageNumberOfSharesOutstandingBasic": {
                    "units": {"shares": list(weighted)}
                },
            },
            "dei": {
                "EntityCommonStockSharesOutstanding": {
                    "units": {"shares": list(entity)}
                }
            },
        }
    }


def _extract_fetcher_shares(payload, fiscal_year=2024):
    return _extract_field(
        payload,
        SHARES_DEFINITION,
        fiscal_year,
        "0000000001",
        FACTS_URL,
    )


def test_task_109_selects_exact_annual_shares_and_preserves_sec_fact() -> None:
    # Company Facts can tag a valid instant fact Q4 even when its source is the
    # annual 10-K and its date is exactly fiscal year-end.
    annual = _sec_entry(15_116_786_000, fiscal_period="Q4")
    result = _extract_fetcher_shares(_companyfacts(common=(annual,)))

    assert result.status is FactStatus.RETRIEVED
    assert result.raw_value == 15_116_786_000
    assert result.unit == "shares"
    assert result.fiscal_year == 2024
    assert result.period_start is None
    assert result.period_end == "2024-09-28"
    assert result.filing_form == "10-K"
    assert result.filing_date == "2024-11-01"
    assert result.accession_number == "0000000001-24-000123"
    assert result.source_url == (
        "https://www.sec.gov/Archives/edgar/data/1/000000000124000123/"
    )
    assert result.sec_source_identifier == "CIK0000000001:0000000001-24-000123"
    assert result.xbrl_taxonomy == "us-gaap"
    assert result.xbrl_concept == "CommonStockSharesOutstanding"


def test_task_109_maps_shares_to_fiscal_year_end_not_cover_date() -> None:
    fiscal_year_end = _sec_entry(15_116_786_000)
    later_repeat = _sec_entry(
        15_116_000_000,
        fiscal_year=2025,
        filed="2025-10-31",
        accession="0000000001-25-000125",
    )
    cover_page = _sec_entry(
        15_115_823_000,
        end="2024-10-18",
        accession="0000000001-24-000124",
    )

    result = _extract_fetcher_shares(
        _companyfacts(
            common=(fiscal_year_end, later_repeat),
            entity=(cover_page,),
        )
    )

    assert result.status is FactStatus.RETRIEVED
    assert result.raw_value == fiscal_year_end["val"]
    assert result.period_end == "2024-09-28"
    assert result.xbrl_concept == "CommonStockSharesOutstanding"
    assert result.accession_number == fiscal_year_end["accn"]


def test_task_109_rejects_weighted_average_eps_shares() -> None:
    weighted_average = _sec_entry(
        15_343_783_000,
        start="2023-10-01",
    )

    result = _extract_fetcher_shares(
        _companyfacts(weighted=(weighted_average,))
    )

    assert result.status is FactStatus.MISSING
    assert result.raw_value is None
    assert result.xbrl_concept is None
    assert "point-in-time" in result.missing_reason


def test_task_109_unavailable_annual_shares_remain_missing() -> None:
    result = _extract_fetcher_shares(_companyfacts())

    assert result.status is FactStatus.MISSING
    assert result.raw_value is None
    assert result.period_end is None
    assert result.accession_number is None
    assert "no value was guessed" in result.missing_reason


def test_task_79_live_shares_outstanding_extraction() -> None:
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
            if value.financial_field == "Shares Outstanding"
        )
        annual_revenue = next(
            value
            for value in statements.for_fiscal_year(latest_fiscal_year)
            if value.financial_field == "Revenue"
            and value.status is FactStatus.RETRIEVED
        )
        raw_before_extraction = source_fact.raw_value

        result = extract_shares_outstanding(
            identity_result.company, latest_fiscal_year, statements
        )

        if source_fact.status is FactStatus.MISSING:
            assert result.status is FactStatus.MISSING
            assert result.raw_sec_value is None
            assert result.normalized_shares_millions is None
            continue

        assert result.status is FactStatus.RETRIEVED
        assert result.metric_name == "Shares Outstanding"
        assert result.raw_sec_value == raw_before_extraction
        assert source_fact.raw_value == raw_before_extraction
        assert result.raw_unit == "shares"
        assert result.normalized_shares_millions == result.raw_sec_value / 1_000_000
        assert result.balance_sheet_date == annual_revenue.period_end
        assert result.filing_form == source_fact.filing_form
        assert result.filing_date == source_fact.filing_date
        assert result.accession_number == source_fact.accession_number
        assert result.source_url == source_fact.source_url
        assert (
            result.xbrl_taxonomy,
            result.xbrl_concept,
        ) in VALID_SHARES_OUTSTANDING_CONCEPTS

        print(f"Company: {result.company_name}")
        print(f"Ticker: {result.ticker}")
        print(f"Metric: {result.metric_name}")
        print(f"Raw SEC value: {result.raw_sec_value}")
        print(f"Raw unit: {result.raw_unit}")
        print(f"Normalized shares millions: {result.normalized_shares_millions:,.6f}")
        print(f"Fiscal year: {result.fiscal_year}")
        print(f"Balance-sheet date: {result.balance_sheet_date}")
        print(f"Filing form: {result.filing_form}")
        print(f"Filing date: {result.filing_date}")
        print(f"Accession number: {result.accession_number}")
        print(f"XBRL concept: {result.xbrl_taxonomy}:{result.xbrl_concept}")
        print(f"Source: {result.source_url}")
        print(f"Status: {result.status.value}")

    print("Task 79 live Shares Outstanding extraction tests passed")


def _fact(
    metric="Shares Outstanding",
    concept="CommonStockSharesOutstanding",
    *,
    end="2025-12-31",
    value=100_000_000,
    start=None,
):
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
        unit="USD" if metric == "Revenue" else "shares",
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


def _annual_revenue():
    return _fact(
        metric="Revenue",
        concept="RevenueFromContractWithCustomerExcludingAssessedTax",
        start="2025-01-01",
        value=1_000_000_000,
    )


def test_wrong_balance_sheet_date_is_rejected() -> None:
    shares = _fact(end="2025-11-30")
    result = extract_shares_outstanding(
        "EXM", 2025, _statements(_annual_revenue(), shares)
    )
    assert result.status is FactStatus.NEEDS_VALIDATION
    assert result.raw_sec_value == shares.raw_value
    assert result.normalized_shares_millions is None


def test_weighted_average_shares_do_not_replace_year_end_shares() -> None:
    weighted = _fact(
        concept="WeightedAverageNumberOfSharesOutstandingBasic",
        start="2025-01-01",
    )
    result = extract_shares_outstanding(
        "EXM", 2025, _statements(_annual_revenue(), weighted)
    )
    assert result.status is FactStatus.NEEDS_VALIDATION
    assert result.normalized_shares_millions is None
    assert "point-in-time" in result.validation_reason


def test_missing_shares_remain_missing() -> None:
    result = extract_shares_outstanding(
        "EXM", 2025, _statements(_annual_revenue())
    )
    assert result.status is FactStatus.MISSING
    assert result.raw_sec_value is None


def test_conflicting_share_facts_need_validation() -> None:
    shares = _fact()
    conflict = replace(shares, raw_value=110_000_000)
    result = extract_shares_outstanding(
        "EXM", 2025, _statements(_annual_revenue(), shares, conflict)
    )
    assert result.status is FactStatus.NEEDS_VALIDATION
    assert result.raw_sec_value is None
    assert len(result.candidate_facts) == 2


def test_multiple_share_classes_are_not_combined() -> None:
    class_a = _fact(concept="CommonStockSharesOutstanding", value=80_000_000)
    class_b = _fact(
        concept="EntityCommonStockSharesOutstanding", value=20_000_000
    )
    result = extract_shares_outstanding(
        "EXM", 2025, _statements(_annual_revenue(), class_a, class_b)
    )
    assert result.status is FactStatus.NEEDS_VALIDATION
    assert result.raw_sec_value is None
    assert result.normalized_shares_millions is None
    assert {fact.raw_value for fact in result.candidate_facts} == {
        80_000_000,
        20_000_000,
    }
    assert "not combined" in result.validation_reason


if __name__ == "__main__":
    test_wrong_balance_sheet_date_is_rejected()
    test_weighted_average_shares_do_not_replace_year_end_shares()
    test_missing_shares_remain_missing()
    test_conflicting_share_facts_need_validation()
    test_multiple_share_classes_are_not_combined()
    test_task_79_live_shares_outstanding_extraction()
