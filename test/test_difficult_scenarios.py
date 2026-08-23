"""Task 106: exercise difficult contexts through existing interpreters only."""

from __future__ import annotations

import contextlib
import io
import sys
from pathlib import Path

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

with contextlib.redirect_stdout(io.StringIO()):
    from Analysis.buyback_adjustment import classify_net_share_effect
    from Analysis.normalization_red_flags import classify_normalization
    from Analysis.repeated_one_off_detection import build_category_summary
    from Analysis.sbc_vs_dilution import classify_year
    from Analysis.tax_red_flags import (
        MOVEMENT_THRESHOLD,
        calculate_growth,
        classify_dta_risk,
        classify_overall,
    )
    from Calculations.normalized_net_income import calculate_item_adjustment
    from Calculations.working_capital_analysis import classify_cash_effect

from Analysis.capex_interpretation import interpret_capex
from Analysis.deferred_tax_interpretation import interpret_deferred_taxes
from Analysis.normalized_earnings_interpretation import interpret_normalized_earnings
from Analysis.sbc_interpretation import interpret_sbc
from Analysis.working_capital_interpretation import interpret_working_capital


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def assessment(output: dict) -> dict:
    require(len(output["yearly_assessments"]) == 1, "expected one yearly assessment")
    return output["yearly_assessments"][0]


def test_high_inventory_before_product_launch() -> None:
    # Boundary: Analysis.inventory_warning builds its rule directly over the
    # fixed Apple DataFrames and exposes no function accepting synthetic rows.
    # The reusable production cash-effect classifier is exercised here; the
    # existing inventory flag remains an explicit input to the interpreter.
    cash_classification = classify_cash_effect(-409)
    require(cash_classification == "Cash Use", "production cash-use classification changed")
    working_capital_cash_use = cash_classification == "Cash Use"
    source = {
        "company": {"name": "Scenario Company"},
        "working_capital": [{
            "Fiscal Year": 2030,
            "Revenue Growth": 0.03,
            "Inventory Growth": 0.42,
            "AP Growth": 0.04,
            "OCF Growth": -0.02,
            "AR Change": 17,
            "Inventory Change": 411,
            "AP Change": 19,
            "Net Working Capital Cash Effect": -409,
            "Inventory Flag": True,
            "AP Classification": "No AP concern triggered",
            "Working Capital Cash Use": working_capital_cash_use,
            "Overall Severity": "Medium",
            "Explanation": "Inventory increased before a scheduled product launch.",
        }],
    }
    result = assessment(interpret_working_capital(source))
    require(result["existing_severity"] == "Medium", "inventory severity changed")
    require(result["supporting_evidence"]["inventory_flag"] is True, "inventory flag changed")
    require(result["supporting_evidence"]["inventory_growth"] == 0.42, "inventory growth changed")
    require(result["supporting_evidence"]["working_capital_cash_use"] is True, "production cash-use result changed")
    require(result["source_explanation"] == source["working_capital"][0]["Explanation"], "launch context changed")
    require(bool(result["concerns"]), "triggered inventory flag was not interpreted")


def test_high_capex_for_expansion() -> None:
    # Boundary: Analysis.capex_rule is a module-level pipeline over the fixed
    # CapEx DataFrame. It has no reusable classifier for a synthetic ratio, so
    # this scenario retains its existing interpreter-level flag coverage.
    source = {
        "company": {"name": "Scenario Company"},
        "financial_summary": [{
            "Fiscal Year": 2030,
            "CapEx": 900,
            "CapEx Growth": 0.55,
            "CapEx / Revenue": 0.18,
            "CapEx / D&A": 2.4,
            "Revenue": 5_000,
            "D&A": 375,
            "CapEx Review Flag": True,
            "CapEx Classification": "Needs investigation",
        }],
        "red_flags": [{
            "Fiscal Year": 2030,
            "Metric": "CapEx vs D&A",
            "Result": "Review",
            "Severity": "Medium",
            "Explanation": "Capital spending supports a disclosed capacity expansion.",
        }],
    }
    result = assessment(interpret_capex(source))
    require(result["existing_severity"] == "Medium", "CapEx severity changed")
    require(result["supporting_evidence"]["capex_flag"] is True, "CapEx flag changed")
    require(result["supporting_evidence"]["capex_to_da"] == 2.4, "CapEx / D&A changed")
    require("requires investigation" in " ".join(result["concerns"]).lower(), "CapEx concern is not cautious")


