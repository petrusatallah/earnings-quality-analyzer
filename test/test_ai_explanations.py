"""Task 105: verify the production AI-input and interpretation pipeline."""

from __future__ import annotations

import contextlib
import copy
import io
import json
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

with contextlib.redirect_stdout(io.StringIO()):
    from Analysis.accrual_red_flags import accrual_red_flags_df
    from Analysis.master_analysis_table import analyst_summary_df
    from Analysis.normalization_red_flags import normalization_red_flags_df
    from Analysis.red_flag_table import red_flag_table_df
    from Analysis.sbc_red_flags import sbc_red_flags_df
    from Analysis.severity_system import (
        benchmark_severity_df,
        detailed_severity_table_df,
        fiscal_year_severity_summary_df,
    )
    from Analysis.tax_red_flags import tax_red_flags_df
    from Analysis.working_capital_red_flags import working_capital_red_flags_df

from Analysis.accrual_interpretation import interpret_accrual_quality
from Analysis.ai_input_preparation import build_ai_analysis_input
from Analysis.capex_interpretation import interpret_capex
from Analysis.deferred_tax_interpretation import interpret_deferred_taxes
from Analysis.final_earnings_quality_conclusion import (
    build_final_earnings_quality_conclusion,
)
from Analysis.normalized_earnings_interpretation import interpret_normalized_earnings
from Analysis.sbc_interpretation import interpret_sbc
from Analysis.working_capital_interpretation import interpret_working_capital
from Data.analysis_validation_gate import AnalysisDecision, AnalysisValidationGateResult


FORBIDDEN_FACT_CLAIMS = ("fraud", "manipulation", "insolvency")
BUY_SELL_RECOMMENDATIONS = (
    "buy recommendation",
    "sell recommendation",
    "recommend buying",
    "recommend selling",
    "buy/sell recommendation",
)
CAUTIOUS_LANGUAGE = (
    "possible",
    "may indicate",
    "requires investigation",
    "warrants review",
    "warrants investor review",
    "requires review",
    "for review",
    "further investigation",
)


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def build_production_input() -> dict:
    gate = AnalysisValidationGateResult(
        decision=AnalysisDecision.CONTINUE,
        can_analyze=True,
        requested_fiscal_years=(2022, 2023, 2024, 2025),
        blocking_issues=(),
        metric_year_results=(),
        blocking_issue_count=0,
    )
    return build_ai_analysis_input(
        company_name="Apple Inc.",
        ticker="AAPL",
        validation_gate=gate,
        financial_summary_df=analyst_summary_df,
        cash_conversion_df=accrual_red_flags_df,
        working_capital_df=working_capital_red_flags_df,
        taxes_df=tax_red_flags_df,
        sbc_df=sbc_red_flags_df,
        normalized_earnings_df=normalization_red_flags_df,
        red_flags_df=red_flag_table_df,
        detailed_severity_df=detailed_severity_table_df,
        fiscal_year_severity_df=fiscal_year_severity_summary_df,
        overall_severity_df=benchmark_severity_df,
    )


def build_outputs(structured_input: dict) -> dict:
    interpretations = {
        "accrual": interpret_accrual_quality(structured_input),
        "working_capital": interpret_working_capital(structured_input),
        "capex": interpret_capex(structured_input),
        "deferred_taxes": interpret_deferred_taxes(structured_input),
        "sbc": interpret_sbc(structured_input),
        "normalized_earnings": interpret_normalized_earnings(structured_input),
    }
    final = build_final_earnings_quality_conclusion(
        **interpretations,
        existing_overall_severity=structured_input["overall_assessment"][
            "overall_severity"
        ],
    )
    return {**interpretations, "final": final}


def test_structured_input_drives_all_interpretations_without_mutation() -> None:
    structured_input = build_production_input()
    original = copy.deepcopy(structured_input)
    outputs = build_outputs(structured_input)

    require(structured_input == original, "interpretation pipeline changed Task 90 input")
    require(
        structured_input["company"]["fiscal_years"] == [2022, 2023, 2024, 2025],
        "Task 90 fiscal years were not preserved",
    )
    expected_areas = {
        "accrual": "Accrual Quality",
        "working_capital": "Working Capital",
        "capex": "CapEx",
        "deferred_taxes": "Deferred Taxes",
        "sbc": "Stock-Based Compensation",
        "normalized_earnings": "Normalized Earnings",
    }
    for key, area in expected_areas.items():
        require(
            outputs[key]["area"] == area,
            f"{key} area: expected {area!r}, actual {outputs[key]['area']!r}",
        )
        require(
            bool(outputs[key]["explanation"].strip()),
            f"{area}: expected a non-empty explanation",
        )


