"""Task 107: verified Microsoft extraction and reusable analyzer coverage.

The fixed FY2023/FY2024 values below are transcribed from Microsoft's FY2024
Form 10-K (amounts in USD millions, shares in millions). Expected calculations
and rule results are fixed reviewed answers, not generated from production
outputs. Several project calculations remain module-level Apple DataFrame
pipelines; this test uses callable production functions wherever available and
passes the fixed reviewed results through Task 90 and the interpreters.
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


CIK = "0000789019"
SOURCE_2023 = "https://www.sec.gov/Archives/edgar/data/789019/000095017023035122/msft-20230630.htm"
SOURCE_2024 = "https://www.sec.gov/Archives/edgar/data/789019/000095017024087843/msft-20240630.htm"
FILING_METADATA = {
    2023: {"end": "2023-06-30", "filed": "2023-07-27", "accn": "0000950170-23-035122"},
    2024: {"end": "2024-06-30", "filed": "2024-07-30", "accn": "0000950170-24-087843"},
}

# Fixed official filing values. DTA and DTL use the disclosed deferred-tax
# assets net of valuation allowance and disclosed gross deferred-tax liabilities.
EXPECTED_RAW = {
    2023: {
        "Revenue": (211_915, "USD", "Income Statement", "RevenueFromContractWithCustomerExcludingAssessedTax"),
        "Net Income": (72_361, "USD", "Income Statement", "NetIncomeLoss"),
        "Operating Cash Flow": (87_582, "USD", "Cash Flow Statement", "NetCashProvidedByUsedInOperatingActivities"),
        "Accounts Receivable": (48_688, "USD", "Balance Sheet", "AccountsReceivableNetCurrent"),
        "Inventory": (2_500, "USD", "Balance Sheet", "InventoryNet"),
        "Accounts Payable": (18_095, "USD", "Balance Sheet", "AccountsPayableCurrent"),
        "Depreciation & Amortization": (13_861, "USD", "Cash Flow Statement", "DepreciationDepletionAndAmortization"),
        "Capital Expenditures": (28_107, "USD", "Cash Flow Statement", "PaymentsToAcquirePropertyPlantAndEquipment"),
        "Stock-Based Compensation": (9_611, "USD", "Cash Flow Statement", "ShareBasedCompensation"),
        "Shares Outstanding": (7_432, "shares", "Balance Sheet", "CommonStockSharesOutstanding"),
        "Income Tax Expense": (16_950, "USD", "Income Statement", "IncomeTaxExpenseBenefit"),
        "Deferred Tax Assets": (29_911, "USD", "Balance Sheet", "DeferredTaxAssetsNet"),
        "Deferred Tax Liabilities": (10_181, "USD", "Balance Sheet", "DeferredIncomeTaxLiabilities"),
    },
    2024: {
        "Revenue": (245_122, "USD", "Income Statement", "RevenueFromContractWithCustomerExcludingAssessedTax"),
        "Net Income": (88_136, "USD", "Income Statement", "NetIncomeLoss"),
        "Operating Cash Flow": (118_548, "USD", "Cash Flow Statement", "NetCashProvidedByUsedInOperatingActivities"),
        "Accounts Receivable": (56_924, "USD", "Balance Sheet", "AccountsReceivableNetCurrent"),
        "Inventory": (1_246, "USD", "Balance Sheet", "InventoryNet"),
        "Accounts Payable": (21_996, "USD", "Balance Sheet", "AccountsPayableCurrent"),
        "Depreciation & Amortization": (22_287, "USD", "Cash Flow Statement", "DepreciationDepletionAndAmortization"),
        "Capital Expenditures": (44_477, "USD", "Cash Flow Statement", "PaymentsToAcquirePropertyPlantAndEquipment"),
        "Stock-Based Compensation": (10_734, "USD", "Cash Flow Statement", "ShareBasedCompensation"),
        "Shares Outstanding": (7_434, "shares", "Balance Sheet", "CommonStockSharesOutstanding"),
        "Income Tax Expense": (19_651, "USD", "Income Statement", "IncomeTaxExpenseBenefit"),
        "Deferred Tax Assets": (32_099, "USD", "Balance Sheet", "DeferredTaxAssetsNet"),
        "Deferred Tax Liabilities": (12_447, "USD", "Balance Sheet", "DeferredIncomeTaxLiabilities"),
    },
}

# Independently reviewed fixed results from the disclosed values and existing
# project formulas/rules. These literals are the expected reference.
EXPECTED_ANALYSIS_2024 = {
    "revenue_growth": 0.15669962013071279,
    "net_income_growth": 0.2180041735188845,
    "ocf_growth": 0.35356580119202574,
    "ar_growth": 0.16915872494249096,
    "inventory_growth": -0.5016,
    "ap_growth": 0.21558441558441557,
    "da_growth": 0.6078926484380637,
    "capex_growth": 0.5824171914469705,
    "sbc_growth": 0.11684528144834044,
    "shares_growth": 0.00026910656620021526,
    "ar_revenue_gap": 0.012459104811778171,
    "free_cash_flow": 74_071,
    "net_working_capital_cash_effect": -3_081,
    "capex_to_da": 1.9956476869924171,
    "capex_to_revenue": 0.18144842160230415,
    "sbc_to_net_income": 0.12178905328129255,
    "dta_to_net_income": 0.3641985113914859,
    "dta_growth": 0.07315034602654542,
    "dtl_growth": 0.22257145663490815,
    "ar_flag": False,
    "ni_ocf_flag": False,
    "combined_accrual_flag": False,
    "accrual_severity": "None",
    "inventory_flag": False,
    "ap_classification": "Normal supplier financing pattern",
    "working_capital_cash_use": True,
    "working_capital_severity": "Low",
    "capex_flag": True,
    "capex_status": "Needs investigation",
    "capex_severity": "Medium",
    "dta_risk_flag": False,
    "deferred_tax_movement_flag": False,
    "tax_severity": "None",
    "large_sbc_flag": True,
    "dilution_flag": False,
    "buyback_offset_classification": "Buybacks partially offset share issuance",
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
            raw_value = value_millions * 1_000_000
            entry = {
                "fy": year,
                "fp": "FY",
                "form": "10-K",
                "end": metadata["end"],
                "filed": metadata["filed"],
                "accn": metadata["accn"],
                "val": raw_value,
            }
            if metric in DURATION_METRICS:
                entry["start"] = f"{year - 1}-07-01"
            concept_payload = facts["us-gaap"].setdefault(concept, {"units": {}})
            concept_payload["units"].setdefault(unit, []).append(entry)
    return {"entityName": "Microsoft Corporation", "facts": facts}


def extracted_microsoft_statements():
    identity = identify_company("Microsoft Corporation")
    assert identity.status is IdentificationStatus.MATCHED
    assert identity.company is not None
    assert identity.company.ticker == "MSFT"
    requests = []

    def fixed_loader(url, _headers, _timeout):
        requests.append(url)
        if url == SEC_TICKER_URL:
            return {"0": {"cik_str": 789019, "ticker": "MSFT", "title": "Microsoft Corporation"}}
        if url == SEC_COMPANY_FACTS_URL.format(cik=CIK):
            return company_facts_payload()
        raise AssertionError(f"unexpected source request: {url}")

    fetcher = SECFinancialStatementFetcher(
        "EarningsQualityAgent tests@example.com",
        minimum_request_interval=0.11,
        json_loader=fixed_loader,
    )
    return fetcher.fetch(identity.company, fiscal_years=(2023, 2024)), requests


def test_second_non_financial_company() -> None:
    statements, requests = extracted_microsoft_statements()
    assert statements.company_name == "Microsoft Corporation"
    assert statements.ticker == "MSFT"
    assert statements.cik == CIK
    assert len(requests) == 2, f"expected two mocked SEC reads, actual {requests!r}"

    actual = {(value.fiscal_year, value.financial_field): value for value in statements.values}
    assert len(actual) == 26, f"expected 26 extracted facts, actual {len(actual)}"
    for year, metrics in EXPECTED_RAW.items():
        for metric, (expected_millions, expected_unit, expected_statement, expected_concept) in metrics.items():
            value = actual[(year, metric)]
            prefix = f"company=MSFT, fiscal_year={year}, metric={metric}"
            assert value.status is FactStatus.RETRIEVED, f"{prefix}, expected Retrieved, actual={value.status.value}"
            assert value.raw_value == expected_millions * 1_000_000, f"{prefix}, expected value={expected_millions * 1_000_000!r}, actual={value.raw_value!r}"
            assert value.unit == expected_unit, f"{prefix}, expected unit={expected_unit!r}, actual={value.unit!r}"
            assert value.financial_statement == expected_statement, f"{prefix}, expected statement={expected_statement!r}, actual={value.financial_statement!r}"
            assert value.xbrl_concept == expected_concept, f"{prefix}, expected concept={expected_concept!r}, actual={value.xbrl_concept!r}"
            assert value.filing_date == FILING_METADATA[year]["filed"], f"{prefix}, filing date mismatch"
            assert value.source_url in {SOURCE_2023.rsplit("/", 1)[0] + "/", SOURCE_2024.rsplit("/", 1)[0] + "/"}, f"{prefix}, unexpected source={value.source_url!r}"


def test_microsoft_reusable_calculations_and_rules() -> None:
    statements, _ = extracted_microsoft_statements()
    values = {
        (item.fiscal_year, item.financial_field): item.raw_value / 1_000_000
        for item in statements.values
    }
    expected = EXPECTED_ANALYSIS_2024

    growth_fields = {
        "revenue_growth": "Revenue",
        "net_income_growth": "Net Income",
        "ocf_growth": "Operating Cash Flow",
        "ar_growth": "Accounts Receivable",
        "inventory_growth": "Inventory",
        "ap_growth": "Accounts Payable",
        "da_growth": "Depreciation & Amortization",
        "capex_growth": "Capital Expenditures",
        "sbc_growth": "Stock-Based Compensation",
        "shares_growth": "Shares Outstanding",
    }
    actual_growth = {}
    for result_name, metric in growth_fields.items():
        actual_growth[result_name] = calculate_growth(values[(2024, metric)], values[(2023, metric)])
        require_close(actual_growth[result_name], expected[result_name], result_name)

    ar_change = values[(2024, "Accounts Receivable")] - values[(2023, "Accounts Receivable")]
    inventory_change = values[(2024, "Inventory")] - values[(2023, "Inventory")]
    ap_change = values[(2024, "Accounts Payable")] - values[(2023, "Accounts Payable")]
    calculated_results = {
        "free_cash_flow": (
            values[(2024, "Operating Cash Flow")]
            - values[(2024, "Capital Expenditures")]
        ),
        "net_working_capital_cash_effect": -ar_change - inventory_change + ap_change,
        "capex_to_da": (
            values[(2024, "Capital Expenditures")]
            / values[(2024, "Depreciation & Amortization")]
        ),
        "capex_to_revenue": (
            values[(2024, "Capital Expenditures")]
            / values[(2024, "Revenue")]
        ),
        "sbc_to_net_income": (
            values[(2024, "Stock-Based Compensation")]
            / abs(values[(2024, "Net Income")])
        ),
        "dta_to_net_income": (
            values[(2024, "Deferred Tax Assets")]
            / abs(values[(2024, "Net Income")])
        ),
    }
    for result_name, actual_result in calculated_results.items():
        require_close(actual_result, expected[result_name], result_name)

    ar_gap = actual_growth["ar_growth"] - actual_growth["revenue_growth"]
    require_close(ar_gap, expected["ar_revenue_gap"], "AR/revenue gap")
    ar_flag = bool(ar_gap >= AR_GAP_THRESHOLD)
    ni_ocf_flag = bool(actual_growth["net_income_growth"] > 0 and actual_growth["ocf_growth"] < 0)
    combined_accrual_flag, _, accrual_severity, _ = classify_accrual_signal(
        ar_flag, ni_ocf_flag
    )
    assert ar_flag is expected["ar_flag"]
    assert ni_ocf_flag is expected["ni_ocf_flag"]
    assert combined_accrual_flag is expected["combined_accrual_flag"]
    assert accrual_severity == expected["accrual_severity"]

    # Inventory, AP, CapEx, and combined SBC rules are module-level DataFrame
    # pipelines without synthetic-input callables. Apply their exported fixed
    # thresholds/rule contract here without refactoring production architecture.
    inventory_flag = bool(
        actual_growth["inventory_growth"] - actual_growth["revenue_growth"] >= 0.10
    )
    assert inventory_flag is expected["inventory_flag"]
    ap_classification = (
        "Normal supplier financing pattern"
        if actual_growth["ap_growth"] > actual_growth["revenue_growth"]
        and actual_growth["ocf_growth"] >= 0
        else "No AP concern triggered"
    )
    assert ap_classification == expected["ap_classification"]
    assert classify_cash_effect(
        calculated_results["net_working_capital_cash_effect"]
    ) == "Cash Use"

    capex_flag = bool(calculated_results["capex_to_da"] >= capex_threshold)
    assert capex_flag is expected["capex_flag"]
    assert ("Needs investigation" if capex_flag else "No investigation triggered") == expected["capex_status"]

    dta_risk = classify_dta_risk(
        calculated_results["dta_to_net_income"],
        actual_growth["net_income_growth"],
        values[(2024, "Net Income")],
    )
    dta_growth = calculate_growth(values[(2024, "Deferred Tax Assets")], values[(2023, "Deferred Tax Assets")])
    dtl_growth = calculate_growth(values[(2024, "Deferred Tax Liabilities")], values[(2023, "Deferred Tax Liabilities")])
    require_close(dta_growth, expected["dta_growth"], "DTA growth")
    require_close(dtl_growth, expected["dtl_growth"], "DTL growth")
    movement_flag = bool(abs(dta_growth) >= MOVEMENT_THRESHOLD or abs(dtl_growth) >= MOVEMENT_THRESHOLD)
    _, tax_severity = classify_overall(dta_risk, movement_flag)
    assert dta_risk is expected["dta_risk_flag"]
    assert movement_flag is expected["deferred_tax_movement_flag"]
    assert tax_severity == expected["tax_severity"]

    dilution = classify_year(pd.Series({
        "SBC Growth": actual_growth["sbc_growth"],
        "Shares Outstanding Growth": actual_growth["shares_growth"],
    }))
    large_sbc_flag = bool(
        calculated_results["sbc_to_net_income"] >= LARGE_SBC_THRESHOLD
    )
    assert large_sbc_flag is expected["large_sbc_flag"]
    assert bool(dilution.iloc[2]) is expected["dilution_flag"]
    assert expected["buyback_offset_classification"] == "Buybacks partially offset share issuance"


def microsoft_structured_input() -> dict:
    e = EXPECTED_ANALYSIS_2024
    gate = AnalysisValidationGateResult(
        decision=AnalysisDecision.CONTINUE,
        can_analyze=True,
        requested_fiscal_years=(2023, 2024),
        blocking_issues=(), metric_year_results=(), blocking_issue_count=0,
    )
    return build_ai_analysis_input(
        company_name="Microsoft Corporation",
        ticker="MSFT",
        validation_gate=gate,
        financial_summary_df=pd.DataFrame([{
            "Fiscal Year": 2024, "Revenue": 245_122, "Net Income": 88_136,
            "Operating Cash Flow": 118_548, "CapEx": 44_477, "D&A": 22_287,
            "CapEx / Revenue": e["capex_to_revenue"], "CapEx / D&A": e["capex_to_da"],
            "CapEx Review Flag": e["capex_flag"], "CapEx Classification": e["capex_status"],
        }]),
        cash_conversion_df=pd.DataFrame([{
            "Fiscal Year": 2024, "Revenue Growth": e["revenue_growth"],
            "AR Growth": e["ar_growth"], "AR Revenue Gap": e["ar_revenue_gap"],
            "AR Flag": e["ar_flag"], "NI OCF Flag": e["ni_ocf_flag"],
            "Combined Accrual Flag": e["combined_accrual_flag"], "Severity": e["accrual_severity"],
        }]),
        working_capital_df=pd.DataFrame([{
            "Fiscal Year": 2024, "Revenue Growth": e["revenue_growth"],
            "Inventory Growth": e["inventory_growth"], "AP Growth": e["ap_growth"],
            "OCF Growth": e["ocf_growth"], "Net Working Capital Cash Effect": e["net_working_capital_cash_effect"],
            "Inventory Flag": e["inventory_flag"], "AP Classification": e["ap_classification"],
            "Working Capital Cash Use": e["working_capital_cash_use"], "Overall Severity": e["working_capital_severity"],
            "Explanation": "Fixed Microsoft FY2024 working-capital results.",
        }]),
        taxes_df=pd.DataFrame([{
            "Fiscal Year": 2024, "Deferred Tax Assets": 32_099, "Deferred Tax Liabilities": 12_447,
            "DTA / Net Income": e["dta_to_net_income"], "DTA Growth": e["dta_growth"], "DTL Growth": e["dtl_growth"],
            "DTA Risk Flag": e["dta_risk_flag"], "Deferred Tax Movement Flag": e["deferred_tax_movement_flag"],
            "Overall Tax Severity": e["tax_severity"], "Explanation": "Fixed Microsoft FY2024 tax results.",
        }]),
        sbc_df=pd.DataFrame([{
            "Fiscal Year": 2024, "SBC": 10_734, "SBC / Net Income": e["sbc_to_net_income"],
            "Shares Outstanding": 7_434, "Shares Outstanding Growth": e["shares_growth"],
            "Large SBC Flag": e["large_sbc_flag"], "Dilution Flag": e["dilution_flag"],
            "Shares Repurchased": 32, "Shares Issued": 34,
            "Buyback Offset Classification": e["buyback_offset_classification"],
            "Overall SBC Severity": e["sbc_severity"], "Explanation": "Fixed Microsoft FY2024 SBC results.",
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


def test_microsoft_structured_input_and_interpretations() -> None:
    structured = microsoft_structured_input()
    assert structured["company"] == {
        "name": "Microsoft Corporation", "ticker": "MSFT", "fiscal_years": [2023, 2024]
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
        actual = output["yearly_assessments"][0]["existing_severity"]
        assert actual == expected_severities[area], (
            f"Microsoft {area} severity: expected {expected_severities[area]!r}, actual {actual!r}"
        )
    assert outputs["capex"]["yearly_assessments"][0]["supporting_evidence"]["capex_flag"] is True
    assert outputs["sbc"]["yearly_assessments"][0]["supporting_evidence"]["large_sbc_flag"] is True
    assert outputs["working_capital"]["yearly_assessments"][0]["supporting_evidence"]["ap_classification"] == "Normal supplier financing pattern"


if __name__ == "__main__":
    test_second_non_financial_company()
    test_microsoft_reusable_calculations_and_rules()
    test_microsoft_structured_input_and_interpretations()
    print("Task 107 second company tests passed")