def test_high_ap_from_supplier_bargaining_power() -> None:
    # Boundary: Analysis.ap_warning calculates and classifies only its fixed
    # project DataFrames; no callable AP classifier accepts synthetic inputs.
    source = {
        "company": {"name": "Scenario Company"},
        "working_capital": [{
            "Fiscal Year": 2030,
            "AP Growth": 0.48,
            "AP Change": 630,
            "Inventory Flag": False,
            "AP Classification": "Normal supplier financing pattern",
            "Working Capital Cash Use": False,
            "Overall Severity": "Low",
            "Explanation": "Management attributes payment terms to supplier bargaining power.",
        }],
    }
    result = assessment(interpret_working_capital(source))
    require(result["existing_severity"] == "Low", "AP severity changed")
    require(result["supporting_evidence"]["ap_classification"] == "Normal supplier financing pattern", "AP classification changed")
    require(result["supporting_evidence"]["ap_growth"] == 0.48, "AP growth changed")
    require("requires review" in " ".join(result["concerns"]).lower(), "AP case is not marked for review")


def test_high_sbc_with_offsetting_buybacks() -> None:
    # The production dilution and net-share-direction functions accept
    # synthetic rows. The combined large-SBC/buyback rule remains a fixed
    # module-level DataFrame pipeline and is therefore kept at interpreter level.
    dilution_result = classify_year(pd.Series({
        "SBC Growth": 0.25,
        "Shares Outstanding Growth": -0.02,
    }))
    production_dilution_flag = bool(dilution_result.iloc[2])
    require(production_dilution_flag is False, "production dilution rule should not trigger")
    net_share_direction = classify_net_share_effect(-40)
    require(net_share_direction == "Net share reduction", "production net-share classification changed")
    source = {
        "company": {"name": "Scenario Company"},
        "sbc": [{
            "Fiscal Year": 2030,
            "SBC": 800,
            "SBC / Net Income": 0.40,
            "Shares Outstanding": 980,
            "Shares Outstanding Growth": -0.02,
            "Large SBC Flag": True,
            "Dilution Flag": production_dilution_flag,
            "Shares Repurchased": 100,
            "Shares Issued": 60,
            "Net Share Effect": -40,
            "Buyback Offset Ratio": 1.6666666667,
            "Buyback Offset Classification": "Buybacks more than offset share issuance",
            "Overall SBC Severity": "Medium",
            "Explanation": "Repurchases offset gross issuance in the supplied results.",
        }],
    }
    result = assessment(interpret_sbc(source))
    require(result["existing_severity"] == "Medium", "SBC severity changed")
    require(result["supporting_evidence"]["large_sbc_flag"] is True, "large-SBC flag changed")
    require(result["supporting_evidence"]["dilution_flag"] is False, "dilution flag changed")
    require(result["supporting_evidence"]["buyback_offset_ratio"] == 1.6666666667, "buyback ratio changed")
    require(net_share_direction == "Net share reduction", "net-share direction was not preserved")
    require(bool(result["positive_signals"]) and bool(result["concerns"]), "offsetting buyback case should preserve mixed signals")