def test_outputs_are_cautious_and_not_recommendations() -> None:
    outputs = build_outputs(build_production_input())
    serialized = json.dumps(outputs).lower()

    for term in FORBIDDEN_FACT_CLAIMS:
        require(term not in serialized, f"unsupported factual claim found: {term!r}")
    for phrase in BUY_SELL_RECOMMENDATIONS:
        require(phrase not in serialized, f"buy/sell recommendation found: {phrase!r}")

    concern_text = json.dumps(outputs["final"]["key_concerns"]).lower()
    require(bool(outputs["final"]["key_concerns"]), "expected benchmark concerns")
    require(
        any(phrase in concern_text for phrase in CAUTIOUS_LANGUAGE),
        f"concerning output lacks cautious language: {concern_text!r}",
    )


def test_final_output_preserves_existing_overall_severity() -> None:
    structured_input = build_production_input()
    outputs = build_outputs(structured_input)
    expected = structured_input["overall_assessment"]["overall_severity"]
    actual = outputs["final"]["existing_overall_severity"]

    require(
        actual == expected,
        f"existing overall severity: expected {expected!r}, actual {actual!r}",
    )
    require(
        outputs["final"]["earnings_quality_conclusion"]
        in {"Strong", "Generally Healthy", "Needs Investigation", "Weak"},
        "final conclusion used an unsupported label",
    )
    require(
        bool(outputs["final"]["explanation"].strip()),
        "final conclusion explanation is required",
    )


def test_changed_supplied_flag_changes_interpretation_without_recalculation() -> None:
    base = {
        "company": {"name": "Grounding Test", "fiscal_years": [2030]},
        "financial_summary": [
            {"Fiscal Year": 2030, "Net Income": 17, "Operating Cash Flow": 999}
        ],
        "cash_conversion": [
            {
                "Fiscal Year": 2030,
                "Revenue Growth": 0.91,
                "AR Growth": -0.73,
                "AR Flag": False,
                "NI OCF Flag": False,
                "Combined Accrual Flag": False,
                "Severity": "Existing Custom Severity",
            }
        ],
        "working_capital": [
            {"Fiscal Year": 2030, "Net Working Capital Cash Effect": -444}
        ],
    }
    positive = interpret_accrual_quality(base)
    changed_input = copy.deepcopy(base)
    changed_input["cash_conversion"][0]["AR Flag"] = True
    changed_input["cash_conversion"][0]["Combined Accrual Flag"] = True
    concerning = interpret_accrual_quality(changed_input)

    positive_year = positive["yearly_assessments"][0]
    concerning_year = concerning["yearly_assessments"][0]
    require(not positive_year["concerns"], f"false flags invented concerns: {positive_year['concerns']!r}")
    require(
        any("combined accrual warning" in item.lower() for item in concerning_year["concerns"]),
        f"changed combined flag did not affect interpretation: {concerning_year['concerns']!r}",
    )
    require(
        concerning_year["existing_severity"] == "Existing Custom Severity",
        f"severity was reclassified: expected 'Existing Custom Severity', actual {concerning_year['existing_severity']!r}",
    )
    for field, expected in {
        "net_income": 17,
        "operating_cash_flow": 999,
        "revenue_growth": 0.91,
        "ar_growth": -0.73,
        "ar_revenue_gap": None,
        "net_working_capital_cash_effect": -444,
    }.items():
        require(
            concerning_year["evidence"][field] == expected,
            f"grounded evidence {field}: expected {expected!r}, actual {concerning_year['evidence'][field]!r}",
        )
    require(
        "ar_revenue_gap" in concerning_year["unavailable_evidence"],
        "missing AR/revenue gap was calculated or not marked unavailable",
    )
    require(
        set(concerning_year["evidence"]) == {
            "net_income",
            "operating_cash_flow",
            "revenue_growth",
            "ar_growth",
            "ar_revenue_gap",
            "net_working_capital_cash_effect",
            "ar_flag",
            "ni_ocf_flag",
            "combined_accrual_flag",
        },
        f"unsupported evidence was invented: {set(concerning_year['evidence'])!r}",
    )


