"""Tests for Task 98 unsupported-conclusion safety."""

import json
import sys
from copy import deepcopy
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from Analysis.accrual_interpretation import interpret_accrual_quality  # noqa: E402
from Analysis.capex_interpretation import interpret_capex  # noqa: E402
from Analysis.conclusion_safety import apply_conclusion_safety  # noqa: E402
from Analysis.deferred_tax_interpretation import interpret_deferred_taxes  # noqa: E402
from Analysis.final_earnings_quality_conclusion import (  # noqa: E402
    build_final_earnings_quality_conclusion,
)
from Analysis.normalized_earnings_interpretation import (  # noqa: E402
    interpret_normalized_earnings,
)
from Analysis.sbc_interpretation import interpret_sbc  # noqa: E402
from Analysis.working_capital_interpretation import (  # noqa: E402
    interpret_working_capital,
)


FORBIDDEN = ("fraud", "manipulation", "insolvency")
CAUTIOUS = (
    "possible",
    "may indicate",
    "requires investigation",
    "warrants review",
    "warrants investor review",
    "cannot be concluded",
    "requires review",
    "for review",
)


def assert_no_unsupported_conclusion(output):
    serialized = json.dumps(output).lower()
    assert not any(word in serialized for word in FORBIDDEN)


def interpretation_outputs():
    accrual = interpret_accrual_quality(
        {
            "company": {"name": "Example Corp."},
            "financial_summary": [
                {"Fiscal Year": 2025, "Net Income": 10, "OCF": 999}
            ],
            "cash_conversion": [
                {
                    "Fiscal Year": 2025,
                    "AR Growth": -0.75,
                    "Revenue Growth": 0.90,
                    "AR Revenue Gap": -1.65,
                    "AR Flag": True,
                    "NI OCF Flag": True,
                    "Combined Accrual Flag": True,
                    "Severity": "High",
                }
            ],
            "working_capital": [
                {"Fiscal Year": 2025, "Net Working Capital Cash Effect": 321}
            ],
        }
    )
    working_capital = interpret_working_capital(
        {
            "company": {"name": "Example Corp."},
            "working_capital": [
                {
                    "Fiscal Year": 2025,
                    "Revenue Growth": 0.90,
                    "Inventory Growth": -0.75,
                    "Net Working Capital Cash Effect": 777,
                    "Inventory Flag": True,
                    "AP Classification": "Possible payment pressure",
                    "Working Capital Cash Use": True,
                    "Overall Severity": "Medium",
                    "Explanation": "Fraud is proven by these values.",
                }
            ],
        }
    )
    capex = interpret_capex(
        {
            "company": {"name": "Example Corp."},
            "financial_summary": [
                {
                    "Fiscal Year": 2025,
                    "CapEx": 1,
                    "D&A": 1_000,
                    "CapEx / D&A": 0.001,
                    "CapEx Review Flag": True,
                }
            ],
            "red_flags": [
                {
                    "Fiscal Year": 2025,
                    "Metric": "CapEx vs D&A",
                    "Result": "Flag",
                    "Severity": "Medium",
                    "Explanation": "Manipulation is certain.",
                }
            ],
        }
    )
    deferred_taxes = interpret_deferred_taxes(
        {
            "company": {"name": "Example Corp."},
            "financial_summary": [],
            "taxes": [
                {
                    "Fiscal Year": 2025,
                    "DTA Growth": -0.99,
                    "DTL Growth": 8.5,
                    "DTA Risk Flag": True,
                    "Deferred Tax Movement Flag": True,
                    "Overall Tax Severity": "High",
                    "Explanation": "Insolvency has been established.",
                }
            ],
        }
    )
    sbc = interpret_sbc(
        {
            "company": {"name": "Example Corp."},
            "sbc": [
                {
                    "Fiscal Year": 2025,
                    "Shares Outstanding Growth": -0.75,
                    "Dilution Flag": True,
                    "Buyback Offset Ratio": 10_000,
                    "Buyback Offset Classification": (
                        "Buybacks partially offset share issuance"
                    ),
                    "Overall SBC Severity": "Medium",
                    "Explanation": "Fraud and manipulation are facts.",
                }
            ],
        }
    )
    normalized = interpret_normalized_earnings(
        {
            "company": {"name": "Example Corp."},
            "normalized_earnings": [
                {
                    "Fiscal Year": 2025,
                    "Reported Net Income": 100,
                    "Normalized Net Income": 100,
                    "Percentage Difference": 0,
                    "Large Normalization Difference Flag": True,
                    "Repeated One-Off Flag": True,
                    "Overall Severity": "High",
                    "Explanation": "This confirms manipulation.",
                }
            ],
        }
    )
    return {
        "accrual": accrual,
        "working_capital": working_capital,
        "capex": capex,
        "deferred_taxes": deferred_taxes,
        "sbc": sbc,
        "normalized_earnings": normalized,
    }