def test_large_dta_with_strong_future_earnings() -> None:
    dta_growth = calculate_growth(2_700, 2_000)
    dtl_growth = calculate_growth(400, 396)
    dta_risk_flag = classify_dta_risk(
        dta_ratio=2.25,
        net_income_growth=0.25,
        net_income=1_200,
    )
    movement_flag = bool(
        abs(dta_growth) >= MOVEMENT_THRESHOLD
        or abs(dtl_growth) >= MOVEMENT_THRESHOLD
    )
    tax_signal, tax_severity = classify_overall(dta_risk_flag, movement_flag)
    require(dta_risk_flag is False, "strong positive earnings should not trigger the production DTA-risk rule")
    require(movement_flag is True, "35% DTA growth should trigger the production movement rule")
    require(tax_severity == "Medium", f"expected production tax severity 'Medium', actual {tax_severity!r}")
    source = {
        "company": {"name": "Scenario Company"},
        "financial_summary": [{"Fiscal Year": 2030, "Net Income": 1_200}],
        "taxes": [{
            "Fiscal Year": 2030,
            "Tax Expense": 210,
            "Deferred Tax Assets": 2_700,
            "Deferred Tax Liabilities": 400,
            "DTA / Net Income": 2.25,
            "DTA Growth": dta_growth,
            "DTL Growth": dtl_growth,
            "Deferred Tax Movement Flag": movement_flag,
            "DTA Risk Flag": dta_risk_flag,
            "Overall Tax Severity": tax_severity,
            "Explanation": "Forecasts supplied by management show strong future earnings.",
        }],
    }
    result = assessment(interpret_deferred_taxes(source))
    require(result["existing_severity"] == "Medium", "tax severity changed")
    require(result["supporting_evidence"]["dta_risk_flag"] is False, "DTA risk flag changed")
    require(result["supporting_evidence"]["deferred_tax_movement_flag"] is True, "tax movement flag changed")
    require(result["supporting_evidence"]["deferred_tax_assets"] == 2_700, "DTA value changed")
    require(bool(result["concerns"]), "triggered tax movement was not interpreted")
    require(tax_signal == "Tax items require investigation", "production tax signal changed")


def test_repeated_one_time_charges() -> None:
    repeated_items = pd.DataFrame([
        {"Fiscal Year": 2029, "Category": "Restructuring", "Availability": "Available"},
        {"Fiscal Year": 2030, "Category": "Restructuring", "Availability": "Available"},
    ])
    repetition = build_category_summary(
        repeated_items, ["Restructuring"]
    ).iloc[0]
    repeated_flag = bool(repetition["Repeated One-Off"])
    require(repeated_flag is True, "production repeated-one-off rule should trigger")
    require(repetition["Years Appearing"] == 2, "production repetition count changed")

    adjustment, adjustment_status = calculate_item_adjustment(pd.Series({
        "Manual Classification": "Non-recurring",
        "Tax Basis": "After-tax",
        "Direction": "Charge",
        "Value": 180,
    }))
    require(adjustment == 180, f"expected production adjustment 180, actual {adjustment!r}")
    require(adjustment_status == "Adjusted", f"expected adjustment status 'Adjusted', actual {adjustment_status!r}")
    normalization_signal, normalization_severity, _ = classify_normalization(
        repeated_flag, True
    )
    require(normalization_severity == "High", "production normalization severity changed")
    source = {
        "company": {"name": "Scenario Company"},
        "normalized_earnings": [{
            "Fiscal Year": 2030,
            "Reported Net Income": 1_000,
            "Normalization Adjustment": adjustment,
            "Normalized Net Income": 1_180,
            "Normalization Difference": 180,
            "Normalization Difference %": 0.18,
            "One-Off Category": "Restructuring",
            "One-Off Description": "Third annual restructuring charge.",
            "Classification": "Operating expense adjustment",
            "Review Status": "Review required",
            "Large Normalization Difference Flag": True,
            "Repeated One-Off Flag": repeated_flag,
            "Normalization Signal": normalization_signal,
            "Severity": normalization_severity,
            "Explanation": "The existing repeated-one-off rule triggered.",
        }],
    }
    result = assessment(interpret_normalized_earnings(source))
    require(result["existing_severity"] == "High", "normalization severity changed")
    require(result["supporting_evidence"]["repeated_one_off_flag"] is True, "repeated-one-off flag changed")
    require(result["one_off_classification"] == "Operating expense adjustment", "one-off classification changed")
    require(result["supporting_evidence"]["normalization_difference"] == 180, "normalization difference changed")
    require("requires review" in " ".join(result["concerns"]).lower(), "repeated charge lacks cautious review language")


if __name__ == "__main__":
    test_high_inventory_before_product_launch()
    test_high_capex_for_expansion()
    test_high_ap_from_supplier_bargaining_power()
    test_high_sbc_with_offsetting_buybacks()
    test_large_dta_with_strong_future_earnings()
    test_repeated_one_time_charges()
    print("Task 106 difficult scenario tests passed")
