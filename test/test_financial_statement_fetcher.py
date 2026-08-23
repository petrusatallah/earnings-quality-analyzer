"""Live SEC retrieval test for Task 72.

Set SEC_USER_AGENT to an identifying value before running, for example:
    $env:SEC_USER_AGENT = "EarningsQualityAgent your-email@example.com"
    python test/test_financial_statement_fetcher.py
"""

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
    FINANCIAL_FIELD_DEFINITIONS,
    FactStatus,
    SECFinancialStatementFetcher,
    _extract_field,
)


CORE_METRICS = ("Revenue", "Net Income", "Operating Cash Flow")
REQUIRED_METRICS = CORE_METRICS + (
    "Accounts Receivable",
    "Inventory",
    "Accounts Payable",
    "Depreciation & Amortization",
    "Capital Expenditures",
    "Stock-Based Compensation",
    "Shares Outstanding",
    "Income Tax Expense",
    "Deferred Tax Assets",
    "Deferred Tax Liabilities",
)

ADDITIONAL_LIVE_COMPANIES = ("MSFT", "AMZN")
DURATION_BY_METRIC = {
    definition.name: definition.duration
    for definition in FINANCIAL_FIELD_DEFINITIONS
}
DA_DEFINITION = next(
    definition
    for definition in FINANCIAL_FIELD_DEFINITIONS
    if definition.name == "Depreciation & Amortization"
)
SYNTHETIC_CIK = "0000000001"
SYNTHETIC_FACTS_URL = (
    "https://data.sec.gov/api/xbrl/companyfacts/CIK0000000001.json"
)


def _da_entry(value, *, accession="0000000001-26-000001"):
    return {
        "fy": 2025,
        "fp": "FY",
        "form": "10-K",
        "start": "2025-01-01",
        "end": "2025-12-31",
        "filed": "2026-02-15",
        "accn": accession,
        "val": value,
    }


def _da_payload(*, combined=(), depreciation=()):
    return {
        "facts": {
            "us-gaap": {
                "DepreciationDepletionAndAmortization": {
                    "units": {"USD": list(combined)}
                },
                "Depreciation": {"units": {"USD": list(depreciation)}},
            }
        }
    }


def test_verified_combined_da_is_accepted_and_preferred() -> None:
    result = _extract_field(
        _da_payload(
            combined=(_da_entry(1_250_000_000),),
            depreciation=(_da_entry(900_000_000),),
        ),
        DA_DEFINITION,
        2025,
        SYNTHETIC_CIK,
        SYNTHETIC_FACTS_URL,
    )

    assert result.status is FactStatus.RETRIEVED
    assert result.financial_field == "Depreciation & Amortization"
    assert result.raw_value == 1_250_000_000
    assert result.xbrl_taxonomy == "us-gaap"
    assert result.xbrl_concept == "DepreciationDepletionAndAmortization"


def test_depreciation_only_is_preserved_as_unavailable_evidence_not_da() -> None:
    result = _extract_field(
        _da_payload(depreciation=(_da_entry(900_000_000),)),
        DA_DEFINITION,
        2025,
        SYNTHETIC_CIK,
        SYNTHETIC_FACTS_URL,
    )

    assert result.status is FactStatus.NEEDS_VALIDATION
    assert result.raw_value is None
    assert result.financial_field == "Depreciation & Amortization"
    assert result.unit == "USD"
    assert result.period_start == "2025-01-01"
    assert result.period_end == "2025-12-31"
    assert result.xbrl_taxonomy == "us-gaap"
    assert result.xbrl_concept == "Depreciation"
    assert result.filing_form == "10-K"
    assert result.filing_date == "2026-02-15"
    assert result.accession_number == "0000000001-26-000001"
    assert result.source_url == (
        "https://www.sec.gov/Archives/edgar/data/1/000000000126000001/"
    )
    assert "depreciation only" in result.validation_reason
    assert "no amortization was substituted or estimated" in result.validation_reason
    assert result.candidate_values[0].raw_value == 900_000_000

def _normalized_usd_millions(raw_value, unit):
    """Return a separate display normalization without mutating the SEC fact."""

    if unit != "USD" or not isinstance(raw_value, (int, float)):
        return None
    return raw_value / 1_000_000


