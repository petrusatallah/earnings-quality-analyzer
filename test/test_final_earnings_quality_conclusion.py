"""Tests for the revised Task 97 final earnings-quality conclusion."""

import json
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from Analysis.final_earnings_quality_conclusion import (  # noqa: E402
    build_final_earnings_quality_conclusion,
)


VALID_LABELS = {"Strong", "Generally Healthy", "Needs Investigation", "Weak"}
AREA_NAMES = {
    "accrual": "Accrual Quality",
    "working_capital": "Working Capital",
    "capex": "CapEx",
    "deferred_taxes": "Deferred Taxes",
    "sbc": "Stock-Based Compensation",
    "normalized_earnings": "Normalized Earnings",
}


def interpretation(area, severity="None", positives=None, concerns=None):
    positive_field = (
        "key_positive_signals" if area == "Accrual Quality" else "positive_signals"
    )
    concern_field = "key_concerns" if area == "Accrual Quality" else "concerns"
    return {
        "area": area,
        "overall_assessment": f"Existing {area} conclusion.",
        "fiscal_years_discussed": [2024, 2025],
        "existing_severities": [
            {"fiscal_year": 2025, "severity": severity}
        ],
        positive_field: list(positives or []),
        concern_field: list(concerns or []),
        "explanation": f"Existing {area} explanation.",
        "yearly_assessments": [
            {
                "fiscal_year": 2025,
                "supporting_evidence": {"unchanged_value": 123.45},
            }
        ],
    }


def interpretations(*, positive_everywhere=True):
    supplied = {
        key: interpretation(
            area,
            positives=[f"{area} positive"] if positive_everywhere else [],
        )
        for key, area in AREA_NAMES.items()
    }
    supplied["existing_overall_severity"] = [
        {
            "Benchmark Severity": "Material Concern",
            "Explanation": "Existing Task 90 severity explanation.",
        }
    ]
    return supplied


def assert_valid_conclusion(result, expected_label):
    assert result["earnings_quality_conclusion"] == expected_label
    assert result["earnings_quality_conclusion"] in VALID_LABELS
    assert isinstance(result["explanation"], str)
    assert result["explanation"].strip()


def test_strong_conclusion_is_covered_and_has_explanation() -> None:
    result = build_final_earnings_quality_conclusion(**interpretations())

    assert_valid_conclusion(result, "Strong")
    assert result["key_concerns"] == []


def test_generally_healthy_conclusion_is_covered_and_has_explanation() -> None:
    supplied = interpretations()
    supplied["capex"]["positive_signals"] = []

    result = build_final_earnings_quality_conclusion(**supplied)

    assert_valid_conclusion(result, "Generally Healthy")
    assert result["key_concerns"] == []


def test_needs_investigation_conclusion_is_covered_and_has_explanation() -> None:
    supplied = interpretations()
    supplied["working_capital"]["concerns"] = ["Working-capital concern"]
    supplied["working_capital"]["existing_severities"] = [
        {"fiscal_year": 2025, "severity": "Medium"}
    ]

    result = build_final_earnings_quality_conclusion(**supplied)

    assert_valid_conclusion(result, "Needs Investigation")
    assert {"area": "Working Capital", "concern": "Working-capital concern"} in result[
        "key_concerns"
    ]


def test_weak_conclusion_is_covered_and_has_explanation() -> None:
    supplied = interpretations()
    supplied["accrual"]["key_concerns"] = ["Existing severe accrual concern"]
    supplied["accrual"]["existing_severities"] = [
        {"fiscal_year": 2025, "severity": "High"}
    ]

    result = build_final_earnings_quality_conclusion(**supplied)

    assert_valid_conclusion(result, "Weak")
    assert result["supporting_interpretation_by_category"]["accrual"][
        "interpretation"
    ]["existing_severities"] == supplied["accrual"]["existing_severities"]


