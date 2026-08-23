"""Task 108: verified Amazon extraction and analyzer coverage.

Fixed FY2023/FY2024 values are transcribed from Amazon's FY2024 Form 10-K.
Amounts are USD millions and shares are millions. Expected calculations and
rule results are reviewed literals, independent of production outputs.
"""

from __future__ import annotations

import contextlib
import io
import json
import math
import sys
from pathlib import Path

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

with contextlib.redirect_stdout(io.StringIO()):
    from Analysis.accrual_red_flags import AR_GAP_THRESHOLD, classify_accrual_signal
    from Analysis.capex_rule import rule_threshold as capex_threshold
    from Analysis.sbc_red_flags import LARGE_SBC_THRESHOLD
    from Analysis.sbc_vs_dilution import classify_year
    from Analysis.tax_red_flags import (
        MOVEMENT_THRESHOLD,
        calculate_growth,
        classify_dta_risk,
        classify_overall,
    )
    from Calculations.working_capital_analysis import classify_cash_effect

from Analysis.accrual_interpretation import interpret_accrual_quality
from Analysis.ai_input_preparation import build_ai_analysis_input
from Analysis.capex_interpretation import interpret_capex
from Analysis.deferred_tax_interpretation import interpret_deferred_taxes
from Analysis.sbc_interpretation import interpret_sbc
from Analysis.working_capital_interpretation import interpret_working_capital
from Data.analysis_validation_gate import AnalysisDecision, AnalysisValidationGateResult
from Data.company_identifier import IdentificationStatus, identify_company
from Data.financial_statement_fetcher import (
    FactStatus,
    SEC_COMPANY_FACTS_URL,
    SEC_TICKER_URL,
    SECFinancialStatementFetcher,
)


CIK = "0001018724"
FILING_METADATA = {
    2023: {"end": "2023-12-31", "filed": "2024-02-02", "accn": "0001018724-24-000008"},
    2024: {"end": "2024-12-31", "filed": "2025-02-07", "accn": "0001018724-25-000004"},
}
EXPECTED_RAW = {
    2023: {
        "Revenue": (574_785, "USD", "Income Statement", "RevenueFromContractWithCustomerExcludingAssessedTax"),
        "Net Income": (30_425, "USD", "Income Statement", "NetIncomeLoss"),
        "Operating Cash Flow": (84_946, "USD", "Cash Flow Statement", "NetCashProvidedByUsedInOperatingActivities"),
        "Accounts Receivable": (52_253, "USD", "Balance Sheet", "AccountsReceivableNetCurrent"),
        "Inventory": (33_318, "USD", "Balance Sheet", "InventoryNet"),
        "Accounts Payable": (84_981, "USD", "Balance Sheet", "AccountsPayableCurrent"),
        "Depreciation & Amortization": (48_663, "USD", "Cash Flow Statement", "DepreciationDepletionAndAmortization"),
        "Capital Expenditures": (52_729, "USD", "Cash Flow Statement", "PaymentsToAcquirePropertyPlantAndEquipment"),
        "Stock-Based Compensation": (24_023, "USD", "Cash Flow Statement", "ShareBasedCompensation"),
        "Shares Outstanding": (10_383, "shares", "Balance Sheet", "CommonStockSharesOutstanding"),
        "Income Tax Expense": (7_120, "USD", "Income Statement", "IncomeTaxExpenseBenefit"),
        "Deferred Tax Assets": (45_788, "USD", "Balance Sheet", "DeferredTaxAssetsNet"),
        "Deferred Tax Liabilities": (32_591, "USD", "Balance Sheet", "DeferredIncomeTaxLiabilities"),
    },
    2024: {
        "Revenue": (637_959, "USD", "Income Statement", "RevenueFromContractWithCustomerExcludingAssessedTax"),
        "Net Income": (59_248, "USD", "Income Statement", "NetIncomeLoss"),
        "Operating Cash Flow": (115_877, "USD", "Cash Flow Statement", "NetCashProvidedByUsedInOperatingActivities"),
        "Accounts Receivable": (55_451, "USD", "Balance Sheet", "AccountsReceivableNetCurrent"),
        "Inventory": (34_214, "USD", "Balance Sheet", "InventoryNet"),
        "Accounts Payable": (94_363, "USD", "Balance Sheet", "AccountsPayableCurrent"),
        "Depreciation & Amortization": (52_795, "USD", "Cash Flow Statement", "DepreciationDepletionAndAmortization"),
        "Capital Expenditures": (82_999, "USD", "Cash Flow Statement", "PaymentsToAcquirePropertyPlantAndEquipment"),
        "Stock-Based Compensation": (22_011, "USD", "Cash Flow Statement", "ShareBasedCompensation"),
        "Shares Outstanding": (10_593, "shares", "Balance Sheet", "CommonStockSharesOutstanding"),
        "Income Tax Expense": (9_265, "USD", "Income Statement", "IncomeTaxExpenseBenefit"),
        "Deferred Tax Assets": (55_045, "USD", "Balance Sheet", "DeferredTaxAssetsNet"),
        "Deferred Tax Liabilities": (39_080, "USD", "Balance Sheet", "DeferredIncomeTaxLiabilities"),
    },
}