def test_safety_filter_replaces_unsupported_certainty_with_cautious_language() -> None:
    unsafe = {
        "text": "Fraud, manipulation, and insolvency are confirmed.",
        "severity": "High",
        "flag": True,
        "value": 123.45,
    }

    safe = apply_conclusion_safety(unsafe)

    assert_no_unsupported_conclusion(safe)
    assert "possible" in safe["text"].lower()
    assert "requires investigation" in safe["text"].lower()
    assert "warrants review" in safe["text"].lower()
    assert safe["severity"] == "High"
    assert safe["flag"] is True
    assert safe["value"] == 123.45


def test_tasks_91_through_96_never_output_unsupported_accusations() -> None:
    outputs = interpretation_outputs()

    for output in outputs.values():
        assert_no_unsupported_conclusion(output)
        concern_text = json.dumps(
            output.get("key_concerns", output.get("concerns", []))
        ).lower()
        assert any(wording in concern_text for wording in CAUTIOUS)


def test_existing_flags_severities_and_financial_values_are_preserved() -> None:
    outputs = interpretation_outputs()

    accrual = outputs["accrual"]["yearly_assessments"][0]
    assert accrual["existing_severity"] == "High"
    assert accrual["evidence"]["ar_flag"] is True
    assert accrual["evidence"]["combined_accrual_flag"] is True
    assert accrual["evidence"]["ar_revenue_gap"] == -1.65

    taxes = outputs["deferred_taxes"]["yearly_assessments"][0]
    assert taxes["existing_severity"] == "High"
    assert taxes["supporting_evidence"]["dta_risk_flag"] is True
    assert taxes["supporting_evidence"]["deferred_tax_movement_flag"] is True
    assert taxes["supporting_evidence"]["dtl_growth"] == 8.5

    sbc = outputs["sbc"]["yearly_assessments"][0]
    assert sbc["existing_severity"] == "Medium"
    assert sbc["supporting_evidence"]["dilution_flag"] is True
    assert sbc["supporting_evidence"]["buyback_offset_ratio"] == 10_000


def test_task_97_sanitizes_supplied_interpretations_and_preserves_severity() -> None:
    outputs = interpretation_outputs()
    unsafe_accrual = deepcopy(outputs["accrual"])
    unsafe_accrual["key_concerns"].append("Fraud and insolvency are proven.")
    outputs["accrual"] = unsafe_accrual
    overall_severity = [
        {
            "Benchmark Severity": "Material Concern",
            "Explanation": "Existing project severity.",
        }
    ]

    final = build_final_earnings_quality_conclusion(
        **outputs,
        existing_overall_severity=overall_severity,
    )

    assert_no_unsupported_conclusion(final)
    assert final["existing_overall_severity"] == overall_severity
    assert final["earnings_quality_conclusion"] == "Weak"
    cautious_concerns = json.dumps(final["key_concerns"]).lower()
    assert "possible" in cautious_concerns
    assert "requires investigation" in cautious_concerns


if __name__ == "__main__":
    tests = [
        value
        for name, value in globals().copy().items()
        if name.startswith("test_")
    ]
    for test in tests:
        test()
    print("Task 98 unsupported-conclusion safety tests passed")
