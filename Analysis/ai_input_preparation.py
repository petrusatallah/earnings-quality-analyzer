"""Prepare validated analysis outputs for a future AI interpretation step.

This module is intentionally limited to packaging existing results.  It does
not calculate financial metrics, assign severities, fetch data, or call an AI
service.
"""

from datetime import date, datetime
from enum import Enum
from typing import Any, Dict

import pandas as pd

from Data.analysis_validation_gate import (
    AnalysisDecision,
    AnalysisValidationGateResult,
)


class AnalysisInputBlockedError(RuntimeError):
    """Raised when Task 89 has not approved the analysis inputs."""


def _json_value(value: Any) -> Any:
    """Return a JSON-compatible representation without filling missing data."""

    if value is None:
        return None
    missing = pd.isna(value)
    if not hasattr(missing, "__len__") and bool(missing):
        return None
    if isinstance(value, Enum):
        return _json_value(value.value)
    if isinstance(value, (datetime, date, pd.Timestamp)):
        return value.isoformat()

    # pandas/numpy scalar values retain their value when converted with item().
    if hasattr(value, "item"):
        value = value.item()
    if isinstance(value, dict):
        return {str(key): _json_value(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_value(item) for item in value]
    return value


def _records(frame: pd.DataFrame) -> list[dict[str, Any]]:
    """Copy every existing DataFrame field into JSON-compatible records."""

    if not isinstance(frame, pd.DataFrame):
        raise TypeError("Analysis inputs must be pandas DataFrames.")
    return [
        {str(column): _json_value(value) for column, value in row.items()}
        for row in frame.to_dict(orient="records")
    ]


def build_ai_analysis_input(
    *,
    company_name: Any,
    ticker: Any,
    validation_gate: AnalysisValidationGateResult,
    financial_summary_df: pd.DataFrame,
    cash_conversion_df: pd.DataFrame,
    working_capital_df: pd.DataFrame,
    taxes_df: pd.DataFrame,
    sbc_df: pd.DataFrame,
    normalized_earnings_df: pd.DataFrame,
    red_flags_df: pd.DataFrame,
    detailed_severity_df: pd.DataFrame,
    fiscal_year_severity_df: pd.DataFrame,
    overall_severity_df: pd.DataFrame,
) -> Dict[str, Any]:
    """Package existing analysis tables after a successful Task 89 decision.

    Fiscal years are sourced from ``validation_gate`` so the output cannot
    silently describe a different, unvalidated period.  Missing DataFrame
    values become JSON ``null`` values (Python ``None``); they are never
    estimated or replaced with analytical values.
    """

    if not isinstance(validation_gate, AnalysisValidationGateResult):
        raise TypeError("validation_gate must be a Task 89 gate result.")
    if (
        not validation_gate.can_analyze
        or validation_gate.decision is not AnalysisDecision.CONTINUE
    ):
        raise AnalysisInputBlockedError(
            "Task 89 validation did not approve analysis preparation."
        )

    return {
        "company": {
            "name": _json_value(company_name),
            "ticker": _json_value(ticker),
            "fiscal_years": [
                _json_value(year)
                for year in validation_gate.requested_fiscal_years
            ],
        },
        "financial_summary": _records(financial_summary_df),
        "cash_conversion": _records(cash_conversion_df),
        "working_capital": _records(working_capital_df),
        "taxes": _records(taxes_df),
        "sbc": _records(sbc_df),
        "normalized_earnings": _records(normalized_earnings_df),
        "red_flags": _records(red_flags_df),
        "overall_assessment": {
            "detailed_severities": _records(detailed_severity_df),
            "fiscal_year_severities": _records(fiscal_year_severity_df),
            "overall_severity": _records(overall_severity_df),
        },
    }
