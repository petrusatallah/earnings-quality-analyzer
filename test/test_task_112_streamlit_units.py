"""Focused tests for Task 112 Streamlit unit-aware financial formatting."""

import ast
from numbers import Real
from pathlib import Path
from typing import Any, Mapping

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[1]
APP_PATH = PROJECT_ROOT / "app.py"


def _load_formatting_namespace() -> dict[str, Any]:
    tree = ast.parse(APP_PATH.read_text(encoding="utf-8"), filename=str(APP_PATH))
    required_names = {
        "_MONETARY_COLUMN_MARKERS",
        "_FINANCIAL_METRIC_UNIT_ALIASES",
        "_USD_AXIS_LABEL_EXPRESSION",
        "_compact_currency_from_millions",
        "_compact_currency",
        "_is_usd_millions",
        "_is_raw_usd",
        "_format_monetary_value",
        "_monetary_value_in_usd",
        "_financial_unit_lookup",
        "_monetary_units_for_columns",
        "_is_monetary_column",
        "_is_missing_display_value",
        "_display_value",
        "_format_kpi",
    }
    body = []
    for statement in tree.body:
        if isinstance(statement, ast.FunctionDef) and statement.name in required_names:
            body.append(statement)
        elif isinstance(statement, ast.Assign) and any(
            isinstance(target, ast.Name) and target.id in required_names
            for target in statement.targets
        ):
            body.append(statement)
    namespace = {
        "Any": Any,
        "Mapping": Mapping,
        "Real": Real,
        "pd": pd,
    }
    exec(compile(ast.Module(body=body, type_ignores=[]), str(APP_PATH), "exec"), namespace)
    return namespace


FORMATTERS = _load_formatting_namespace()


def test_raw_usd_values_display_at_the_correct_compact_magnitude() -> None:
    format_value = FORMATTERS["_format_monetary_value"]

    assert format_value(416_161_000_000, "USD") == "$416.2B"
    assert format_value(2_500_000, "USD") == "$2.5M"
    assert format_value(1_250, "USD") == "$1.2K"


def test_usd_million_values_are_not_double_scaled() -> None:
    format_value = FORMATTERS["_format_monetary_value"]
    chart_value = FORMATTERS["_monetary_value_in_usd"]

    assert format_value(416_161, "USD millions") == "$416.2B"
    assert format_value(12.5, "USD millions") == "$12.5M"
    assert chart_value(416_161, "USD millions") == 416_161_000_000
    assert chart_value(416_161_000_000, "USD") == 416_161_000_000
    axis_expression = FORMATTERS["_USD_AXIS_LABEL_EXPRESSION"]
    assert all(suffix in axis_expression for suffix in ("'K'", "'M'", "'B'"))


def test_missing_values_remain_unavailable_or_an_em_dash() -> None:
    format_value = FORMATTERS["_format_monetary_value"]
    format_kpi = FORMATTERS["_format_kpi"]
    display_value = FORMATTERS["_display_value"]

    assert format_value(None, "USD") == "—"
    assert format_value(float("nan"), "USD millions") == "—"
    assert format_kpi(None, "USD") == "Unavailable"
    assert display_value(pd.NA, "Revenue", "USD") == "—"


def test_unit_formatting_does_not_modify_underlying_financial_data() -> None:
    raw = pd.DataFrame(
        [
            {"Fiscal Year": 2025, "Metric": "Revenue", "Value": 416_161_000_000, "Units": "USD"},
            {"Fiscal Year": 2025, "Metric": "Net Income", "Value": 112_010_000_000, "Units": "USD"},
        ]
    )
    original = raw.copy(deep=True)
    unit_map = FORMATTERS["_monetary_units_for_columns"](
        ("Revenue", "Net Income", "Free Cash Flow"), raw
    )

    assert unit_map == {"Revenue": "USD", "Net Income": "USD"}
    assert FORMATTERS["_display_value"](
        raw.loc[0, "Value"], "Revenue", unit_map["Revenue"]
    ) == "$416.2B"
    pd.testing.assert_frame_equal(raw, original)