# FCF follows the project's OCF - gross CapEx formula. Amazon separately reports
# an FCF measure using property purchases net of sales/incentives; it is not
# substituted for the project's calculation here.
EXPECTED_ANALYSIS_2024 = {
    "revenue_growth": 0.10990892246666145,
    "net_income_growth": 0.9473459326211997,
    "ocf_growth": 0.36412544439997174,
    "ar_growth": 0.06120222762329436,
    "inventory_growth": 0.026892370490425595,
    "ap_growth": 0.11040114849201586,
    "da_growth": 0.08491050695600354,
    "capex_growth": 0.5740674012403042,
    "sbc_growth": -0.08375306997460767,
    "shares_growth": 0.020225368390638543,
    "ar_revenue_gap": -0.04870669484336709,
    "free_cash_flow": 32_878,
    "net_working_capital_cash_effect": 5_288,
    "capex_to_da": 1.5720996306468416,
    "capex_to_revenue": 0.13010083720113674,
    "sbc_to_net_income": 0.3715062111801242,
    "dta_to_net_income": 0.9290608965703484,
    "dta_growth": 0.20217087446492532,
    "dtl_growth": 0.19910404712957566,
    "ar_flag": False,
    "ni_ocf_flag": False,
    "combined_accrual_flag": False,
    "accrual_severity": "None",
    "inventory_flag": False,
    "ap_classification": "Normal supplier financing pattern",
    "working_capital_cash_use": False,
    "working_capital_severity": "Low",
    "capex_flag": True,
    "capex_status": "Needs investigation",
    "capex_severity": "Medium",
    "dta_risk_flag": False,
    "deferred_tax_movement_flag": False,
    "tax_severity": "None",
    "large_sbc_flag": True,
    "dilution_flag": True,
    "sbc_severity": "Medium",
    "overall_severity": "Needs Investigation",
}

DURATION_METRICS = {
    "Revenue", "Net Income", "Operating Cash Flow", "Depreciation & Amortization",
    "Capital Expenditures", "Stock-Based Compensation", "Income Tax Expense",
}


def require_close(actual, expected, label: str) -> None:
    assert math.isclose(float(actual), float(expected), rel_tol=1e-12, abs_tol=1e-12), (
        f"{label}: expected {expected!r}, actual {actual!r}"
    )


def company_facts_payload() -> dict:
    facts = {"us-gaap": {}}
    for year, metrics in EXPECTED_RAW.items():
        metadata = FILING_METADATA[year]
        for metric, (value_millions, unit, _statement, concept) in metrics.items():
            entry = {
                "fy": year, "fp": "FY", "form": "10-K",
                "end": metadata["end"], "filed": metadata["filed"],
                "accn": metadata["accn"], "val": value_millions * 1_000_000,
            }
            if metric in DURATION_METRICS:
                entry["start"] = f"{year}-01-01"
            concept_payload = facts["us-gaap"].setdefault(concept, {"units": {}})
            concept_payload["units"].setdefault(unit, []).append(entry)
    return {"entityName": "Amazon.com, Inc.", "facts": facts}


def extracted_amazon_statements():
    identity = identify_company("Amazon")
    assert identity.status is IdentificationStatus.MATCHED
    assert identity.company is not None
    assert identity.company.ticker == "AMZN"
    assert identity.company.company_name == "Amazon.com, Inc."
    requests = []

    def fixed_loader(url, _headers, _timeout):
        requests.append(url)
        if url == SEC_TICKER_URL:
            return {"0": {"cik_str": 1018724, "ticker": "AMZN", "title": "Amazon.com, Inc."}}
        if url == SEC_COMPANY_FACTS_URL.format(cik=CIK):
            return company_facts_payload()
        raise AssertionError(f"unexpected source request: {url}")

    fetcher = SECFinancialStatementFetcher(
        "EarningsQualityAgent tests@example.com",
        minimum_request_interval=0.11,
        json_loader=fixed_loader,
    )
    return fetcher.fetch(identity.company, fiscal_years=(2023, 2024)), requests


