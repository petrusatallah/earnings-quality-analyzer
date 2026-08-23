"""Task 82 shared provenance validation tests."""

import sys
from pathlib import Path
from types import SimpleNamespace


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from Data.da_capex_extractors import AnnualDurationMetricExtraction  # noqa: E402
from Data.deferred_tax_extractors import TaxMetricExtraction  # noqa: E402
from Data.net_income_extractor import NetIncomeExtraction  # noqa: E402
from Data.one_off_candidate_extractor import OneOffCandidate, OneOffStatus  # noqa: E402
from Data.operating_cash_flow_extractor import OperatingCashFlowExtraction  # noqa: E402
from Data.provenance import (  # noqa: E402
    ProvenanceMixin,
    ProvenanceStatus,
    validate_provenance,
)
from Data.revenue_extractor import RevenueExtraction  # noqa: E402
from Data.sbc_extractor import StockBasedCompensationExtraction  # noqa: E402
from Data.shares_outstanding_extractor import SharesOutstandingExtraction  # noqa: E402
from Data.working_capital_extractors import BalanceSheetMetricExtraction  # noqa: E402


DURATION_METRICS = (
    "Revenue", "Net Income", "Operating Cash Flow",
    "Depreciation & Amortization", "Capital Expenditures",
    "Stock-Based Compensation", "Income Tax Expense",
)
POINT_IN_TIME_METRICS = (
    "Accounts Receivable", "Inventory", "Accounts Payable",
    "Shares Outstanding", "Deferred Tax Assets", "Deferred Tax Liabilities",
)


def _numeric_value(metric_name: str):
    point_in_time = metric_name in POINT_IN_TIME_METRICS
    return SimpleNamespace(
        metric_name=metric_name,
        raw_sec_value=1_000_000,
        raw_unit="shares" if metric_name == "Shares Outstanding" else "USD",
        fiscal_year=2025,
        filing_form="10-K",
        filing_date="2026-02-15",
        accession_number="0000000001-26-000001",
        source_url="https://www.sec.gov/Archives/edgar/data/1/example.htm",
        xbrl_taxonomy="us-gaap",
        xbrl_concept="ExampleConcept",
        balance_sheet_date="2025-12-31" if point_in_time else None,
        period_start=None if point_in_time else "2025-01-01",
        period_end=None if point_in_time else "2025-12-31",
        status="RETRIEVED",
    )


def test_all_financial_metrics_have_complete_required_provenance() -> None:
    for metric_name in DURATION_METRICS + POINT_IN_TIME_METRICS:
        provenance = validate_provenance(_numeric_value(metric_name))
        assert provenance.provenance_status is ProvenanceStatus.COMPLETE
        assert provenance.source_url
        assert provenance.fiscal_year == 2025
        assert provenance.raw_unit
        assert provenance.xbrl_concept == "ExampleConcept"
        if metric_name in POINT_IN_TIME_METRICS:
            assert provenance.extraction_location.balance_sheet_date == "2025-12-31"
        else:
            assert provenance.extraction_location.period_start == "2025-01-01"
            assert provenance.extraction_location.period_end == "2025-12-31"


def test_all_existing_extraction_result_types_expose_shared_provenance() -> None:
    result_types = (
        RevenueExtraction,
        NetIncomeExtraction,
        OperatingCashFlowExtraction,
        BalanceSheetMetricExtraction,
        AnnualDurationMetricExtraction,
        StockBasedCompensationExtraction,
        SharesOutstandingExtraction,
        TaxMetricExtraction,
        OneOffCandidate,
    )
    assert all(issubclass(result_type, ProvenanceMixin) for result_type in result_types)


def test_one_off_candidate_preserves_available_evidence_and_location() -> None:
    candidate = OneOffCandidate(
        fiscal_year=2024,
        candidate_name="State Aid Decision",
        category="Unusual Tax Charge or Benefit",
        raw_amount=10_200_000_000,
        raw_unit="USD",
        normalized_usd_millions=10_200,
        impact_direction="Decreases income / increases expense",
        xbrl_concept="us-gaap:CurrentIncomeTaxExpenseBenefit",
        filing_form="10-K",
        filing_date="2024-11-01",
        accession_number="0000320193-24-000123",
        filing_section_or_note="Note 7",
        source_url="https://www.sec.gov/Archives/edgar/data/320193/example.htm",
        source_evidence="The company recorded a one-time income tax charge.",
        status=OneOffStatus.CANDIDATE_FOUND,
    )
    provenance = candidate.provenance
    assert provenance.provenance_status is ProvenanceStatus.COMPLETE
    assert provenance.extraction_location.filing_section_or_note == "Note 7"
    assert provenance.extraction_location.source_evidence == candidate.source_evidence


def test_incomplete_numeric_provenance_is_flagged_for_validation() -> None:
    incomplete = _numeric_value("Revenue")
    incomplete.source_url = None
    incomplete.xbrl_concept = None
    incomplete.period_start = None
    provenance = validate_provenance(incomplete)
    assert provenance.provenance_status is ProvenanceStatus.INCOMPLETE_NEEDS_VALIDATION
    assert set(provenance.missing_required_fields) == {
        "source_url", "xbrl_concept", "period_start"
    }


if __name__ == "__main__":
    test_all_financial_metrics_have_complete_required_provenance()
    test_all_existing_extraction_result_types_expose_shared_provenance()
    test_one_off_candidate_preserves_available_evidence_and_location()
    test_incomplete_numeric_provenance_is_flagged_for_validation()
    print("Task 82 provenance tests passed")