def test_area_flags_and_severities_are_preserved_from_task_90() -> None:
    structured = build_production_input()
    outputs = build_outputs(structured)

    def by_year(records):
        return {record["Fiscal Year"]: record for record in records}

    checks = {
        "accrual": (
            by_year(structured["cash_conversion"]),
            "evidence",
            {"AR Flag": "ar_flag", "NI OCF Flag": "ni_ocf_flag", "Combined Accrual Flag": "combined_accrual_flag"},
            ("Accrual Severity", "Severity"),
        ),
        "working_capital": (
            by_year(structured["working_capital"]),
            "supporting_evidence",
            {"Inventory Flag": "inventory_flag", "AP Classification": "ap_classification", "Working Capital Cash Use": "working_capital_cash_use"},
            ("Overall Severity", "Working Capital Severity"),
        ),
        "deferred_taxes": (
            by_year(structured["taxes"]),
            "supporting_evidence",
            {"DTA Risk Flag": "dta_risk_flag", "Deferred Tax Movement Flag": "deferred_tax_movement_flag"},
            ("Overall Tax Severity", "Tax Severity"),
        ),
        "sbc": (
            by_year(structured["sbc"]),
            "supporting_evidence",
            {"Large SBC Flag": "large_sbc_flag", "Dilution Flag": "dilution_flag", "Buyback Offset Classification": "buyback_offset_classification"},
            ("Overall SBC Severity", "SBC Severity"),
        ),
        "normalized_earnings": (
            by_year(structured["normalized_earnings"]),
            "supporting_evidence",
            {"Large Normalization Difference Flag": "large_normalization_difference_flag", "Repeated One-Off Flag": "repeated_one_off_flag", "Classification": "classification"},
            ("Overall Severity", "Normalization Severity", "Severity"),
        ),
    }

    for area, (source_by_year, evidence_field, flag_fields, severity_fields) in checks.items():
        for yearly in outputs[area]["yearly_assessments"]:
            year = yearly["fiscal_year"]
            source = source_by_year[year]
            for source_field, output_field in flag_fields.items():
                if source_field in source:
                    require(
                        yearly[evidence_field][output_field] == source[source_field],
                        f"{area} FY{year} {source_field}: expected {source[source_field]!r}, "
                        f"actual {yearly[evidence_field][output_field]!r}",
                    )
            expected_severity = next(
                (source[field] for field in severity_fields if field in source),
                None,
            )
            require(
                yearly["existing_severity"] == expected_severity,
                f"{area} FY{year} severity: expected {expected_severity!r}, "
                f"actual {yearly['existing_severity']!r}",
            )

    capex_financial = by_year(structured["financial_summary"])
    capex_flags = {
        record["Fiscal Year"]: record
        for record in structured["red_flags"]
        if record.get("Metric") in {"CapEx", "CapEx vs D&A", "Capital Expenditures"}
    }
    for yearly in outputs["capex"]["yearly_assessments"]:
        year = yearly["fiscal_year"]
        source_flag = capex_flags.get(year, {})
        source_financial = capex_financial.get(year, {})
        expected_severity = source_flag.get(
            "Severity", source_financial.get("CapEx Severity", source_financial.get("Severity"))
        )
        require(
            yearly["existing_severity"] == expected_severity,
            f"capex FY{year} severity: expected {expected_severity!r}, actual {yearly['existing_severity']!r}",
        )
        if "CapEx Review Flag" in source_financial:
            require(
                yearly["supporting_evidence"]["capex_flag"]
                == source_financial["CapEx Review Flag"],
                f"capex FY{year} flag was reclassified",
            )


if __name__ == "__main__":
    test_structured_input_drives_all_interpretations_without_mutation()
    test_outputs_are_cautious_and_not_recommendations()
    test_final_output_preserves_existing_overall_severity()
    test_changed_supplied_flag_changes_interpretation_without_recalculation()
    test_area_flags_and_severities_are_preserved_from_task_90()
    print("Task 105 AI explanation tests passed")