def test_task_72_apple_retrieval() -> None:
    user_agent = os.environ.get("SEC_USER_AGENT", "").strip()
    if not user_agent:
        raise RuntimeError(
            "Set SEC_USER_AGENT to an identifying application name and real "
            "contact email before running this live SEC test."
        )

    identity_result = identify_company("AAPL")
    assert identity_result.status is IdentificationStatus.MATCHED
    assert identity_result.company is not None
    assert identity_result.company.ticker == "AAPL"

    fetcher = SECFinancialStatementFetcher(user_agent)
    sec_company = fetcher.resolve_cik(identity_result.company)
    assert sec_company.ticker == "AAPL"
    assert sec_company.cik == "0000320193"

    statements = fetcher.fetch(identity_result.company)
    available = tuple(
        value
        for value in statements.values
        if value.status is FactStatus.RETRIEVED
        and value.financial_field in CORE_METRICS
    )
    metrics_by_year = {}
    for value in available:
        metrics_by_year.setdefault(value.fiscal_year, {})[value.financial_field] = value

    complete_years = tuple(
        fiscal_year
        for fiscal_year, metrics in metrics_by_year.items()
        if all(metric in metrics for metric in CORE_METRICS)
    )
    assert complete_years, "No annual filing contained all required Task 72 metrics."

    latest_fiscal_year = max(complete_years)
    latest_values = {
        value.financial_field: value
        for value in statements.for_fiscal_year(latest_fiscal_year)
        if value.financial_field in REQUIRED_METRICS
    }
    assert set(latest_values) == set(REQUIRED_METRICS)

    # These three established checks must remain successful for the latest year.
    latest_core_metrics = {metric: latest_values[metric] for metric in CORE_METRICS}
    assert all(
        metric.status is FactStatus.RETRIEVED
        for metric in latest_core_metrics.values()
    )
    filing_forms = {value.filing_form for value in latest_core_metrics.values()}
    assert filing_forms <= set(ANNUAL_FORMS)
    assert None not in filing_forms

    print(f"Company: {statements.company_name}")
    print(f"Ticker: {statements.ticker}")
    print(f"CIK: {statements.cik}")
    print(f"Fiscal year: {latest_fiscal_year}")
    print(f"Filing form: {', '.join(sorted(filing_forms))}")

    summary = {"Retrieved": 0, "Missing": 0, "Needs Validation": 0}

    for metric_name in REQUIRED_METRICS:
        metric = latest_values[metric_name]
        raw_value_before_normalization = metric.raw_value

        if metric.status is FactStatus.MISSING:
            summary["Missing"] += 1
            print(f"{metric_name}: MISSING")
            print(f"  Fiscal year: {metric.fiscal_year}")
            print(f"  Source: {metric.source_url}")
            continue

        if metric.status is FactStatus.NEEDS_VALIDATION:
            summary["Needs Validation"] += 1
            print(f"{metric_name}: NEEDS VALIDATION")
            print(f"  Fiscal year: {metric.fiscal_year}")
            print(f"  Candidate concept: {metric.xbrl_taxonomy}:{metric.xbrl_concept}")
            print(f"  Source: {metric.source_url}")
            print(f"  Reason: {metric.validation_reason}")
            for candidate in metric.candidate_values:
                print(f"  Candidate raw SEC value: {candidate.raw_value}")
                print(f"  Candidate raw unit: {candidate.unit}")
                print(
                    "  Candidate XBRL concept: "
                    f"{candidate.xbrl_taxonomy}:{candidate.xbrl_concept}"
                )
                print(f"  Candidate source: {candidate.source_url}")
            continue

        normalized_value = _normalized_usd_millions(metric.raw_value, metric.unit)
        assert metric.raw_value == raw_value_before_normalization

        expected_unit = "shares" if metric_name == "Shares Outstanding" else "USD"
        metadata_complete = all(
            (
                metric.raw_value is not None,
                metric.filing_form in ANNUAL_FORMS,
                bool(metric.xbrl_concept),
                bool(metric.xbrl_taxonomy),
                bool(metric.source_url),
            )
        )
        confident = metadata_complete and metric.unit == expected_unit

        if confident:
            summary["Retrieved"] += 1
            status_text = FactStatus.RETRIEVED.value
        else:
            summary["Needs Validation"] += 1
            status_text = FactStatus.NEEDS_VALIDATION.value

        print(f"{metric_name}: {status_text}")
        print(f"  Raw SEC value: {metric.raw_value}")
        print(f"  Raw unit: {metric.unit}")
        print(
            "  Normalized USD millions: "
            + (f"{normalized_value:,.6f}" if normalized_value is not None else "N/A")
        )
        print(f"  Fiscal year: {metric.fiscal_year}")
        print(f"  XBRL concept: {metric.xbrl_taxonomy}:{metric.xbrl_concept}")
        print(f"  Source: {metric.source_url}")

    assert all(
        latest_values[metric_name].status is FactStatus.RETRIEVED
        for metric_name in CORE_METRICS
    )
    assert sum(summary.values()) == len(REQUIRED_METRICS)

    print("Validation summary:")
    print(f"  Retrieved: {summary['Retrieved']}")
    print(f"  Missing: {summary['Missing']}")
    print(f"  Needs Validation: {summary['Needs Validation']}")

    print("Task 72 full retrieval test passed")