def test_amazon_identification_extraction_and_provenance() -> None:
    statements, requests = extracted_amazon_statements()
    assert statements.company_name == "Amazon.com, Inc."
    assert statements.ticker == "AMZN"
    assert statements.cik == CIK
    assert len(requests) == 2, f"expected two mocked SEC reads, actual {requests!r}"

    actual = {(item.fiscal_year, item.financial_field): item for item in statements.values}
    assert len(actual) == 26, f"expected 26 facts, actual {len(actual)}"
    expected_source_directories = {
        "https://www.sec.gov/Archives/edgar/data/1018724/000101872424000008/",
        "https://www.sec.gov/Archives/edgar/data/1018724/000101872425000004/",
    }
    for year, metrics in EXPECTED_RAW.items():
        for metric, (expected_millions, unit, statement, concept) in metrics.items():
            item = actual[(year, metric)]
            prefix = f"company=AMZN, fiscal_year={year}, metric={metric}"
            assert item.status is FactStatus.RETRIEVED, f"{prefix}, expected Retrieved, actual={item.status.value}"
            assert item.raw_value == expected_millions * 1_000_000, f"{prefix}, expected={expected_millions * 1_000_000!r}, actual={item.raw_value!r}"
            assert item.unit == unit, f"{prefix}, expected unit={unit!r}, actual={item.unit!r}"
            assert item.financial_statement == statement, f"{prefix}, expected statement={statement!r}, actual={item.financial_statement!r}"
            assert item.xbrl_concept == concept, f"{prefix}, expected concept={concept!r}, actual={item.xbrl_concept!r}"
            assert item.filing_date == FILING_METADATA[year]["filed"], f"{prefix}, filing date mismatch"
            assert item.source_url in expected_source_directories, f"{prefix}, unexpected provenance={item.source_url!r}"


def calculated_amazon_results() -> tuple[dict, dict]:
    statements, _ = extracted_amazon_statements()
    values = {
        (item.fiscal_year, item.financial_field): item.raw_value / 1_000_000
        for item in statements.values
    }
    growth_fields = {
        "revenue_growth": "Revenue", "net_income_growth": "Net Income",
        "ocf_growth": "Operating Cash Flow", "ar_growth": "Accounts Receivable",
        "inventory_growth": "Inventory", "ap_growth": "Accounts Payable",
        "da_growth": "Depreciation & Amortization", "capex_growth": "Capital Expenditures",
        "sbc_growth": "Stock-Based Compensation", "shares_growth": "Shares Outstanding",
    }
    results = {
        name: calculate_growth(values[(2024, metric)], values[(2023, metric)])
        for name, metric in growth_fields.items()
    }
    ar_change = values[(2024, "Accounts Receivable")] - values[(2023, "Accounts Receivable")]
    inventory_change = values[(2024, "Inventory")] - values[(2023, "Inventory")]
    ap_change = values[(2024, "Accounts Payable")] - values[(2023, "Accounts Payable")]
    results.update({
        "ar_revenue_gap": results["ar_growth"] - results["revenue_growth"],
        "free_cash_flow": values[(2024, "Operating Cash Flow")] - values[(2024, "Capital Expenditures")],
        "net_working_capital_cash_effect": -ar_change - inventory_change + ap_change,
        "capex_to_da": values[(2024, "Capital Expenditures")] / values[(2024, "Depreciation & Amortization")],
        "capex_to_revenue": values[(2024, "Capital Expenditures")] / values[(2024, "Revenue")],
        "sbc_to_net_income": values[(2024, "Stock-Based Compensation")] / abs(values[(2024, "Net Income")]),
        "dta_to_net_income": values[(2024, "Deferred Tax Assets")] / abs(values[(2024, "Net Income")]),
        "dta_growth": calculate_growth(values[(2024, "Deferred Tax Assets")], values[(2023, "Deferred Tax Assets")]),
        "dtl_growth": calculate_growth(values[(2024, "Deferred Tax Liabilities")], values[(2023, "Deferred Tax Liabilities")]),
    })
    return values, results