def test_required_output_fields_are_present() -> None:
    result = build_final_earnings_quality_conclusion(**interpretations())

    assert {
        "earnings_quality_conclusion",
        "explanation",
        "positive_signals",
        "key_concerns",
        "areas_needing_investigation",
        "fiscal_years_covered",
        "existing_overall_severity",
    }.issubset(result)
    assert result["fiscal_years_covered"] == [2024, 2025]


def test_all_six_areas_and_existing_severities_are_preserved() -> None:
    supplied = interpretations()
    result = build_final_earnings_quality_conclusion(**supplied)

    supporting = result["supporting_interpretation_by_category"]
    assert set(supporting) == set(AREA_NAMES)
    for key in AREA_NAMES:
        assert supporting[key]["interpretation"] == supplied[key]
        assert supporting[key]["interpretation"]["existing_severities"] == supplied[
            key
        ]["existing_severities"]


def test_task_90_existing_overall_severity_is_preserved_exactly() -> None:
    supplied = interpretations()
    task_90_severity = {
        "records": [
            {
                "Benchmark Severity": "Material Concern",
                "Explanation": "Preserve this exact Task 90 value.",
            }
        ],
        "source": "Task 90",
    }
    supplied["existing_overall_severity"] = task_90_severity

    result = build_final_earnings_quality_conclusion(**supplied)

    assert result["existing_overall_severity"] == task_90_severity
    assert result["existing_overall_severity"] is not task_90_severity


def test_positive_signals_and_concerns_are_combined_without_ranking() -> None:
    supplied = interpretations()
    supplied["deferred_taxes"]["concerns"] = ["Existing tax concern"]

    result = build_final_earnings_quality_conclusion(**supplied)

    assert {"area": "Deferred Taxes", "concern": "Existing tax concern"} in result[
        "key_concerns"
    ]
    assert {
        "area": "Stock-Based Compensation",
        "signal": "Stock-Based Compensation positive",
    } in result["positive_signals"]
    assert [item["area"] for item in result["areas_needing_investigation"]] == [
        "Deferred Taxes"
    ]


def test_missing_area_stays_unavailable_and_requires_investigation() -> None:
    supplied = interpretations()
    supplied["capex"] = None

    result = build_final_earnings_quality_conclusion(**supplied)
    capex = result["supporting_interpretation_by_category"]["capex"]

    assert_valid_conclusion(result, "Needs Investigation")
    assert capex["availability"] == "unavailable"
    assert capex["interpretation"] is None
    assert result["existing_overall_severity"] == supplied["existing_overall_severity"]
    assert "not filled with invented evidence" in result["explanation"]


def test_financial_evidence_is_copied_without_calculation_or_score() -> None:
    supplied = interpretations()
    evidence = {
        "reported_value": 10,
        "cash_value": 999,
        "deliberately_inconsistent_ratio": -123.456,
    }
    supplied["accrual"]["yearly_assessments"][0]["supporting_evidence"] = evidence

    result = build_final_earnings_quality_conclusion(**supplied)
    preserved = result["supporting_interpretation_by_category"]["accrual"][
        "interpretation"
    ]["yearly_assessments"][0]["supporting_evidence"]

    assert preserved == evidence
    assert '"score":' not in json.dumps(result).lower()


def test_no_buy_or_sell_recommendation_is_produced() -> None:
    result = build_final_earnings_quality_conclusion(**interpretations())
    generated = " ".join(
        [result["earnings_quality_conclusion"], result["explanation"]]
        + [item["signal"] for item in result["positive_signals"]]
        + [item["concern"] for item in result["key_concerns"]]
    ).lower()

    assert "buy recommendation" not in generated
    assert "sell recommendation" not in generated
    assert "recommend buying" not in generated
    assert "recommend selling" not in generated


if __name__ == "__main__":
    tests = [
        value
        for name, value in globals().copy().items()
        if name.startswith("test_")
    ]
    for test in tests:
        test()
    print("Revised Task 97 final earnings-quality conclusion tests passed")