def test_task_72_additional_company_reliability() -> None:
    user_agent = os.environ.get("SEC_USER_AGENT", "").strip()
    if not user_agent:
        raise RuntimeError(
            "Set SEC_USER_AGENT to an identifying application name and real "
            "contact email before running this live SEC test."
        )

    for ticker in ADDITIONAL_LIVE_COMPANIES:
        identity_result = identify_company(ticker)
        assert identity_result.status is IdentificationStatus.MATCHED
        assert identity_result.company is not None
        assert identity_result.company.ticker == ticker

        fetcher = SECFinancialStatementFetcher(user_agent)
        sec_company = fetcher.resolve_cik(identity_result.company)
        assert sec_company.ticker == ticker
        assert len(sec_company.cik) == 10 and sec_company.cik.isdigit()

        statements = fetcher.fetch(identity_result.company)
        assert statements.values, f"No annual SEC facts were returned for {ticker}."

        all_keys = tuple(
            (value.fiscal_year, value.financial_field)
            for value in statements.values
        )
        assert len(all_keys) == len(set(all_keys)), (
            f"Duplicate metric/fiscal-year records were returned for {ticker}."
        )

        latest_fiscal_year = max(value.fiscal_year for value in statements.values)
        latest_values = statements.for_fiscal_year(latest_fiscal_year)
        assert len(latest_values) == len(REQUIRED_METRICS)
        assert {value.financial_field for value in latest_values} == set(REQUIRED_METRICS)

        print(f"Company: {statements.company_name}")
        print(f"Ticker: {statements.ticker}")
        print(f"CIK: {statements.cik}")

        for metric in latest_values:
            assert metric.status in {
                FactStatus.RETRIEVED,
                FactStatus.MISSING,
                FactStatus.NEEDS_VALIDATION,
            }

            if metric.status is FactStatus.RETRIEVED:
                assert metric.raw_value is not None
                assert metric.filing_form in ANNUAL_FORMS
                assert metric.xbrl_concept
                assert metric.source_url

                if DURATION_BY_METRIC[metric.financial_field]:
                    assert metric.period_start and metric.period_end
                    period_days = (
                        date.fromisoformat(metric.period_end)
                        - date.fromisoformat(metric.period_start)
                    ).days
                    assert 300 <= period_days <= 430, (
                        f"Quarterly/YTD period selected for {ticker} "
                        f"{metric.financial_field}: {period_days} days."
                    )
                else:
                    assert metric.period_start is None
            else:
                # A missing or uncertain metric must never contain an estimated
                # selected value. Auditable candidates remain separate.
                assert metric.raw_value is None
                if metric.status is FactStatus.MISSING:
                    assert not metric.candidate_values
                else:
                    assert metric.validation_reason

            print(f"Metric: {metric.financial_field}")
            print(f"  Status: {metric.status.value}")
            print(f"  Value: {metric.raw_value if metric.raw_value is not None else 'N/A'}")
            print(
                "  XBRL concept: "
                + (
                    f"{metric.xbrl_taxonomy}:{metric.xbrl_concept}"
                    if metric.xbrl_concept
                    else "N/A"
                )
            )
            print(f"  Fiscal year: {metric.fiscal_year}")
            print(f"  Filing form: {metric.filing_form or 'N/A'}")
            print(f"  Source: {metric.source_url or 'N/A'}")

        print(f"Task 72 {ticker} reliability test passed")


if __name__ == "__main__":
    test_verified_combined_da_is_accepted_and_preferred()
    test_depreciation_only_is_preserved_as_unavailable_evidence_not_da()
    test_task_72_apple_retrieval()
    test_task_72_additional_company_reliability()