def test_amazon_calculations_rules_flags_and_severities() -> None:
    values, actual = calculated_amazon_results()
    expected = EXPECTED_ANALYSIS_2024
    numeric_fields = [
        "revenue_growth", "net_income_growth", "ocf_growth", "ar_growth",
        "inventory_growth", "ap_growth", "da_growth", "capex_growth",
        "sbc_growth", "shares_growth", "ar_revenue_gap", "free_cash_flow",
        "net_working_capital_cash_effect", "capex_to_da", "capex_to_revenue",
        "sbc_to_net_income", "dta_to_net_income", "dta_growth", "dtl_growth",
    ]
    for field in numeric_fields:
        require_close(actual[field], expected[field], field)

    ar_flag = bool(actual["ar_revenue_gap"] >= AR_GAP_THRESHOLD)
    ni_ocf_flag = bool(actual["net_income_growth"] > 0 and actual["ocf_growth"] < 0)
    combined_flag, _, accrual_severity, _ = classify_accrual_signal(ar_flag, ni_ocf_flag)
    assert ar_flag is expected["ar_flag"]
    assert ni_ocf_flag is expected["ni_ocf_flag"]
    assert combined_flag is expected["combined_accrual_flag"]
    assert accrual_severity == expected["accrual_severity"]

    # Inventory/AP/CapEx/combined SBC rules are fixed module-level DataFrame
    # pipelines. Apply their existing rule contracts to the verified results;
    # no production refactor or alternate threshold is introduced.
    inventory_flag = bool(actual["inventory_growth"] - actual["revenue_growth"] >= 0.10)
    assert inventory_flag is expected["inventory_flag"]
    ap_classification = (
        "Normal supplier financing pattern"
        if actual["ap_growth"] > actual["revenue_growth"] and actual["ocf_growth"] >= 0
        else "No AP concern triggered"
    )
    assert ap_classification == expected["ap_classification"]
    wc_classification = classify_cash_effect(actual["net_working_capital_cash_effect"])
    assert wc_classification == "Cash Benefit"
    assert (wc_classification == "Cash Use") is expected["working_capital_cash_use"]

    capex_flag = bool(actual["capex_to_da"] >= capex_threshold)
    assert capex_flag is expected["capex_flag"]
    assert ("Needs investigation" if capex_flag else "No investigation triggered") == expected["capex_status"]

    dta_risk = classify_dta_risk(
        actual["dta_to_net_income"], actual["net_income_growth"], values[(2024, "Net Income")]
    )
    movement_flag = bool(
        abs(actual["dta_growth"]) >= MOVEMENT_THRESHOLD
        or abs(actual["dtl_growth"]) >= MOVEMENT_THRESHOLD
    )
    _, tax_severity = classify_overall(dta_risk, movement_flag)
    assert dta_risk is expected["dta_risk_flag"]
    assert movement_flag is expected["deferred_tax_movement_flag"]
    assert tax_severity == expected["tax_severity"]

    dilution = classify_year(pd.Series({
        "SBC Growth": actual["sbc_growth"],
        "Shares Outstanding Growth": actual["shares_growth"],
    }))
    large_sbc_flag = bool(actual["sbc_to_net_income"] >= LARGE_SBC_THRESHOLD)
    assert large_sbc_flag is expected["large_sbc_flag"]
    assert bool(dilution.iloc[2]) is expected["dilution_flag"]

    # Gross share issuance and repurchase amounts were not independently
    # verified for this benchmark. The change in shares outstanding is not a
    # substitute for those inputs, so Amazon buyback-offset classification is
    # intentionally outside this test's independently supported coverage.


