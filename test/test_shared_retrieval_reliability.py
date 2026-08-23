"""Synthetic reliability tests shared by Tasks 70-75."""

import sys
from pathlib import Path
from unittest.mock import patch


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from Data.financial_statement_fetcher import (  # noqa: E402
    AnnualFinancialStatements,
    FINANCIAL_FIELD_DEFINITIONS,
    FactStatus,
    SECFinancialStatementFetcher,
    SourceClassification,
    TransientSecRequestError,
    _extract_field,
)
from Data.revenue_extractor import extract_revenue  # noqa: E402


CIK = "0000000001"
FACTS_URL = "https://data.sec.gov/api/xbrl/companyfacts/CIK0000000001.json"
REVENUE_DEFINITION = next(
    definition
    for definition in FINANCIAL_FIELD_DEFINITIONS
    if definition.name == "Revenue"
)
REVENUE_CONCEPT = "RevenueFromContractWithCustomerExcludingAssessedTax"


def _payload(entries, unit="USD"):
    return {
        "facts": {
            "us-gaap": {
                REVENUE_CONCEPT: {
                    "units": {unit: entries},
                }
            }
        }
    }


def _entry(**overrides):
    entry = {
        "fy": 2025,
        "fp": "FY",
        "form": "10-K",
        "start": "2025-01-01",
        "end": "2025-12-31",
        "filed": "2026-02-15",
        "accn": "0000000001-26-000001",
        "val": 1_000_000_000,
    }
    entry.update(overrides)
    return entry


def test_wrong_period_and_quarterly_facts_are_never_selected() -> None:
    short_annual_candidate = _extract_field(
        _payload([_entry(start="2025-07-01")]),
        REVENUE_DEFINITION,
        2025,
        CIK,
        FACTS_URL,
    )
    assert short_annual_candidate.status is FactStatus.NEEDS_VALIDATION
    assert short_annual_candidate.raw_value is None
    assert short_annual_candidate.candidate_values[0].period_start == "2025-07-01"

    quarterly_only = _extract_field(
        _payload([_entry(form="10-Q", fp="Q3", start="2025-01-01")]),
        REVENUE_DEFINITION,
        2025,
        CIK,
        FACTS_URL,
    )
    assert quarterly_only.status is FactStatus.MISSING
    assert quarterly_only.raw_value is None


def test_conflicting_original_and_amended_facts_need_validation() -> None:
    conflict = _extract_field(
        _payload(
            [
                _entry(),
                _entry(
                    form="10-K/A",
                    filed="2026-03-01",
                    accn="0000000001-26-000002",
                    val=1_100_000_000,
                ),
            ]
        ),
        REVENUE_DEFINITION,
        2025,
        CIK,
        FACTS_URL,
    )
    assert conflict.status is FactStatus.NEEDS_VALIDATION
    assert conflict.raw_value is None
    assert {candidate.raw_value for candidate in conflict.candidate_values} == {
        1_000_000_000,
        1_100_000_000,
    }


def test_consistent_amendment_is_selected_auditably() -> None:
    amended = _extract_field(
        _payload(
            [
                _entry(),
                _entry(
                    form="10-K/A",
                    filed="2026-03-01",
                    accn="0000000001-26-000002",
                ),
            ]
        ),
        REVENUE_DEFINITION,
        2025,
        CIK,
        FACTS_URL,
    )
    assert amended.status is FactStatus.RETRIEVED
    assert amended.raw_value == 1_000_000_000
    assert amended.filing_form == "10-K/A"
    assert amended.accession_number == "0000000001-26-000002"


def test_missing_metric_remains_missing() -> None:
    missing = _extract_field(
        {"facts": {}}, REVENUE_DEFINITION, 2025, CIK, FACTS_URL
    )
    assert missing.status is FactStatus.MISSING
    assert missing.raw_value is None
    assert missing.candidate_values == ()


def test_non_usd_unit_is_preserved_and_never_labeled_usd_millions() -> None:
    raw_fact = _extract_field(
        _payload([_entry(val=900_000_000)], unit="EUR"),
        REVENUE_DEFINITION,
        2025,
        CIK,
        FACTS_URL,
    )
    statements = AnnualFinancialStatements(
        company_name="Example Corporation",
        ticker="EXM",
        cik=CIK,
        source_classification=SourceClassification.PRIMARY,
        values=(raw_fact,),
        company_facts_url=FACTS_URL,
    )
    result = extract_revenue("EXM", 2025, statements)

    assert result.status is FactStatus.NEEDS_VALIDATION
    assert result.raw_sec_value == 900_000_000
    assert result.raw_unit == "EUR"
    assert result.normalized_usd_millions is None


def test_temporary_sec_errors_retry_and_successful_response_is_cached() -> None:
    calls = []

    def loader(url, headers, timeout):
        calls.append(url)
        assert "@" in headers["User-Agent"]
        if len(calls) == 1:
            raise TransientSecRequestError("temporary", retry_after=0)
        return {"ok": True}

    fetcher = SECFinancialStatementFetcher(
        "EarningsQualityAgent tests@example.com",
        max_retries=2,
        retry_backoff_seconds=0,
        json_loader=loader,
    )
    with patch("Data.financial_statement_fetcher.time.sleep"):
        first = fetcher._get_json(FACTS_URL)
        second = fetcher._get_json(FACTS_URL)

    assert first == {"ok": True}
    assert second is first
    assert len(calls) == 2


if __name__ == "__main__":
    test_wrong_period_and_quarterly_facts_are_never_selected()
    test_conflicting_original_and_amended_facts_need_validation()
    test_consistent_amendment_is_selected_auditably()
    test_missing_metric_remains_missing()
    test_non_usd_unit_is_preserved_and_never_labeled_usd_millions()
    test_temporary_sec_errors_retry_and_successful_response_is_cached()
    print("Tasks 70-75 shared reliability tests passed")