def amazon_structured_input() -> dict:
    _, a = calculated_amazon_results()
    e = EXPECTED_ANALYSIS_2024
    gate = AnalysisValidationGateResult(
        decision=AnalysisDecision.CONTINUE, can_analyze=True,
        requested_fiscal_years=(2023, 2024), blocking_issues=(),
        metric_year_results=(), blocking_issue_count=0,
    )
    return build_ai_analysis_input(
        company_name="Amazon.com, Inc.", ticker="AMZN", validation_gate=gate,
        financial_summary_df=pd.DataFrame([{
            "Fiscal Year": 2024, "Revenue": 637_959, "Net Income": 59_248,
            "Operating Cash Flow": 115_877, "CapEx": 82_999, "D&A": 52_795,
            "CapEx / Revenue": a["capex_to_revenue"], "CapEx / D&A": a["capex_to_da"],
            "CapEx Review Flag": e["capex_flag"], "CapEx Classification": e["capex_status"],
        }]),
        cash_conversion_df=pd.DataFrame([{
            "Fiscal Year": 2024, "Revenue Growth": a["revenue_growth"], "AR Growth": a["ar_growth"],
            "AR Revenue Gap": a["ar_revenue_gap"], "AR Flag": e["ar_flag"],
            "NI OCF Flag": e["ni_ocf_flag"], "Combined Accrual Flag": e["combined_accrual_flag"],
            "Severity": e["accrual_severity"],
        }]),
        working_capital_df=pd.DataFrame([{
            "Fiscal Year": 2024, "Revenue Growth": a["revenue_growth"],
            "Inventory Growth": a["inventory_growth"], "AP Growth": a["ap_growth"],
            "OCF Growth": a["ocf_growth"], "Net Working Capital Cash Effect": a["net_working_capital_cash_effect"],
            "Inventory Flag": e["inventory_flag"], "AP Classification": e["ap_classification"],
            "Working Capital Cash Use": e["working_capital_cash_use"],
            "Overall Severity": e["working_capital_severity"],
            "Explanation": "Fixed Amazon FY2024 working-capital results.",
        }]),
        taxes_df=pd.DataFrame([{
            "Fiscal Year": 2024, "Deferred Tax Assets": 55_045, "Deferred Tax Liabilities": 39_080,
            "DTA / Net Income": a["dta_to_net_income"], "DTA Growth": a["dta_growth"],
            "DTL Growth": a["dtl_growth"], "DTA Risk Flag": e["dta_risk_flag"],
            "Deferred Tax Movement Flag": e["deferred_tax_movement_flag"],
            "Overall Tax Severity": e["tax_severity"], "Explanation": "Fixed Amazon FY2024 tax results.",
        }]),
        sbc_df=pd.DataFrame([{
            "Fiscal Year": 2024, "SBC": 22_011, "SBC / Net Income": a["sbc_to_net_income"],
            "Shares Outstanding": 10_593, "Shares Outstanding Growth": a["shares_growth"],
            "Large SBC Flag": e["large_sbc_flag"], "Dilution Flag": e["dilution_flag"],
            "Overall SBC Severity": e["sbc_severity"], "Explanation": "Fixed Amazon FY2024 SBC results.",
        }]),
        normalized_earnings_df=pd.DataFrame(),
        red_flags_df=pd.DataFrame([{
            "Fiscal Year": 2024, "Metric": "CapEx vs D&A", "Result": "Review",
            "Severity": e["capex_severity"], "Explanation": "CapEx / D&A exceeds the existing threshold.",
        }]),
        detailed_severity_df=pd.DataFrame([{"Fiscal Year": 2024, "Area": "CapEx", "Severity": e["capex_severity"]}]),
        fiscal_year_severity_df=pd.DataFrame([{"Fiscal Year": 2024, "High-Level Severity": e["overall_severity"]}]),
        overall_severity_df=pd.DataFrame([{"Benchmark Severity": e["overall_severity"]}]),
    )


def test_amazon_task_90_input_and_interpretations() -> None:
    structured = amazon_structured_input()
    assert structured["company"] == {
        "name": "Amazon.com, Inc.", "ticker": "AMZN", "fiscal_years": [2023, 2024]
    }
    json.dumps(structured)
    outputs = {
        "accrual": interpret_accrual_quality(structured),
        "working_capital": interpret_working_capital(structured),
        "capex": interpret_capex(structured),
        "tax": interpret_deferred_taxes(structured),
        "sbc": interpret_sbc(structured),
    }
    expected_severities = {
        "accrual": "None", "working_capital": "Low", "capex": "Medium",
        "tax": "None", "sbc": "Medium",
    }
    for area, output in outputs.items():
        actual_severity = output["yearly_assessments"][0]["existing_severity"]
        assert actual_severity == expected_severities[area], (
            f"Amazon {area} severity: expected {expected_severities[area]!r}, actual {actual_severity!r}"
        )
    assert outputs["capex"]["yearly_assessments"][0]["supporting_evidence"]["capex_flag"] is True
    assert outputs["sbc"]["yearly_assessments"][0]["supporting_evidence"]["dilution_flag"] is True
    assert outputs["working_capital"]["yearly_assessments"][0]["supporting_evidence"]["ap_classification"] == "Normal supplier financing pattern"


if __name__ == "__main__":
    test_amazon_identification_extraction_and_provenance()
    test_amazon_calculations_rules_flags_and_severities()
    test_amazon_task_90_input_and_interpretations()
    print("Task 108 third company tests passed")
